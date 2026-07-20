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

# 2. الإعدادات والرموز الأساسية
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or os.environ.get("API_KEY")
ADMIN_ID = 1436656132

USER_FAVORITES = {}

# قائمة التصنيفات الأساسية
GENRES = {
    "action": {"id": 28, "name": "💥 أكشن"},
    "horror": {"id": 27, "name": "👻 رعب"},
    "comedy": {"id": 35, "name": "🍿 كوميدي"},
    "drama": {"id": 18, "name": "🎭 دراما"},
    "scifi": {"id": 878, "name": "🛸 خيال علمي"}
}

# قاموس ترجمة جميع تصنيفات TMDB للعربية
GENRE_MAP = {
    28: "أكشن 💥", 12: "مغامرة 🏹", 16: "أنيميشن 🎨", 35: "كوميديا 🍿", 80: "جريمة 🔍",
    99: "وثائقي 📹", 18: "دراما 🎭", 10751: "عائلي 👨‍👩‍👧", 14: "فانتازيا 🧙‍♂️", 36: "تاريخ 📜",
    27: "رعب 👻", 10402: "موسيقى 🎵", 9648: "غموض 🕵️‍♂️", 10749: "رومانسي 💖", 878: "خيال علمي 🛸",
    10770: "فيلم تلفزيوني 📺", 53: "إثارة ⚡", 10752: "حرب ⚔️", 37: "غرب أمريكي 🤠"
}

app = FastAPI()

@app.get("/")
@app.head("/")
def home():
    return "Bot is alive and running!"

def extract_genre_names(genre_ids, actual_media_type):
    if genre_ids:
        names = [GENRE_MAP.get(gid) for gid in genre_ids if gid in GENRE_MAP]
        if names:
            return " | ".join(names)
    return "فيلم 🎬" if actual_media_type == "movie" else "مسلسل 📺"

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

# مولدات روابط المشاهدة (الأساسي والبديلة)
def generate_watch_url(media_type, media_id):
    return f"https://vidsrc.me/embed/movie?tmdb={media_id}" if media_type == "movie" else f"https://vidsrc.me/embed/tv?tmdb={media_id}"

def generate_watch_url_alt1(media_type, media_id):
    return f"https://vidsrc.to/embed/movie/{media_id}" if media_type == "movie" else f"https://vidsrc.to/embed/tv/{media_id}"

def generate_watch_url_alt2(media_type, media_id):
    return f"https://embed.su/embed/movie/{media_id}" if media_type == "movie" else f"https://embed.su/embed/tv/{media_id}"

