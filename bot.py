import os
import logging
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from models import db, Ayah, User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= Flask Setup ================= #
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()

# ================= Bot Config ================= #
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

# ================= Helper Functions ================= #
def save_ayah(ayah_id, text, audio_file_id):
    with app.app_context():
        existing = Ayah.query.filter_by(ayah_id=ayah_id).first()
        if existing:
            existing.text = text
            existing.audio_file_id = audio_file_id
        else:
            ayah = Ayah(ayah_id=ayah_id, text=text, audio_file_id=audio_file_id)
            db.session.add(ayah)
        db.session.commit()

def register_user(user):
    with app.app_context():
        if not User.query.filter_by(user_id=user.id).first():
            u = User(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            db.session.add(u)
            db.session.commit()

def get_user_count():
    with app.app_context():
        return User.query.count()

def get_ayah_count():
    with app.app_context():
        return Ayah.query.count()

# ================= Handlers ================= #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user)

    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "🌟 Assalomu alaykum!\n\nFoydalanuvchilar faqat admin tomonidan qo‘shilishi mumkin."
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ Siz admin emassiz!")
        return

    msg = update.message
    ayah_id = msg.caption
    audio_file_id = msg.audio.file_id if msg.audio else None

    if not ayah_id or not audio_file_id:
        await msg.reply_text("⚠️ Caption bo‘sh yoki audio mavjud emas.")
        return

    save_ayah(ayah_id, msg.caption, audio_file_id)
    await msg.reply_text(f"✅ Oyat saqlandi: {ayah_id}\n📊 Foydalanuvchilar: {get_user_count()}")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "stats":
        total_ayahs = get_ayah_count()
        total_users = get_user_count()
        await query.edit_message_text(f"📊 Statistika:\nOyatlar: {total_ayahs}\nFoydalanuvchilar: {total_users}")

# ================= Telegram Webhook ================= #
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put(update)
    return "ok"

# ================= Main ================= #
def main():
    global application
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.ALL & filters.FORWARDED, handle_forward))
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    # Flask app uchun webhook
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    main()
