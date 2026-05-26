import os
import logging
import requests
import threading
from fastapi import FastAPI
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# 1. إعدادات الـ Logs لمراقبة الأداء
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. الإعدادات والرموز الأساسية
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("API_KEY")
ADMIN_ID = 1436656132

# 3. إعداد سيرفر الويب الوهمي لتخطي نظام النوم
app = FastAPI()

@app.get("/")
def home():
    return "Bot is alive and running!"

# 4. دالة تشغيل بوت تليجرام في الخلفية
def start_bot():
    try:
        # بناء التطبيق وتشغيله بنظام الـ Polling
        application = Application.builder().token(BOT_TOKEN).build()
        
        # ربط الدوال (مثال دالة start الأصلية لبوت فِلْمَه)
        application.add_handler(CommandHandler("start", start))
        
        logger.info("تم تشغيل بوت تليجرام في الخلفية بنجاح...")
        application.run_polling(close_loop=False)
    except Exception as e:
        logger.error(f"خطأ أثناء تشغيل البوت: {e}")

# 5. رسالة الترحيب الأصلية لبوت فِلْمَه
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🎬 **مرحباً بك في بوت فِلْمَه!**\n"
        "أنا دليلك الذكي لاكتشاف الأفلام والمسلسلات الاحترافية.\n"
        "ابحث عن أي فيلم أو مسلسل، وسأحضر لك البوستر، القصة، والتقييم، "
        "مع توفير روابط الدعم والمشاهدة مباشرة داخل تليجرام.\n"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

# 6. نقطة الانطلاق الرئيسية للسيرفر (هنا السر لـ Render)
if __name__ == "__main__":
    # تشغيل البوت في خيط (Thread) مستقل أولاً
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # تشغيل سيرفر الويب فوراً في الواجهة الأساسية ليستمع للمنفذ ويعطي Render إشارة نجاح 200 OK
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
