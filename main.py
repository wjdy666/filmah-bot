import os
import logging
import asyncio
import random
import requests
from fastapi import FastAPI
import uvicorn
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# 1. إعدادات الـ Logs لمراقبة الأداء بدقة وثبات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# 2. الإعدادات والرموز الأساسية
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or os.environ.get("API_KEY")
ADMIN_ID = 1436656132

# ذاكرة مؤقتة للمفضلة تعتمد على معرف المستخدم
USER_FAVORITES = {}

# قاموس التصنيفات
GENRES = {
    "action": {"id": 28, "name": "💥 أكشن"},
    "horror": {"id": 27, "name": "👻 رعب"},
    "comedy": {"id": 35, "name": "🍿 كوميدي"},
    "drama": {"id": 18, "name": "🎭 دراما"},
    "scifi": {"id": 878, "name": "🛸 خيال علمي"}
}

# 3. إعداد FastAPI
app = FastAPI()

@app.get("/")
@app.head("/")
def home():
    return "Bot is alive and running!"

# ------------------------------
# دوال مساعدة
# ------------------------------

def get_trailer_url(media_type, media_id):
    url = (
        f"https://api.themoviedb.org/3/"
        f"{media_type}/{media_id}/videos"
        f"?api_key={TMDB_API_KEY}"
    )

    try:
        res = requests.get(url, timeout=5).json()

        for video in res.get("results", []):
            if (
                video.get("type") == "Trailer"
                and video.get("site") == "YouTube"
            ):
                return (
                    f"https://www.youtube.com/watch?"
                    f"v={video.get('key')}"
                )

    except Exception as e:
        logger.error(f"Trailer error: {e}")

    return None


def generate_watch_url(media_type, media_id):
    if media_type == "movie":
        return f"https://vidsrc.me/embed/movie?tmdb={media_id}"
    else:
        return f"https://vidsrc.me/embed/tv?tmdb={media_id}"


# ------------------------------
# إرسال بطاقة الفيلم
# ------------------------------

