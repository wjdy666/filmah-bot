import os
import logging
import random
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# 1. إعدادات الـ Logs لمراقبة البوت
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. جلب المتغيرات الأساسية (التوكن ومفتاح الأفلام)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or os.environ.get("API_KEY")

# ذاكرة مؤقتة للمفضلة تعتمد على معرف المستخدم
USER_FAVORITES = {}

# القائمة الكاملة والموسعة لتصنيفات الأفلام (بدون أي نقص)
GENRES = {
    "action": {"id": 28, "name": "💥 أكشن"},
    "adventure": {"id": 12, "name": "🤠 مغامرة"},
    "animation": {"id": 16, "name": "🎨 أنمي ورسوم"},
    "comedy": {"id": 35, "name": "🍿 كوميدي"},
    "crime": {"id": 80, "name": "🕵️ جريمة"},
    "drama": {"id": 18, "name": "🎭 دراما"},
    "family": {"id": 10751, "name": "👨‍👩‍👧 عائلي"},
    "fantasy": {"id": 14, "name": "🧝 خيال وفانتازيا"},
    "horror": {"id": 27, "name": "👻 رعب"},
    "mystery": {"id": 9648, "name": "🧩 غموض"},
    "scifi": {"id": 878, "name": "🛸 خيال علمي"},
    "thriller": {"id": 53, "name": "🥶 إثارة وتشويق"}
}

# 3. إعداد سيرفر FastAPI لمنع ريندر من النوم
app = FastAPI()

@app.get("/")
@app.head("/")
def home():
    return "Filmah Bot is fully and smoothly running!"

# دالة جلب رابط التريلر (الإعلان) من TMDB
def get_trailer_url(media_type, media_id):
    url = f"https://api.themoviedb.org/3/{media_type}/{media_id}/videos?api_key={TMDB_API_KEY}"
    try:
        res = requests.get(url, timeout=5).json()
        videos = res.get("results", [])
        for video in videos:
            if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                return f"https://www.youtube.com/watch?v={video.get('key')}"
    except Exception as e:
        logger.error(f"Error fetching trailer: {e}")
    return None

# دالة توليد روابط المشاهدة من السيرفر الخارجي المترجم
def generate_watch_url(media_type, media_id):
    if media_type == "movie":
        return f"https://vidsrc.me/embed/movie?tmdb={media_id}"
    else:
        return f"https://vidsrc.me/embed/tv?tmdb={media_id}"

# 4. دالة بناء وإرسال بطاقة الفيلم الاحترافية بالبوستر والوصف الكامل
async def send_movie_card(context, chat_id, movie):
    try:
        movie_id = movie.get("id")
        actual_media_type = "movie" if "title" in movie else "tv"

        title = movie.get("title") or movie.get("name") or "عمل غير معروف"
        rating = movie.get("vote_average", 0.0)
        poster_path = movie.get("poster_path")

        overview = movie.get("overview") or "لا يوجد وصف متوفر حالياً باللغة العربية لهذا العمل."
        if len(overview) > 400:
            overview = overview[:400] + "..."

        year = (movie.get("release_date") or movie.get("first_air_date") or "----")[:4]

        result_text = (
            f"🎬 **الاسم:** {title} ({year})\n"
            f"🏷️ **النوع:** {'فيلم 🎬' if actual_media_type == 'movie' else 'مسلسل 📺'}\n"
            f"⭐ **التقييم:** {rating}/10\n\n"
            f"📝 **قصة العمل:**\n{overview}\n\n"
            f"💡 _تنويه للمشاهدة:_ يفضل فتح روابط المشاهدة عبر متصفح يدعم حظر الإعلانات مثل **Brave** لتجربة خالية من الإزعاج."
        )

        watch_url = generate_watch_url(actual_media_type, movie_id)
        trailer_url = get_trailer_url(actual_media_type, movie_id)

        # بناء الأزرار التحتية للبطاقة
        keyboard = [
            [InlineKeyboardButton("🍿 مشاهدة العمل الآن", url=watch_url)]
        ]

        if trailer_url:
            keyboard.append([InlineKeyboardButton("🎬 مشاهدة الإعلان (التريلر)", url=trailer_url)])

        keyboard.append([
            InlineKeyboardButton("❤️ للمفضلة", callback_data=f"add_fav_{movie_id}"),
            InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")
        ])

        if poster_path:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=f"https://image.tmdb.org/t/p/w500{poster_path}",
                caption=result_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=result_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as e:
        logger.error(f"Error in send_movie_card: {e}")

