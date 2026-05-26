import os
import logging
import asyncio
import random
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
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

# ذاكرة مؤقتة للمفضلة تعتمد على معرف المستخدم (ID)
USER_FAVORITES = {}

# 3. إعداد سيرفر الويب FastAPI
app = FastAPI()

@app.get("/")
@app.head("/")
def home():
    return "Bot is alive and running!"

# 4. رسالة الترحيب الأصلية والمطورة لبوت فِلْمَه (ترتيب متناسق وجديد للأزرار)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🎬 **مرحباً بك في بوت فِلْمَه!**\n\n"
        "بوابتك الذكية لاستكشاف عالم السينما والأفلام والمسلسلات 🍿\n\n"
        "💡 **اضغط على أي زر بالأسفل لتحديد نوع البحث، أو اكتب اسم العمل الذي تريده مباشرة!**"
    )
    
    # تنسيق وترتيب الأزرار بشكل هندسي مريح للعين على الموبايل
    keyboard = [
        [
            InlineKeyboardButton("🎬 بحث عن فيلم", callback_data="search_movie"), 
            InlineKeyboardButton("📺 بحث عن مسلسل", callback_data="search_tv")
        ],
        [InlineKeyboardButton("🔍 بحث عام وشامل", callback_data="search_general")],
        [InlineKeyboardButton("⭐ أفضل الأفلام تقييماً", callback_data="top_rated")],
        [
            InlineKeyboardButton("🎲 فيلم عشوائي", callback_data="random_movie"),
            InlineKeyboardButton("❤️ قائمتي المفضلة", callback_data="show_favorites")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome, parse_mode="Markdown", reply_markup=reply_markup)

# --- إضافة جديدة: أمر المساعدة والشرح المطور ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🍿 **دليل استخدام بوت فِلْمَه:**\n\n"
        "🔹 **البحث المباشر:** أرسل اسم أي فيلم أو مسلسل في المحادثة مباشرة وسيتم جلب بوستر العمل، قصته، تقييمه، ورابط التريلر الخاص به.\n"
        "🔹 **البحث المخصص:** استخدم الأزرار بالأسفل لتحديد إذا كنت تبحث عن فيلم فقط أو مسلسل فقط لنتائج أدق.\n"
        "🔹 **المفضلة:** عند عرض أي عمل، يمكنك ضغط 'إضافة للمفضلة' للوصول للفيلم لاحقاً من قائمتك.\n\n"
        "💬 للعودة للبداية أرسل: /start"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# --- دالة مساعدة لجلب رابط التريلر من TMDB ---
def get_trailer_url(media_type, media_id):
    url = f"https://api.themoviedb.org/3/{media_type}/{media_id}/videos?api_key={TMDB_API_KEY}"
    try:
        res = requests.get(url).json()
        videos = res.get("results", [])
        for video in videos:
            if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                return f"https://www.youtube.com/watch?v={video.get('key')}"
    except Exception as e:
        logger.error(f"Error fetching trailer: {e}")
    return None

# 5. دالة معالجة الضغط على الأزرار التفاعلية
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    
    if data == "search_movie":
        context.user_data['search_type'] = 'movie'
        await query.edit_message_text("📥 أرسل لي اسم **الفيلم** الذي تبحث عنه باللغة العربية أو الإنجليزية:")
    elif data == "search_tv":
        context.user_data['search_type'] = 'tv'
        await query.edit_message_text("📥 أرسل لي اسم **المسلسل** الذي تبحث عنه:")
    elif data == "search_general":
        context.user_data['search_type'] = 'multi'
        await query.edit_message_text("📥 اكتب كلمة البحث العامة وسأفتش لك في الأفلام والمسلسلات معاً:")
        
    elif data == "top_rated":
        url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=ar-SA&page=1"
        try:
            res = requests.get(url).json()
            movies = res.get("results", [])[:5]
            if not movies:
                await query.edit_message_text("❌ لم أتمكن من جلب الأفلام حالياً.")
                return
                
            top_text = "⭐ **أفضل الأفلام تقييماً حالياً:**\n\n"
            for idx, movie in enumerate(movies, 1):
                top_text += f"{idx}. 🎬 **{movie.get('title')}** ({movie.get('release_date', '----')[:4]}) — ⭐ {movie.get('vote_average', 0.0)}/10\n"
            
            keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]]
            await query.edit_message_text(top_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"Error top rated: {e}")

    elif data == "random_movie":
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=ar-SA&sort_by=popularity.desc&page={random.randint(1, 5)}"
        try:
            res = requests.get(url).json()
            results = res.get("results", [])
            if results:
                movie = random.choice(results)
                title = movie.get("title")
                movie_id = movie.get("id")
                rating = movie.get("vote_average", 0.0)
                poster_path = movie.get("poster_path")
                year = movie.get("release_date", "----")[:4]
                
                result_text = f"🎲 **اقتراح فِلْمَه لك اليوم:**\n\n🎬 **الاسم:** {title} ({year})\n⭐ **التقييم:** {rating}/10\n"
                
                trailer = get_trailer_url("movie", movie_id)
                
                # ترتيب الأزرار بلمسة جمالية منسقة للنتائج
                keyboard = []
                if trailer:
                    keyboard.append([InlineKeyboardButton("🍿 مشاهدة الإعلان (التريلر)", url=trailer)])
                
                keyboard.append([
                    InlineKeyboardButton("📝 قصة العمل", callback_data=f"show_story_movie_{movie_id}"),
                    InlineKeyboardButton("❤️ للمفضلة", callback_data=f"add_fav_{movie_id}")
                ])
                keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])
                
                if poster_path:
                    await query.message.reply_photo(photo=f"https://image.tmdb.org/t/p/w500{poster_path}", caption=result_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    await query.message.reply_text(result_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"Error random movie: {e}")

    elif data.startswith("add_fav_"):
        media_id = data.split("_")[2]
        url = f"https://api.themoviedb.org/3/movie/{media_id}?api_key={TMDB_API_KEY}&language=ar"
        res = requests.get(url).json()
        title = res.get("title") or res.get("name") or "عمل غير معروف"
        
        if user_id not in USER_FAVORITES:
            USER_FAVORITES[user_id] = []
            
        if title not in USER_FAVORITES[user_id]:
            USER_FAVORITES[user_id].append(title)
            await query.message.reply_text(f"✅ تم إضافة **{title}** إلى قائمتك المفضلة! ❤️", parse_mode="Markdown")
        else:
            await query.message.reply_text(f"ℹ️ **{title}** موجود بالفعل في مفضلتك.", parse_mode="Markdown")

    elif data == "show_favorites":
        favs = USER_FAVORITES.get(user_id, [])
        if not favs:
            fav_text = "❤️ **قائمتك المفضلة فارغة حالياً.**\nابحث عن أعمال وأضفها عبر زر الحفظ!"
        else:
            fav_text = "⭐ **قائمتك المفضلة في فِلْمَه:**\n\n" + "\n".join([f"🍿 - {item}" for item in favs])
            
        keyboard = [[InlineKeyboardButton("🔙 العودة للقائمة", callback_data="main_menu")]]
        await query.message.reply_text(fav_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "main_menu":
        try:
            await query.message.delete()
        except:
            pass
        await start(update, context)

    elif data.startswith("show_story_"):
        _, _, media_type, media_id = data.split("_")
        url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}&language=ar"
        try:
            res = requests.get(url).json()
            overview = res.get("overview") or "لا يوجد وصف متوفر حالياً باللغة العربية."
            await query.message.reply_text(f"📝 **القصة:**\n\n{overview}", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error story: {e}")

# 6. دالة استقبال نصوص البحث والربط
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_query = update.message.text
    search_type = context.user_data.get('search_type', 'multi')
    
    await update.message.reply_text(f"🔍 جاري البحث عن: *{search_query}* في فِلْمَه...", parse_mode="Markdown")
    url = f"https://api.themoviedb.org/3/search/{search_type}?api_key={TMDB_API_KEY}&query={search_query}&language=ar"
    
    try:
        response = requests.get(url).json()
        results = response.get("results", [])
        if not results:
            await update.message.reply_text("❌ لم أتمكن من العثور على نتائج، تأكد من الاسم.")
            return
            
        first_result = results[0]
        actual_media_type = first_result.get("media_type", search_type)
        if actual_media_type == "multi":
            actual_media_type = "movie" if "title" in first_result else "tv"
            
        title = first_result.get("title") or first_result.get("name")
        rating = first_result.get("vote_average", 0.0)
        poster_path = first_result.get("poster_path")
        media_id = first_result.get("id")
        year = (first_result.get("release_date") or first_result.get("first_air_date") or "----")[:4]
        
        result_text = f"🎬 **الاسم:** {title} ({year})\n"
        result_text += f"🏷️ **النوع:** {'فيلم 🎬' if actual_media_type == 'movie' else 'مسلسل 📺'}\n"
        result_text += f"⭐ **التقييم:** {rating}/10\n"
        
        trailer_url = get_trailer_url(actual_media_type, media_id)
        
        # الترتيب المتناسق للأزرار تحت النتيجة
        keyboard = []
        if trailer_url:
            keyboard.append([InlineKeyboardButton("🍿 مشاهدة الإعلان (التريلر)", url=trailer_url)])
            
        keyboard.append([
            InlineKeyboardButton("📝 قصة العمل", callback_data=f"show_story_{actual_media_type}_{media_id}"),
            InlineKeyboardButton("❤️ للمفضلة", callback_data=f"add_fav_{media_id}")
        ])
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])
        
        if poster_path:
            await update.message.reply_photo(photo=f"https://image.tmdb.org/t/p/w500{poster_path}", caption=result_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(result_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            
        context.user_data['search_type'] = 'multi'
    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء الاتصال بالخادم.")

# 7. تشغيل البوت متزامن مع FastAPI وتثبيت أزرار قائمة الـ Menu برمجياً تلقائياً
@app.on_event("startup")
async def startup_event():
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        # إضافة المعالج الخاص بأمر المساعدة الجديد
        application.add_handler(CommandHandler("help", help_command))
        # تفعيل أوامر الـ Menu من الكود مباشرة لتعمل برمجياً دون تعليق
        application.add_handler(CommandHandler("top", lambda u, c: button_handler(u, c) if False else u.message.reply_text("اضغط على زر أفضل الأفلام من /start حالياً")))
        
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
        
        await application.initialize()
        await application.start()
        
        # --- إضافة أسطورية: تحديث وتعديل أزرار القائمة الجانبية (Menu) بشكل متناسق ومطابق للصورة تلقائياً ---
        await application.bot.set_my_commands([
            BotCommand("start", "🚀 تشغيل البوت والتحكم الرئيسي"),
            BotCommand("top", "⭐ أفضل الأفلام تقييماً حالياً"),
            BotCommand("help", "🔍 شرح طريقة استخدام البوت")
        ])
        
        asyncio.create_task(application.updater.start_polling())
        logger.info("تم تشغيل البوت وتحديث قائمة الأوامر بنجاح!")
    except Exception as e:
        logger.error(f"Startup error: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
