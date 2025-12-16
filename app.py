import os
import logging
from uuid import uuid4

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from pytube import YouTube, Search

# --- KONFIGURATSIYA (MUHIT O'ZGARUVCHILARI) ---
TOKEN = os.getenv("BOT_TOKEN")  
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME") 
WEB_SERVER_PORT = os.getenv("PORT", 8080) 

# --- TEKSHIRUV ---
if not TOKEN:
    raise ValueError("❌ BOT_TOKEN environment o'zgaruvchisi o'rnatilmagan.")

# --- WEBHOOK MANZILLARI ---
WEBHOOK_PATH = f'/{TOKEN}'
# Webhook URL har doim HTTPS bo'lishi kerak
if WEBHOOK_HOST:
    WEBHOOK_URL = f'https://{WEBHOOK_HOST}{WEBHOOK_PATH}'
else:
    # Lokal testlar uchun placeholder
    WEBHOOK_URL = None 

# --- PAPKA VA LOGLAR ---
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- AIOGRAM OBYEKTLARI ---
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# --- HANDLERS (BOT MANTIG'I) ---

async def set_default_commands(bot: Bot):
    """Botning asosiy buyruqlarini sozlash."""
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish"),
    ])

@dp.message(F.text == '/start')
async def command_start_handler(message: types.Message):
    """Foydalanuvchi /start buyrug'ini yuborganda ishlaydi."""
    await message.answer(
        f"Salom, {message.from_user.full_name}! 👋\n"
        "Men qo'shiq qidiruvchi botman. Menga qo'shiq nomini yuboring."
    )

@dp.message(F.text)
async def handle_music_query(message: types.Message):
    """Qo'shiq nomini qabul qiladi, YouTube'da qidiradi va audio faylni qaytaradi."""
    query = message.text
    chat_id = message.chat.id
    temp_filename = None
    
    status_msg = await message.answer(f"🎵 Qidiruv boshlandi: **{query}**")
    
    try:
        # 1. YouTube'da qidirish
        s = Search(query)
        if not s.results:
            await status_msg.edit_text("❌ Afsuski, bu so'z bo'yicha natija topilmadi.")
            return

        video_url = s.results[0].watch_url
        video_title = s.results[0].title
        await status_msg.edit_text(f"✅ Topildi: **{video_title}**\nYuklab olinmoqda, bu biroz vaqt olishi mumkin...")
        
        # 2. Yuklab Olish
        temp_filename = os.path.join(DOWNLOAD_FOLDER, f"{uuid4()}.mp3")
        yt = YouTube(video_url)
        # Eng yaxshi audio sifatini tanlash
        audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
        out_file = audio_stream.download(output_path=DOWNLOAD_FOLDER)
        
        # Fayl nomini .mp3 ga o'zgartirish
        base, ext = os.path.splitext(out_file)
        os.rename(out_file, temp_filename)

        logger.info(f"Fayl yuklandi: {temp_filename}")
        
        # 3. Audio Faylni Yuborish
        audio_file = types.FSInputFile(temp_filename)
        await bot.send_audio(
            chat_id=chat_id, 
            audio=audio_file,
            caption=f"🎵 {video_title}",
            performer=yt.author
        )
        await status_msg.delete() 
        
    except Exception as e:
        logger.error(f"Xato yuz berdi: {e}")
        await status_msg.edit_text("❌ Qo'shiqni topish yoki yuklab olishda xatolik yuz berdi. Iltimos, boshqa nom bilan urinib ko'ring.")
    finally:
        # 4. Vaqtincha faylni o'chirish
        if temp_filename and os.path.exists(temp_filename):
            os.remove(temp_filename)
            logger.info(f"Fayl o'chirildi: {temp_filename}")


# --- WEBHOOK VA SERVER FUNKSIYALARI ---

async def on_startup(bot: Bot):
    """Server ishga tushganda avtomatik Webhookni o'rnatish."""
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)
        await set_default_commands(bot)
        logger.info(f"🚀 Webhook avtomatik o'rnatildi: {WEBHOOK_URL}")
    else:
        logger.warning("RENDER_EXTERNAL_HOSTNAME topilmagani sababli Webhook o'rnatilmadi. Lokal Polling kerak.")

async def on_shutdown(bot: Bot):
    """Server to'xtaganda Webhookni o'chirish."""
    if WEBHOOK_URL:
        await bot.delete_webhook()
        logger.info("🛑 Webhook o'chirildi.")


# Gunicorn orqali ishlatiladigan aiohttp web-serverini yaratuvchi funksiya
def init_web_server():
    """Gunicorn uchun aiohttp Web-ilovasini sozlaydi va qaytaradi."""
    
    # Webhook sozlamalarini dispatcherga ulash
    dp.workflow_data.update({
        'base_url': f"https://{WEBHOOK_HOST}",
        'webhook_path': WEBHOOK_PATH
    })
    
    # aiohttp ilovasini yaratish va dispatcher ni ulash
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, dp.web_handlers['aiohttp'])
    
    # Ishga tushirish/to'xtatish funksiyalarini ulash
    app.on_startup.append(lambda _: on_startup(bot))
    app.on_shutdown.append(lambda _: on_shutdown(bot))
    
    return app


# --- ISHGA TUSHIRISH (Gunicorn emas, lokal testlar uchun) ---
if __name__ == '__main__':
    if WEBHOOK_HOST:
        logger.info("Server Webhook rejimida ishga tushirilmoqda...")
        # Web serverni to'g'ridan-to'g'ri ishga tushirish (Gunicorn emas)
        web.run_app(
            init_web_server(),
            host='0.0.0.0',
            port=WEB_SERVER_PORT
        )
    else:
        logger.info("Lokal sinov rejimi: Polling ishga tushirildi...")
        dp.run_polling(bot)
