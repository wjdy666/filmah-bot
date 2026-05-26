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
TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or os.environ.get("API_KEY")
ADMIN_ID = 1436656132

# 3. إعداد سيرفر الويب الوهمي لتخطي نظام النوم في Render
app = FastAPI()

@app.get("/")
def home():
    return "Bot is alive and running!"

# 4. رسالة الترحيب الأصلية لبوت فِلْمَه مع الأزرار التفاعلية
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
    )
    
    keyboard = [
        [InlineKeyboardButton("🎬 بحث عن فيلم", callback_data="search_movie")],
        [InlineKeyboardButton("📺 بحث عن مسلسل", callback_data="search_tv")],
        [InlineKeyboardButton("🔍 بحث عام", callback_data="search_general")],
        [InlineKeyboardButton("⭐ أفضل الأفلام تقييماً", callback_data="top_rated")]
    ]