async def send_movie_card(context, chat_id, movie):
    try:
        movie_id = movie.get("id")

        actual_media_type = (
            "movie"
            if "title" in movie
            else "tv"
        )

        title = (
            movie.get("title")
            or movie.get("name")
            or "عمل غير معروف"
        )

        rating = movie.get("vote_average", 0.0)
        poster_path = movie.get("poster_path")

        overview = (
            movie.get("overview")
            or "لا يوجد وصف متوفر حالياً."
        )

        if len(overview) > 400:
            overview = overview[:400] + "..."

        year = (
            movie.get("release_date")
            or movie.get("first_air_date")
            or "----"
        )[:4]

        watch_url = generate_watch_url(
            actual_media_type,
            movie_id
        )

        trailer_url = get_trailer_url(
            actual_media_type,
            movie_id
        )

        result_text = (
            f"🎬 **الاسم:** {title} ({year})\n"
            f"🏷️ **النوع:** "
            f"{'فيلم 🎬' if actual_media_type == 'movie' else 'مسلسل 📺'}\n"
            f"⭐ **التقييم:** {rating}/10\n\n"
            f"📝 **القصة:**\n{overview}"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🍿 مشاهدة سريعة",
                    url=watch_url
                )
            ],
            [
                InlineKeyboardButton(
                    "🦁 Brave بدون إعلانات",
                    url=f"brave://open-url?url={watch_url}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🌐 فتح عبر Chrome",
                    url=watch_url.replace(
                        "https://",
                        "googlechrome://"
                    )
                )
            ]
        ]

        if trailer_url:
            keyboard.append([
                InlineKeyboardButton(
                    "🎬 التريلر",
                    url=trailer_url
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "❤️ للمفضلة",
                callback_data=f"add_fav_{movie_id}"
            ),
            InlineKeyboardButton(
                "🏠 الرئيسية",
                callback_data="main_menu"
            )
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
        logger.error(f"send_movie_card error: {e}")


# ------------------------------
# البحث مع الصفحات
# ------------------------------

async def fetch_and_show_results(
    context,
    chat_id,
    query,
    page
):
    url = (
        f"https://api.themoviedb.org/3/search/multi"
        f"?api_key={TMDB_API_KEY}"
        f"&query={query}"
        f"&language=ar"
        f"&page={page}"
    )

    try:
        res = requests.get(url, timeout=5).json()

        results = res.get("results", [])

        if not results:
            await context.bot.send_message(
                chat_id,
                "❌ لا توجد نتائج."
            )
            return

        await send_movie_card(
            context,
            chat_id,
            results[0]
        )

        keyboard = [[
            InlineKeyboardButton(
                "➡️ التالية",
                callback_data=f"page_{page + 1}"
            )
        ]]

        if page > 1:
            keyboard[0].insert(
                0,
                InlineKeyboardButton(
                    "⬅️ السابقة",
                    callback_data=f"page_{page - 1}"
                )
            )

        await context.bot.send_message(
            chat_id,
            f"📄 صفحة {page}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Pagination error: {e}")


# ------------------------------
# لوحة تحكم الأدمن
# ------------------------------

async def admin_panel(update, context):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "📊 الإحصائيات",
                callback_data="admin_stats"
            )
        ],
        [
            InlineKeyboardButton(
                "🔄 إعادة تشغيل",
                callback_data="admin_restart"
            )
        ]
    ]

    await update.effective_message.reply_text(
        "👑 لوحة تحكم المشرف:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ------------------------------
# رسالة البداية
# ------------------------------

async def start(update, context):
    welcome = (
        "🎬 **مرحباً بك في بوت فِلْمَه!**\n\n"
        "ابحث عن أي فيلم أو مسلسل بسهولة 🍿"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "🎬 بحث فيلم",
                callback_data="search_movie"
            ),
            InlineKeyboardButton(
                "📺 بحث مسلسل",
                callback_data="search_tv"
            )
        ],
        [
            InlineKeyboardButton(
                "🔍 بحث شامل",
                callback_data="search_general"
            ),
            InlineKeyboardButton(
                "🎭 التصنيفات",
                callback_data="show_genres"
            )
        ],
        [
            InlineKeyboardButton(
                "⭐ الأعلى تقييماً",
                callback_data="top_rated"
            )
        ],
        [
            InlineKeyboardButton(
                "🎲 فيلم عشوائي",
                callback_data="random_movie"
            ),
            InlineKeyboardButton(
                "❤️ المفضلة",
                callback_data="show_favorites"
            )
        ]
    ]

    if update.callback_query:
        await update.callback_query.message.reply_text(
            welcome,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    else:
        await update.message.reply_text(
            welcome,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ------------------------------
# المساعدة
# ------------------------------

async def help_command(update, context):
    text = (
        "🍿 أرسل اسم أي فيلم أو مسلسل مباشرة.\n"
        "وسيتم جلب روابط المشاهدة والتريلر تلقائياً."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ------------------------------
# الأزرار
# ------------------------------

async def button_handler(update, context):
    query = update.callback_query

    await query.answer()

    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if data == "main_menu":
        await start(update, context)

    elif data.startswith("page_"):
        page = int(data.split("_")[1])

        await fetch_and_show_results(
            context,
            chat_id,
            context.user_data.get(
                'search_query',
                ''
            ),
            page
        )

    elif data == "admin_stats":
        await query.message.reply_text(
            f"📊 عدد مستخدمي المفضلة: "
            f"{len(USER_FAVORITES)}"
        )

    elif data == "admin_restart":
        os._exit(0)

    elif data == "search_movie":
        context.user_data['search_type'] = 'movie'

        await query.edit_message_text(
            "📥 أرسل اسم الفيلم:"
        )

    elif data == "search_tv":
        context.user_data['search_type'] = 'tv'

        await query.edit_message_text(
            "📥 أرسل اسم المسلسل:"
        )

    elif data == "search_general":
        context.user_data['search_type'] = 'multi'

        await query.edit_message_text(
            "📥 أرسل اسم العمل:"
        )

    elif data == "show_genres":

        keyboard = []

        genre_list = list(GENRES.items())

        for i in range(0, len(genre_list), 2):

            row = [
                InlineKeyboardButton(
                    genre_list[i][1]["name"],
                    callback_data=(
                        f"genre_fetch_"
                        f"{genre_list[i][0]}"
                    )
                )
            ]

            if i + 1 < len(genre_list):
                row.append(
                    InlineKeyboardButton(
                        genre_list[i + 1][1]["name"],
                        callback_data=(
                            f"genre_fetch_"
                            f"{genre_list[i + 1][0]}"
                        )
                    )
                )

            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton(
                "🏠 الرئيسية",
                callback_data="main_menu"
            )
        ])

        await query.edit_message_text(
            "🎭 اختر تصنيف:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("genre_fetch_"):

        genre_key = data.split("_")[2]

        genre_id = GENRES[genre_key]["id"]
        genre_name = GENRES[genre_key]["name"]

        status_msg = await query.message.reply_text(
            f"🔄 جاري جلب أفلام {genre_name}..."
        )

        url = (
            f"https://api.themoviedb.org/3/discover/movie"
            f"?api_key={TMDB_API_KEY}"
            f"&language=ar-SA"
            f"&sort_by=popularity.desc"
            f"&with_genres={genre_id}"
            f"&page=1"
        )

        try:
            response = requests.get(
                url,
                timeout=5
            )

            data_res = response.json()

            movies = data_res.get(
                "results",
                []
            )

            try:
                await status_msg.delete()
            except:
                pass

            if not movies:
                await query.message.reply_text(
                    "❌ لا توجد نتائج حالياً."
                )
                return

            for movie in movies[:3]:
                await send_movie_card(
                    context,
                    chat_id,
                    movie
                )

        except Exception as e:
            logger.error(
                f"Genre fetch error: {e}"
            )

    elif data == "top_rated":

        status_msg = await query.message.reply_text(
            "🔄 جاري جلب أعلى الأفلام..."
        )

        url = (
            f"https://api.themoviedb.org/3/movie/top_rated"
            f"?api_key={TMDB_API_KEY}"
            f"&language=ar-SA"
            f"&page=1"
        )

        try:
            response = requests.get(
                url,
                timeout=5
            )

            data_res = response.json()

            movies = data_res.get(
                "results",
                []
            )

            try:
                await status_msg.delete()
            except:
                pass

            if not movies:
                await query.message.reply_text(
                    "❌ لا توجد نتائج."
                )
                return

            for movie in movies[:3]:
                await send_movie_card(
                    context,
                    chat_id,
                    movie
                )

        except Exception as e:
            logger.error(f"Top rated error: {e}")

    elif data == "random_movie":

        url = (
            f"https://api.themoviedb.org/3/discover/movie"
            f"?api_key={TMDB_API_KEY}"
            f"&language=ar-SA"
            f"&sort_by=popularity.desc"
            f"&page={random.randint(1, 5)}"
        )

        try:
            res = requests.get(
                url,
                timeout=5
            ).json()

            results = res.get("results", [])

            if results:
                movie = random.choice(results)

                await send_movie_card(
                    context,
                    chat_id,
                    movie
                )

        except Exception as e:
            logger.error(f"Random error: {e}")

    elif data.startswith("add_fav_"):

        media_id = data.split("_")[2]

        url = (
            f"https://api.themoviedb.org/3/movie/"
            f"{media_id}"
            f"?api_key={TMDB_API_KEY}"
            f"&language=ar"
        )

        try:
            res = requests.get(
                url,
                timeout=5
            ).json()

            title = (
                res.get("title")
                or res.get("name")
                or "عمل غير معروف"
            )

            if user_id not in USER_FAVORITES:
                USER_FAVORITES[user_id] = []

            if title not in USER_FAVORITES[user_id]:

                USER_FAVORITES[user_id].append(
                    title
                )

                await query.message.reply_text(
                    f"✅ تمت إضافة "
                    f"**{title}** للمفضلة ❤️",
                    parse_mode="Markdown"
                )

            else:
                await query.message.reply_text(
                    f"ℹ️ العمل موجود مسبقاً.",
                    parse_mode="Markdown"
                )

        except Exception as e:
            logger.error(f"Fav error: {e}")

    elif data == "show_favorites":

        favs = USER_FAVORITES.get(
            user_id,
            []
        )

        if not favs:
            text = (
                "❤️ لا توجد أعمال محفوظة."
            )

        else:
            text = (
                "⭐ قائمتك المفضلة:\n\n"
                + "\n".join(
                    [f"🍿 {x}" for x in favs]
                )
            )

        await query.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🏠 الرئيسية",
                        callback_data="main_menu"
                    )
                ]
            ])
        )


