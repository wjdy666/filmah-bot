import os
import logging
import requests
import threading
from fastapi import FastAPI
import uvicorn

# 1. إعداد سيرفر الويب الوهمي لتخطي نظام النوم في Render
app = FastAPI()

@app.get("/")
def home():
    return "Bot is alive and running!"

def run_web():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --------------------------------------------------------
# 2. كود بوت التليجرام الأساسي (فِلْمَه)
# --------------------------------------------------------
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# لمراقبة أداء البوت إعداد الـ Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الإعدادات الأساسية
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("API_KEY")
ADMIN_ID = 1436656132  # الخاص بك كأدمن

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب الأصلية للبوت"""
    welcome = (
        "🎬 **مرحباً بك في بوت فِلْمَه!**\n"
        "أنا دليلك الذكي لاكتشاف الأفلام والمسلسلات الاحترافية.\n"
        "ابحث عن أي فيلم أو مسلسل، وسأحضر لك البوستر، القصة، والتقييم، "
        "مع توفير روابط الدعم والمشاهدة مباشرة داخل تليجرام.\n"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")