# 5. الأوامر الرئيسية للترحيب والمساعدة
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🎬 **مرحباً بك في بوت فِلْمَه!**\n\n"
        "بوابتك الذكية لاستكشاف عالم السينما ومشاهدة الأفلام والمسلسلات 🍿\n\n"
        "💡 **اختر نوع البحث من الأزرار بالأسفل، أو اكتب اسم الفيلم/المسلسل مباشرة في الشات!**"
    )

    keyboard = [
        [
            InlineKeyboardButton("🎬 بحث عن فيلم", callback_data="search_movie"),
            InlineKeyboardButton("📺 بحث عن مسلسل", callback_data="search_tv")
        ],
        [
            InlineKeyboardButton("🔍 بحث عام وشامل", callback_data="search_general"),
            InlineKeyboardButton("🎭 تصنيفات الأفلام", callback_data="show_genres")
        ],
        [InlineKeyboardButton("⭐ أفضل الأفلام تقييماً", callback_data="top_rated")],
        [
            InlineKeyboardButton("🎲 فيلم عشوائي", callback_data="random_movie"),
            InlineKeyboardButton("❤️ قائمتي المفضلة", callback_data="show_favorites")
        ]
    ]

    if update.message:
        await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        try:
            await update.callback_query.message.delete()
        except:
            pass
        await update.callback_query.message.reply_text(welcome, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🍿 **دليل استخدام بوت فِلْمَه:**\n\n"
        "🔹 **البحث المباشر:** اكتب اسم الفيلم أو المسلسل في المحادثة مباشرة وسيجلبه البوت فوراً.\n"
        "🔹 **المشاهدة:** الأزرار توفر سيرفرات تدعم الترجمة والتشغيل السريع.\n"
        "🔹 **المفضلة:** زر الحفظ يحفظ أعمالك للرجوع لها عبر القائمة الرئيسية.\n\n"
        "💬 للعودة للبداية أرسل: /start"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# 6. معالج الأزرار وقوائم التحكم السريعة الموسعة
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    data = query.data

    if data == "search_movie":
        context.user_data['search_type'] = 'movie'
        await query.edit_message_text("📥 أرسل الآن اسم **الفيلم** الذي تبحث عنه باللغة العربية أو الإنجليزية:")

    elif data == "search_tv":
        context.user_data['search_type'] = 'tv'
        await query.edit_message_text("📥 أرسل الآن اسم **المسلسل** الذي تبحث عنه:")

    elif data == "search_general":
        context.user_data['search_type'] = 'multi'
        await query.edit_message_text("📥 اكتب اسم العمل (فيلم أو مسلسل) للبحث الشامل والمباشر:")

    elif data == "show_genres":
        genre_text = "🎭 **اختر تصنيفك المفضّل الليلة:**\n\nسأعرض لك باقة من أفضل الأفلام العالمية المتاحة بناءً على اختيارك!"
        keyboard = []
        genre_list = list(GENRES.items())
        # ترتيب الأزرار بشكل ثنائي متناسق وجميل
        for i in range(0, len(genre_list), 2):
            row = [InlineKeyboardButton(genre_list[i][1]["name"], callback_data=f"genre_fetch_{genre_list[i][0]}")]
            if i + 1 < len(genre_list):
                row.append(InlineKeyboardButton(genre_list[i + 1][1]["name"], callback_data=f"genre_fetch_{genre_list[i + 1][0]}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")])
        await query.edit_message_text(genre_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("genre_fetch_"):
        genre_key = data.split("_")[2]
        genre_id = GENRES[genre_key]["id"]
        genre_name = GENRES[genre_key]["name"]
        status_msg = await query.message.reply_text(f"🔄 جاري جلب أفضل أفلام {genre_name}...")
        
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=ar-SA&sort_by=popularity.desc&with_genres={genre_id}&page=1"
        try:
            res = requests.get(url, timeout=5).json()
            movies = res.get("results", [])
            try: await status_msg.delete()
            except: pass
            if not movies:
                await query.message.reply_text("❌ لم يتم العثور على أعمال في هذا التصنيف حالياً.")
                return
            # جلب أعلى 3 أفلام شعبية في التصنيف ببطاقات منفصلة
            for movie in movies[:3]:
                await send_movie_card(context, chat_id, movie)
        except Exception as e:
            logger.error(f"Genre fetch error: {e}")

    elif data == "top_rated":
        status_msg = await query.message.reply_text("🔄 جاري جلب أعلى الأفلام تقييماً عالمياً...")
        url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=ar-SA&page=1"
        try:
            res = requests.get(url, timeout=5).json()
            movies = res.get("results", [])
            try: await status_msg.delete()
            except: pass
            if not movies:
                await query.message.reply_text("❌ عذراً، فشل جلب القائمة من خوادم الأفلام.")
                return
            for movie in movies[:3]:
                await send_movie_card(context, chat_id, movie)
        except Exception as e:
            logger.error(f"Top rated error: {e}")

    elif data == "random_movie":
        # اختيار صفحة عشوائية لضمان تنوع الأفلام المقترحة للمستخدم في كل مرة
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=ar-SA&sort_by=popularity.desc&page={random.randint(1, 5)}"
        try:
            res = requests.get(url, timeout=5).json()
            results = res.get("results", [])
            if results:
                movie = random.choice(results)
                await send_movie_card(context, chat_id, movie)
        except Exception as e:
            logger.error(f"Random movie error: {e}")

    elif data.startswith("add_fav_"):
        media_id = data.split("_")[2]
        url = f"https://api.themoviedb.org/3/movie/{media_id}?api_key={TMDB_API_KEY}&language=ar"
        try:
            res = requests.get(url, timeout=5).json()
            title = res.get("title") or res.get("name") or "عمل غير معروف"
            if user_id not in USER_FAVORITES:
                USER_FAVORITES[user_id] = []
            if title not in USER_FAVORITES[user_id]:
                USER_FAVORITES[user_id].append(title)
                await query.message.reply_text(f"✅ تم إضافة **{title}** إلى مفضلتك! ❤️", parse_mode="Markdown")
            else:
                await query.message.reply_text(f"ℹ️ **{title}** موجود بالفعل في المفضلة.", parse_mode="Markdown")
        except:
            pass

    elif data == "show_favorites":
        favs = USER_FAVORITES.get(user_id, [])
        if not favs:
            fav_text = "❤️ **قائمتك المفضلة فارغة حالياً.**\nتصفح الأعمال واضغط على زر الإضافة لحفظها هنا!"
        else:
            fav_text = "⭐ **قائمتك المفضلة في فِلْمَه:**\n\n" + "\n".join([f"🍿 - {item}" for item in favs])
        await query.message.reply_text(fav_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]]))

    elif data == "main_menu":
        try: await query.message.delete()
        except: pass
        await start(update, context)

