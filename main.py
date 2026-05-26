import os
import logging
import asyncio
import requests
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

# 3. إعداد سيرفر الويب FastAPI لدعم GET و HEAD معاً
app = FastAPI()

@app.get("/")
@app.head("/")
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
    
    # تفادي مشاكل استدعاء الدالة من رسالة أو من زر تراجع
    if update.message:
        await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome, parse_mode="Markdown", reply_markup=reply_markup)

# 5. دالة معالجة الضغط على الأزرار التفاعلية وتطويرها
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "search_movie":
        context.user_data['search_type'] = 'movie'
        await query.edit_message_text("📥 أرسل لي اسم **الفيلم** الذي تبحث عنه باللغة العربية أو الإنجليزية:")
    elif query.data == "search_tv":
        context.user_data['search_type'] = 'tv'
        await query.edit_message_text("📥 أرسل لي اسم **المسلسل** الذي تبحث عنه:")
    elif query.data == "search_general":
        context.user_data['search_type'] = 'multi'
        await query.edit_message_text("📥 اكتب كلمة البحث العامة وسأفتش لك في الأفلام والمسلسلات معاً:")
        
    # --- تطوير: تشغيل ميزة أفضل الأفلام تقييماً تلقائياً ---
    elif query.data == "top_rated":
        await query.edit_message_text("🔄 جاري جلب قائمة أفضل الأفلام تقييماً من TMDB...")
        url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=ar-SA&page=1"
        try:
            res = requests.get(url).json()
            movies = res.get("results", [])[:5] # جلب أفضل 5 أفلام لشاشات الموبايل
            
            if not movies:
                await query.edit_message_text("❌ لم أتمكن من جلب الأفلام حالياً، حاول لاحقاً.")
                return
                
            top_text = "⭐ **أفضل الأفلام تقييماً حالياً:**\n\n"
            for idx, movie in enumerate(movies, 1):
                title = movie.get("title")
                rating = movie.get("vote_average", 0.0)
                year = movie.get("release_date", "----")[:4]
                top_text += f"{idx}. 🎬 **{title}** ({year}) — ⭐ {rating}/10\n"
            
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")]]
            await query.edit_message_text(top_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            
        except Exception as e:
            logger.error(f"خطأ في جلب أفضل الأفلام: {e}")
            await query.edit_message_text("⚠️ حدث خطأ أثناء الاتصال بالسيرفر.")
            
    # زر العودة للقائمة الرئيسية
    elif query.data == "main_menu":
        await query.message.delete() # حذف الرسالة الحالية لإرسال القائمة بشكل نظيف
        await start(update, context)

    # --- تطوير: عرض قصة العمل عند الضغط على الزر الفرعي للفيلم ---
    elif query.data.startswith("show_story_"):
        _, media_type, media_id = query.data.split("_")
        url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}&language=ar"
        try:
            res = requests.get(url).json()
            overview = res.get("overview") or "لا يوجد وصف متوفر حالياً باللغة العربية."
            title = res.get("title") or res.get("name")
            
            story_text = f"📝 **قصة عمل ({title}):**\n\n{overview}"
            await query.message.reply_text(story_text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"خطأ في جلب قصة العمل: {e}")

# 6. دالة استقبال نصوص البحث والربط المطور مع TMDB
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_query = update.message.text
    
    # معرفة نوع البحث المحدد من الأزرار (فيلم، مسلسل، أو عام)، الافتراضي عام 'multi'
    search_type = context.user_data.get('search_type', 'multi')
    
    await update.message.reply_text(f"🔍 جاري البحث عن: *{search_query}* في قاعدة بيانات فِلْمَه...", parse_mode="Markdown")
    
    # تحديد رابط الـ API بناءً على اختيار المستخدم لضمان دقة البحث
    url = f"https://api.themoviedb.org/3/search/{search_type}?api_key={TMDB_API_KEY}&query={search_query}&language=ar"
    
    try:
        response = requests.get(url).json()
        results = response.get("results", [])
        
        if not results:
            await update.message.reply_text("❌ لم أتمكن من العثور على أي نتائج، تأكد من كتابة الاسم بشكل صحيح.")
            return
            
        first_result = results[0]
        
        # استخراج البيانات بذكاء حسب نوع النتيجة المسترجعة
        actual_media_type = first_result.get("media_type", search_type)
        if actual_media_type == "multi": 
            actual_media_type = "movie" if "title" in first_result else "tv"
            
        title = first_result.get("title") or first_result.get("name") or "عنوان غير معروف"
        rating = first_result.get("vote_average", 0.0)
        poster_path = first_result.get("poster_path")
        media_id = first_result.get("id")
        year = (first_result.get("release_date") or first_result.get("first_air_date") or "----")[:4]
        
        result_text = f"🎬 **الاسم:** {title} ({year})\n"
        result_text += f"🏷️ **النوع:** {'فيلم 🎬' if actual_media_type == 'movie' else 'مسلسل 📺'}\n"
        result_text += f"⭐ **التقييم:** {rating}/10\n"
        
        # أزرار تفاعلية تظهر أسفل النتيجة تجعل شكل البوت احترافي وسريع على الموبايل
        keyboard = [
            [InlineKeyboardButton("⭐ قصة العمل بالتفصيل", callback_data=f"show_story_{actual_media_type}_{media_id}")],
            [InlineKeyboardButton("🔙 قائمة البحث الرئيسية", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            await update.message.reply_photo(photo=poster_url, caption=result_text, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            await update.message.reply_text(result_text, parse_mode="Markdown", reply_markup=reply_markup)
            
        # إعادة تعيين نوع البحث التلقائي بعد انتهاء العملية
        context.user_data['search_type'] = 'multi'
            
    except Exception as e:
        logger.error(f"خطأ أثناء جلب البيانات من TMDB: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء الاتصال بقاعدة بيانات الأفلام، يرجى المحاولة لاحقاً.")

# 7. تشغيل البوت متزامن مع الـ Startup لـ FastAPI
@app.on_event("startup")
async def startup_event():
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
        
        await application.initialize()
        await application.start()
        asyncio.create_task(application.updater.start_polling())
        logger.info("تم تشغيل مستمعات البوت بنجاح متزامن مع FastAPI!")
    except Exception as e:
        logger.error(f"خطأ أثناء تشغيل البوت في الـ startup: {e}")

# 8. تشغيل السيرفر الرئيسي
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
