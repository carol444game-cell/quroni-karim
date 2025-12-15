import os, asyncio, threading, random, logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from models import db, Ayah

# ================= LOG =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= FLASK =================
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()

# ================= ENV =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = str(os.environ.get("ADMIN_ID"))
PORT = int(os.environ.get("PORT", 5000))

# Render webhook auto
RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
WEBHOOK_URL = f"https://{RENDER_HOST}/webhook" if RENDER_HOST else None

application = None
loop = None

# ================= HELPERS =================
def save_ayah_auto(uid, sura, ayah, text, audio, channel, msg_id):
    with app.app_context():
        if Ayah.query.filter_by(ayah_uid=uid).first():
            return False
        db.session.add(
            Ayah(
                ayah_uid=uid,
                sura=sura,
                ayah_number=ayah,
                text=text,
                audio_file_id=audio,
                channel_id=channel,
                message_id=msg_id
            )
        )
        db.session.commit()
        return True

def get_random_ayah():
    with app.app_context():
        count = Ayah.query.count()
        if count == 0:
            return None
        return Ayah.query.offset(random.randint(0, count - 1)).first()

def search_ayah(q):
    with app.app_context():
        return Ayah.query.filter(
            Ayah.sura.ilike(f"%{q}%") |
            Ayah.text.ilike(f"%{q}%")
        ).limit(10).all()

# ================= USER COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "╔════════════════════╗\n"
        "🕋 <b>QUR'ON BOT</b>\n"
        "╚════════════════════╝\n\n"
        "📖 Oyatlar va qiroatlar\n"
        "🔍 Sura yoki oyat nomini yozing\n\n"
        "💎 Premium Qur'on xizmati"
    )
    kb = [[InlineKeyboardButton("🎲 Tasodifiy oyat", callback_data="rnd")]]
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def random_ayah(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ayah = get_random_ayah()
    if not ayah:
        await update.message.reply_text("❌ Oyatlar yo‘q")
        return

    caption = (
        f"🕋 <b>{ayah.sura}</b>\n"
        f"📖 Oyat: <b>{ayah.ayah_number}</b>\n\n"
        f"{ayah.text or ''}"
    )

    if ayah.audio_file_id:
        await context.bot.send_audio(
            update.effective_chat.id,
            ayah.audio_file_id,
            caption=caption,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(caption, parse_mode="HTML")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if len(q) < 2:
        return
    res = search_ayah(q)
    if not res:
        await update.message.reply_text("❌ Topilmadi")
        return

    kb = [[InlineKeyboardButton(
        f"{a.sura} ({a.ayah_number})",
        callback_data=a.ayah_uid
    )] for a in res]

    await update.message.reply_text(
        "🔍 <b>QIDIRUV</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= CALLBACK =================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "rnd":
        await random_ayah(q, context)
        return

    with app.app_context():
        ayah = Ayah.query.filter_by(ayah_uid=q.data).first()

    if not ayah:
        await q.edit_message_text("❌ Topilmadi")
        return

    text = (
        f"🕋 <b>{ayah.sura}</b>\n"
        f"📖 Oyat: <b>{ayah.ayah_number}</b>\n\n"
        f"{ayah.text or ''}"
    )

    if ayah.audio_file_id:
        await context.bot.send_audio(
            q.message.chat.id,
            ayah.audio_file_id,
            caption=text,
            parse_mode="HTML"
        )
    else:
        await q.message.reply_text(text, parse_mode="HTML")

# ================= ADMIN AUTO INDEX =================
async def auto_index(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        return

    msg = update.message
    origin = msg.forward_origin
    if not origin or not hasattr(origin, "chat"):
        return

    # Caption format: SURA|OYAT
    caption = msg.caption or ""
    if "|" not in caption:
        await msg.reply_text("❌ Caption: SURA|OYAT")
        return

    sura, ayah = caption.split("|", 1)

    text = msg.text or ""
    audio = msg.audio.file_id if msg.audio else None

    uid = f"{origin.chat.id}_{origin.message_id}"

    ok = save_ayah_auto(
        uid,
        sura.strip(),
        ayah.strip(),
        text.strip(),
        audio,
        str(origin.chat.id),
        str(origin.message_id)
    )

    if ok:
        await msg.reply_text("✅ Oyat avtomatik indexlandi")
    else:
        await msg.reply_text("⚠️ Bu oyat avval qo‘shilgan")

# ================= INIT =================
def create_bot():
    bot = Application.builder().token(BOT_TOKEN).build()
    bot.add_handler(CommandHandler("start", start))
    bot.add_handler(CommandHandler("random", random_ayah))
    bot.add_handler(CallbackQueryHandler(callbacks))
    bot.add_handler(MessageHandler(filters.FORWARDED, auto_index))
    bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    return bot

async def run_bot():
    global application
    application = create_bot()
    await application.initialize()
    await application.start()

    if WEBHOOK_URL:
        await application.bot.set_webhook(WEBHOOK_URL)

    while True:
        await asyncio.sleep(3600)

def start_bot():
    def r():
        global loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot())
    threading.Thread(target=r, daemon=True).start()

# ================= WEBHOOK =================
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, application.bot)
    asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    return "ok"

@app.route("/")
def index():
    return "🕋 Qur'on bot ishlayapti"

if BOT_TOKEN:
    start_bot()

if __name__ == "__main__":
    app.run("0.0.0.0", PORT)
