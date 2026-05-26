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

# 2. الإعدادات والرموز الأساسية (تقرأ من بيئة Render بأمان)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# هنا جعلناه يبحث عن أي مسمى للمفتاح لتفادي الأخطاء
TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or os.environ.get("API_KEY")
ADMIN_ID = 1436656132  # الأدمن

# 3. إعداد سيرفر الويب الوهمي لتخطي نظام النوم في Render
app = FastAPI()

@app.get("/")
def home():
    return "Bot is alive and running!"

# 4. دالة تشغيل بوت تليجرام في الخلفية مع كل الـ Handlers الأساسية
def start_bot():
    try:
        # بناء التطبيق
        application = Application.builder().token(BOT_TOKEN).build()
        
        # ربط الأوامر والرسائل والضغط على الأزرار
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
        
        logger.info("تم تشغيل بوت تليجرام بالخلفية بكافة الصلاحيات والمستمعات...")
        
        # تشغيل الـ Polling مع الحفاظ على الـ Event Loop لـ FastAPI
        application.run_polling(close_loop=False)
    except Exception as e:
        logger.error(f"خطأ أثناء تشغيل البوت: {e}")

# 5. رسالة الترحيب الأصلية لبوت فِلْمَه مع الأزرار التفاعلية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🎬 **مرحباً بك في بوت فِلْمَه!**\n\n"
        "مرحباً بك في عالم الأفلام والمسلسلات 🍿\n\n"
        "اختر من القائمة:\n"
        "🎬 بحث عن فيلم\n"
        "📺 بحث عن مسلسل\n"
        "🔍 بحث عام\n"
        "⭐ أفضل الأفلام تقييماً\n\n"
        "أو اكتب اسم أي فيلم مباشرة وأنا أجيب لك كل التفاصيل! 🎬"