# 7. معالجة نصوص البحث المباشرة من الشات بدقة عالية باللغة العربية
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_query = update.message.text
    search_type = context.user_data.get('search_type', 'multi')
    chat_id = update.message.chat_id

    await update.message.reply_text(f"🔍 جاري البحث عن: *{search_query}* في سيرفرات فِلْمَه...", parse_mode="Markdown")
    url = f"https://api.themoviedb.org/3/search/{search_type}?api_key={TMDB_API_KEY}&query={search_query}&language=ar-SA"
    try:
        res = requests.get(url, timeout=5).json()
        results = res.get("results", [])
        if not filter(None, results):
            await update.message.reply_text("❌ لم أتمكن من العثور على نتائج، يرجى التأكد من كتابة اسم العمل بشكل صحيح.")
            return
        
        # إرسال النتيجة الأولى الأكثر تطابقاً وشهرة
        await send_movie_card(context, chat_id, results[0])
        # إعادة تعيين نمط البحث للتلقائي الشامل بعد انتهاء العملية
        context.user_data['search_type'] = 'multi'
    except Exception as e:
        logger.error(f"Search direct error: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء معالجة البحث، حاول مجدداً لاحقاً.")

# 8. بدء التشغيل وإعداد البوت والـ Polling النظيف المتوافق مع ريندر
@app.on_event("startup")
async def startup_event():
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        # ربط جميع المعالجات والأوامر والأزرار التفاعلية بالملي
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

        await application.initialize()
        await application.start()

        # إعداد قائمة الأوامر بداخل زر المنيو بالتليجرام رسميًا
        await application.bot.set_my_commands([
            BotCommand("start", "🚀 تشغيل البوت والتحكم الرئيسي"),
            BotCommand("help", "🔍 شرح طريقة استخدام البوت")
        ])

        # تشغيل التحديثات وإلغاء أي طلبات معلقة قديمة لتجنب الـ Conflict نهائياً
        import asyncio
        asyncio.create_task(application.updater.start_polling(drop_pending_updates=True))
        logger.info("🔥 النسخة الكاملة والمستقرة 100% تعمل الآن بكفاءة وبدون أي نقص!")

    except Exception as e:
        logger.error(f"Startup crash: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