# 🌟 دالة إرسال بطاقة عمل فردية
async def send_single_card(context, chat_id, item, nav_buttons=None):
    try:
        media_id = item.get("id")
        actual_media_type = "movie" if ("title" in item or item.get("media_type") == "movie") else "tv"

        title = item.get("title") or item.get("name") or "عمل غير معروف"
        rating = item.get("vote_average", 0.0)
        poster_path = item.get("poster_path")

        genre_ids = item.get("genre_ids", [])
        genres_text = extract_genre_names(genre_ids, actual_media_type)

        overview = item.get("overview") or "لا يوجد وصف متوفر حالياً باللغة العربية لهذا العمل السينمائي."
        if len(overview) > 350:
            overview = overview[:350] + "..."

        year = (item.get("release_date") or item.get("first_air_date") or "----")[:4]

        result_text = (
            f"🎬 **الاسم:** {title} ({year})\n"
            f"🏷️ **النوع:** {genres_text}\n"
            f"⭐ **التقييم:** {rating}/10\n\n"
            f"📝 **قصة العمل:**\n{overview}\n\n"
            f"💡 _تنويه للمشاهدة:_ يفضل فتح الروابط عبر متصفح يدعم حظر الإعلانات مثل **Brave**."
        )

        trailer_url = get_trailer_url(actual_media_type, media_id)

        url_main = generate_watch_url(actual_media_type, media_id)
        url_alt1 = generate_watch_url_alt1(actual_media_type, media_id)
        url_alt2 = generate_watch_url_alt2(actual_media_type, media_id)

        keyboard = [
            [InlineKeyboardButton("🍿 مشاهدة العمل (سيرفر أساسي)", url=url_main)],
            [
                InlineKeyboardButton("💿 سيرفر بديل 1", url=url_alt1),
                InlineKeyboardButton("📀 سيرفر بديل 2", url=url_alt2)
            ]
        ]

        if trailer_url:
            keyboard.append([InlineKeyboardButton("🎬 مشاهدة الإعلان (التريلر)", url=trailer_url)])

        # إضافة أزرار التنقل إن وجدت
        if nav_buttons:
            keyboard.append(nav_buttons)

        keyboard.append([
            InlineKeyboardButton("❤️ للمفضلة", callback_data=f"add_fav_{media_id}"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        if poster_path:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=f"https://image.tmdb.org/t/p/w500{poster_path}",
                caption=result_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=result_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )

    except Exception as e:
        logger.error(f"Error in send_single_card: {e}")

# 🌟 دالة إرسال دفعة مكونة من 3 أفلام للتصنيفات
async def send_genre_3_batch(context, chat_id, genre_key, page=1, batch_idx=0):
    genre_id = GENRES[genre_key]["id"]
    url = (
        f"https://api.themoviedb.org/3/discover/movie"
        f"?api_key={TMDB_API_KEY}"
        f"&language=ar-SA"
        f"&sort_by=popularity.desc"
        f"&with_genres={genre_id}"
        f"&page={page}"
    )

    try:
        res = requests.get(url, timeout=5).json()
        movies = res.get("results", [])

        if not movies:
            await context.bot.send_message(chat_id=chat_id, text="❌ لا توجد نتائج إضافية.")
            return

        start_i = batch_idx * 3
        batch_movies = movies[start_i : start_i + 3]

        # إذا كانت الدفعة فارغة في هذه الصفحة، ننتقل للصفحة التالية
        if not batch_movies:
            page += 1
            batch_idx = 0
            url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=ar-SA&sort_by=popularity.desc&with_genres={genre_id}&page={page}"
            res = requests.get(url, timeout=5).json()
            movies = res.get("results", [])
            start_i = 0
            batch_movies = movies[:3]

        total_batches_in_page = (len(movies) + 2) // 3

        for idx, movie in enumerate(batch_movies):
            is_last = (idx == len(batch_movies) - 1)
            nav_buttons = None

            if is_last:
                nav_buttons = []
                # زر السابق
                if batch_idx > 0 or page > 1:
                    prev_b = batch_idx - 1 if batch_idx > 0 else total_batches_in_page - 1
                    prev_p = page if batch_idx > 0 else page - 1
                    nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"gbatch_{genre_key}_{prev_p}_{prev_b}"))

                # زر التالي
                next_b = batch_idx + 1
                next_p = page
                if next_b >= total_batches_in_page:
                    next_b = 0
                    next_p = page + 1
                nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=f"gbatch_{genre_key}_{next_p}_{next_b}"))

            await send_single_card(context, chat_id, movie, nav_buttons=nav_buttons)

    except Exception as e:
        logger.error(f"Error fetching 3 genre movies: {e}")
        await context.bot.send_message(chat_id=chat_id, text="⚠️ حدث خطأ أثناء جلب المقترحات.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🎬 **مرحباً بك في بوت فِلْمَه!**\n\n"
        "بوابتك الذكية لاستكشاف عالم السينما ومشاهدة الأفلام والمسلسلات 🍿\n\n"
        "💡 **اضغط على أي زر بالأسفل لتحديد نوع البحث، أو اكتب اسم العمل الذي تريده مباشرة!**"
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

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=reply_markup)

    elif update.callback_query:
        try:
            await update.callback_query.message.delete()
        except:
            pass

        await update.callback_query.message.reply_text(welcome, parse_mode="Markdown", reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🍿 **دليل استخدام بوت فِلْمَه:**\n\n"
        "🔹 **البحث المباشر:** أرسل اسم أي فيلم أو مسلسل في المحادثة مباشرة.\n"
        "🔹 **المشاهدة:** اختر السيرفر الأساسي أو السيرفرات البديلة.\n"
        "💡 _تنويه للمشاهدة:_ يفضل فتح روابط المشاهدة عبر متصفح **Brave** لحظر الإعلانات.\n"
        "🔹 **المفضلة:** اضغط '❤️ للمفضلة' لحفظ عملك والرجوع له لاحقاً.\n\n"
        "💬 للعودة للبداية أرسل: /start"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    data = query.data

    if data == "search_movie":
        context.user_data['search_type'] = 'movie'
        await query.message.reply_text("📥 أرسل لي اسم **الفيلم** الذي تبحث عنه:")

    elif data == "search_tv":
        context.user_data['search_type'] = 'tv'
        await query.message.reply_text("📥 أرسل لي اسم **المسلسل** الذي تبحث عنه:")

    elif data == "search_general":
        context.user_data['search_type'] = 'multi'
        await query.message.reply_text("📥 اكتب كلمة البحث العامة وسأفتش لك في الأفلام والمسلسلات معاً:")

    elif data == "show_genres":
        genre_text = (
            "🎭 **اختر تصنيفك المفضّل الليلة:**\n\n"
            "سأجلب لك 3 أفلام مقترحة بناءً على اختيارك ببطاقات كاملة مع إمكانية التصفح!"
        )

        keyboard = []
        genre_list = list(GENRES.items())

        for i in range(0, len(genre_list), 2):
            row = [InlineKeyboardButton(genre_list[i][1]["name"], callback_data=f"genre_fetch_{genre_list[i][0]}")]
            if i + 1 < len(genre_list):
                row.append(InlineKeyboardButton(genre_list[i + 1][1]["name"], callback_data=f"genre_fetch_{genre_list[i + 1][0]}"))
            keyboard.append(row)

        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")])

        try:
            await query.message.delete()
        except:
            pass

        await context.bot.send_message(
            chat_id=chat_id,
            text=genre_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # عند اختيار تصنيف: إرسال 3 أفلام فوراً!
    elif data.startswith("genre_fetch_"):
        genre_key = data.split("_")[2]
        try:
            await query.message.delete()
        except:
            pass
        await send_genre_3_batch(context, chat_id, genre_key, page=1, batch_idx=0)

    # عند الضغط على أزرار التنقل (التالي / السابق) داخل التصنيف: جلب 3 أفلام جديدة!
    elif data.startswith("gbatch_"):
        parts = data.split("_")
        genre_key = parts[1]
        page = int(parts[2])
        batch_idx = int(parts[3])

        try:
            await query.message.delete()
        except:
            pass

        await send_genre_3_batch(context, chat_id, genre_key, page=page, batch_idx=batch_idx)

    elif data == "top_rated":
        url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=ar-SA&page=1"

        try:
            response = requests.get(url, timeout=5).json()
            movies = response.get("results", [])

            if not movies:
                await query.message.reply_text("❌ لم أتمكن من جلب الأفلام حالياً.")
                return

            try:
                await query.message.delete()
            except:
                pass

            for movie in movies[:3]:
                await send_single_card(context, chat_id, movie)

        except Exception as e:
            logger.error(f"Error top rated: {e}")

    elif data == "random_movie":
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=ar-SA&sort_by=popularity.desc&page={random.randint(1, 5)}"

        try:
            res = requests.get(url, timeout=5).json()
            results = res.get("results", [])

            if results:
                movie = random.choice(results)
                await send_single_card(context, chat_id, movie)

        except Exception as e:
            logger.error(f"Error random movie: {e}")

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
                await context.bot.send_message(chat_id=chat_id, text=f"✅ تم إضافة **{title}** إلى مفضلتك! ❤️", parse_mode="Markdown")
            else:
                await context.bot.send_message(chat_id=chat_id, text=f"ℹ️ **{title}** موجود بالفعل في مفضلتك.", parse_mode="Markdown")
        except:
            pass

    elif data == "show_favorites":
        favs = USER_FAVORITES.get(user_id, [])

        if not favs:
            fav_text = "❤️ **قائمتك المفضلة فارغة حالياً.**\nابحث عن أعمال وأضفها عبر زر الحفظ!"
        else:
            fav_text = "⭐ **قائمتك المفضلة في فِلْمَه:**\n\n" + "\n".join([f"🍿 - {item}" for item in favs])

        await context.bot.send_message(
            chat_id=chat_id,
            text=fav_text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]])
        )

    elif data == "main_menu":
        try:
            await query.message.delete()
        except:
            pass

        await start(update, context)