# ------------------------------
# البحث
# ------------------------------

async def handle_search(update, context):

    q = update.message.text

    context.user_data['search_query'] = q

    search_type = context.user_data.get(
        'search_type',
        'multi'
    )

    chat_id = update.message.chat_id

    await update.message.reply_text(
        f"🔍 جاري البحث عن: *{q}*",
        parse_mode="Markdown"
    )

    url = (
        f"https://api.themoviedb.org/3/search/"
        f"{search_type}"
        f"?api_key={TMDB_API_KEY}"
        f"&query={q}"
        f"&language=ar"
        f"&page=1"
    )

    try:
        response = requests.get(
            url,
            timeout=5
        ).json()

        results = response.get(
            "results",
            []
        )

        if not results:
            await update.message.reply_text(
                "❌ لا توجد نتائج."
            )
            return

        await send_movie_card(
            context,
            chat_id,
            results[0]
        )

        keyboard = [[
            InlineKeyboardButton(
                "➡️ التالية",
                callback_data="page_2"
            )
        ]]

        await update.message.reply_text(
            "📄 التنقل بين الصفحات:",
            reply_markup=InlineKeyboardMarkup(
                keyboard
            )
        )

        context.user_data['search_type'] = 'multi'

    except Exception as e:
        logger.error(f"Search error: {e}")

        await update.message.reply_text(
            "⚠️ حدث خطأ أثناء البحث."
        )


# ------------------------------
# تشغيل البوت
# ------------------------------

@app.on_event("startup")
async def startup_event():

    try:
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .build()
        )

        application.add_handler(
            CommandHandler("start", start)
        )

        application.add_handler(
            CommandHandler("help", help_command)
        )

        application.add_handler(
            CommandHandler("admin", admin_panel)
        )

        application.add_handler(
            CallbackQueryHandler(button_handler)
        )

        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                handle_search
            )
        )

        await application.initialize()

        await application.start()

        await application.bot.set_my_commands([
            BotCommand(
                "start",
                "🚀 تشغيل البوت"
            ),
            BotCommand(
                "help",
                "📖 شرح الاستخدام"
            ),
            BotCommand(
                "admin",
                "👑 لوحة الأدمن"
            )
        ])

        asyncio.create_task(
            application.updater.start_polling()
        )

        logger.info(
            "Bot started successfully!"
        )

    except Exception as e:
        logger.error(f"Startup error: {e}")


# ------------------------------
# التشغيل النهائي
# ------------------------------

if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(
            os.environ.get("PORT", 8000)
        )
    )
