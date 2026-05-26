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
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome, parse_mode="Markdown", reply_markup=reply_markup)

# 5. دالة معالجة الضغط على الأزرار التفاعلية
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "search_movie":
        await query.edit_message_text("📥 أرسل لي اسم الفيلم الذي تبحث عنه باللغة العربية أو الإنجليزية:")
    elif query.data == "search_tv":
        await query.edit_message_text("📥 أرسل لي اسم المسلسل الذي تبحث عنه:")
    elif query.data == "search_general":
        await query.edit_message_text("📥 اكتب كلمة البحث العامة وسأفتش لك في الأفلام والمسلسلات:")
    elif query.data == "top_rated":
        await query.edit_message_text("🔄 جاري جلب قائمة أفضل الأفلام تقييماً من TMDB...")

# 6. دالة استقبال نصوص البحث والربط مع TMDB
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_query = update.message.text
    await update.message.reply_text(f"🔍 جاري البحث عن: *{search_query}* في قاعدة بيانات TMDB...", parse_mode="Markdown")
    
    url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={search_query}&language=ar"
    
    try:
        response = requests.get(url).json()
        results = response.get("results", [])
        
        if not results:
            await update.message.reply_text("❌ لم أتمكن من العثور على أي نتائج، تأكد من كتابة الاسم بشكل صحيح.")
            return
            
        first_result = results[0]
        media_type = first_result.get("media_type", "movie")
        title = first_result.get("title") or first_result.get("name") or "عنوان غير معروف"
        overview = first_result.get("overview") or "لا يوجد وصف متوفر حالياً."
        rating = first_result.get("vote_average", 0.0)
        poster_path = first_result.get("poster_path")
        
        result_text = f"🎬 **الاسم:** {title}\n"
        result_text += f"🏷️ **النوع:** {'فيلم' if media_type == 'movie' else 'مسلسل'}\n"
        result_text += f"⭐ **التقييم:** {rating}/10\n\n"
        result_text += f"📝 **القصة:**\n{overview}"
        
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            await update.message.reply_photo(photo=poster_url, caption=result_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(result_text, parse_mode="Markdown")
            
    except Exception as e:
        logger.error(f"خطأ أثناء جلب البيانات من TMDB: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء الاتصال بقاعدة بيانات الأفلام، يرجى المحاولة لاحقاً.")

# 7. دالة تشغيل بوت تليجرام في الخلفية
def start_bot():
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
        
        logger.info("تم تشغيل مستمعات البوت بنجاح...")
        application.run_polling(close_loop=False)
    except Exception as e:
        logger.error(f"خطأ أثناء تشغيل البوت: {e}")

# 8. تشغيل السيرفر والبوت معاً
if __name__ == "__main__":
    # تشغيل البوت في خيط مستقل كخلفية لعدم حظر المنفذ
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    
    # تشغيل سيرفر الويب في الواجهة الأمامية لرد الـ Live لـ Render
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