# 6. دالة استقبال البحث
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_query = update.message.text
    search_type = context.user_data.get('search_type', 'multi')
    chat_id = update.message.chat_id

    await update.message.reply_text(f"🔍 جاري البحث عن: *{search_query}* في سيرفرات فِلْمَه...", parse_mode="Markdown")

    url = (
        f"https://api.themoviedb.org/3/search/{search_type}"
        f"?api_key={TMDB_API_KEY}"
        f"&query={search_query}"
        f"&language=ar"
        f"&page=1"
    )

    try:
        response = requests.get(url, timeout=5).json()
        results = response.get("results", [])

        if not filter(None, results):
            await update.message.reply_text("❌ لم أتمكن من العثور على نتائج، تأكد من صحة الاسم.")
            return

        # عرض أول فيلم من نتيجة البحث
        await send_single_card(context, chat_id, results[0])
        context.user_data['search_type'] = 'multi'

    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء الاتصال بالخادم الافتراضي.")

# 7. تشغيل البوت بحل مضاد لخطأ Conflict في Render
@app.on_event("startup")
async def startup_event():
    try:
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

        await application.initialize()
        await application.start()

        await application.bot.set_my_commands([
            BotCommand("start", "🚀 تشغيل البوت والتحكم الرئيسي"),
            BotCommand("help", "🔍 شرح طريقة استخدام البوت")
        ])

        # إلغاء أي Webhook قديم + انتظار 4 ثوانٍ لإغلاق الحاوية السابقة في Render
        await application.bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(4)

        asyncio.create_task(application.updater.start_polling(drop_pending_updates=True))
        logger.info("تم تفعيل الكود بنجاح مع خاصية الـ 3 أفلام المقترحة!")

    except Exception as e:
        logger.error(f"Startup error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
