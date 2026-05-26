# bot_app.py
import os
import logging
import asyncio
import random
import requests
import urllib.parse
from fastapi import FastAPI
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY") or os.environ.get("API_KEY")
ADMIN_ID = 1436656132
PAGE_SIZE = 10

# In-memory favorites
USER_FAVORITES = {}

# Genres map (you can extend)
GENRES = {
    "action": {"id": 28, "name": "💥 أكشن"},
    "horror": {"id": 27, "name": "👻 رعب"},
    "comedy": {"id": 35, "name": "🍿 كوميدي"},
    "drama": {"id": 18, "name": "🎭 دراما"},
    "scifi": {"id": 878, "name": "🛸 خيال علمي"}
}

# FastAPI health endpoint
app = FastAPI()

@app.get("/")
@app.head("/")
def home():
    return "Bot is alive and running!"

# Helper: get trailer
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

# Helper: watch url
def generate_watch_url(media_type, media_id):
    if media_type == "movie":
        return f"https://vidsrc.me/embed/movie?tmdb={media_id}"
    else:
        return f"https://vidsrc.me/embed/tv?tmdb={media_id}"

# Send movie/tv card (safe)
async def send_movie_card(context, chat_id, movie):
    try:
        movie_id = movie.get("id")
        actual_media_type = "movie" if "title" in movie else "tv"

        title = movie.get("title") or movie.get("name") or "عمل غير معروف"
        rating = movie.get("vote_average", 0.0)
        poster_path = movie.get("poster_path")

        overview = movie.get("overview") or "لا يوجد وصف متوفر حالياً."
        if len(overview) > 400:
            overview = overview[:400] + "..."

        year = (movie.get("release_date") or movie.get("first_air_date") or "----")[:4]

        result_text = (
            f"🎬 **الاسم:** {title} ({year})\n"
            f"🏷️ **النوع:** {'فيلم 🎬' if actual_media_type == 'movie' else 'مسلسل 📺'}\n"
            f"⭐ **التقييم:** {rating}/10\n\n"
            f"📝 **قصة العمل:**\n{overview}\n\n"
            f"💡 _تنويه للمشاهدة:_ لتجنب الإعلانات المنبثقة المزعجة، يفضل فتح الروابط عبر متصفح يدعم حظر الإعلانات مثل **Brave**."
        )

        trailer_url = None
        try:
            trailer_url = get_trailer_url(actual_media_type, movie_id)
        except:
            pass

        watch_url = generate_watch_url(actual_media_type, movie_id)

        keyboard = [
            [InlineKeyboardButton("🍿 مشاهدة العمل الآن", url=watch_url)]
        ]

        if trailer_url:
            keyboard.append([InlineKeyboardButton("🎬 مشاهدة الإعلان (التريلر)", url=trailer_url)])

        keyboard.append([
            InlineKeyboardButton("❤️ للمفضلة", callback_data=f"add_fav_{actual_media_type}_{movie_id}"),
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

    except Exception as card_error:
        logger.error(f"Critical error inside send_movie_card: {card_error}")

# Format list results into text
def format_results_list(results, media_type, page, total_results):
    lines = []
    start_index = (page - 1) * PAGE_SIZE + 1
    for idx, item in enumerate(results, start=start_index):
        title = item.get("title") or item.get("name") or "بدون عنوان"
        year = (item.get("release_date") or item.get("first_air_date") or "")[:4]
        lines.append(f"{idx}. {title} ({year})")
    shown = len(results)
    header = f"عرض {shown} من {total_results} نتيجة"
    body = "\n".join(lines) if lines else "لا توجد نتائج في هذه الصفحة."
    return header + "\n\n" + body

# Build pagination keyboard
def build_pagination_keyboard(query, media_type, page, total_results):
    total_pages = max(1, (total_results + PAGE_SIZE - 1) // PAGE_SIZE)
    kb = InlineKeyboardMarkup(row_width=5)
    # Toggle button
    toggle_label = "عرض مسلسلات" if media_type == "movie" else "عرض أفلام"
    # encode query safely
    enc_query = urllib.parse.quote_plus(query)
    kb.add(InlineKeyboardButton(toggle_label, callback_data=f"toggle|{enc_query}|{page}|{media_type}"))
    # Page buttons: show window of pages around current
    start = max(1, page - 2)
    end = min(total_pages, start + 4)
    buttons = []
    for p in range(start, end + 1):
        label = f"•{p}•" if p == page else str(p)
        buttons.append(InlineKeyboardButton(label, callback_data=f"page|{enc_query}|{media_type}|{p}"))
    kb.add(*buttons)
    # navigation shortcuts
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⏮️ أول", callback_data=f"page|{enc_query}|{media_type}|1"))
        nav_row.append(InlineKeyboardButton("◀️ سابق", callback_data=f"page|{enc_query}|{media_type}|{page-1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"page|{enc_query}|{media_type}|{page+1}"))
        nav_row.append(InlineKeyboardButton("آخر ⏭️", callback_data=f"page|{enc_query}|{media_type}|{total_pages}"))
    if nav_row:
        kb.add(*nav_row)
    kb.add(InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu"))
    return kb

# Start / welcome
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
        await update.message.reply_text(
            welcome,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    elif update.callback_query:
        try:
            await update.callback_query.message.delete()
        except:
            pass

        await update.callback_query.message.reply_text(
            welcome,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

# Help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🍿 **دليل استخدام بوت فِلْمَه:**\n\n"
        "🔹 **البحث المباشر:** أرسل اسم أي فيلم أو مسلسل في المحادثة مباشرة.\n"
        "🔹 **المشاهدة:** سيظهر لك زر '🍿 مشاهدة العمل الآن' يأخذك لسيرفر خارجي.\n"
        "🔹 **المفضلة:** اضغط '❤️ للمفضلة' لحفظ عملك والرجوع له لاحقاً.\n\n"
        "💬 للعودة للبداية أرسل: /start"
    )

    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.reply_text(help_text, parse_mode="Markdown")

# Callback handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
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

    elif data == "show_genres":
        genre_text = (
            "🎭 **اختر تصنيفك المفضّل الليلة:**\n\n"
            "سأجلب لك باقة من أفضل الأعمال بناءً على اختيارك ببطاقات كاملة!"
        )
        keyboard = []
        genre_list = list(GENRES.items())
        for i in range(0, len(genre_list), 2):
            row = [
                InlineKeyboardButton(
                    genre_list[i][1]["name"],
                    callback_data=f"genre_fetch_{genre_list[i][0]}"
                )
            ]
            if i + 1 < len(genre_list):
                row.append(
                    InlineKeyboardButton(
                        genre_list[i + 1][1]["name"],
                        callback_data=f"genre_fetch_{genre_list[i + 1][0]}"
                    )
                )
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 العودة للقائمة الرئيسية", callback_data="main_menu")])
        await query.edit_message_text(genre_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("genre_fetch_"):
        genre_key = data.split("_", 2)[2]
        genre_id = GENRES.get(genre_key, {}).get("id")
        genre_name = GENRES.get(genre_key, {}).get("name", genre_key)
        status_msg = await query.message.reply_text(f"🔄 جاري جلب أعمال {genre_name}...")
        url = (
            f"https://api.themoviedb.org/3/discover/movie"
            f"?api_key={TMDB_API_KEY}"
            f"&language=ar-SA"
            f"&sort_by=popularity.desc"
            f"&with_genres={genre_id}"
            f"&page=1"
        )
        try:
            response = requests.get(url, timeout=5)
            data_res = response.json()
            movies = data_res.get("results", [])
            try:
                await status_msg.delete()
            except:
                pass
            if not movies:
                await query.message.reply_text("❌ لم أتمكن من العثور على أعمال في هذا التصنيف حالياً.")
                return
            for movie in movies[:3]:
                await send_movie_card(context, chat_id, movie)
        except Exception as e:
            logger.error(f"Error fetching genre films: {e}")
            await query.message.reply_text("⚠️ خطأ في الاتصال بالخادم، حاول مجدداً.")

    elif data == "top_rated":
        status_msg = await query.message.reply_text("🔄 جاري جلب أعلى الأعمال تقييماً...")
        url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=ar-SA&page=1"
        try:
            response = requests.get(url, timeout=5).json()
            movies = response.get("results", [])
            try:
                await status_msg.delete()
            except:
                pass
            if not movies:
                await query.message.reply_text("❌ لم أتمكن من جلب الأعمال حالياً.")
                return
            for movie in movies[:3]:
                await send_movie_card(context, chat_id, movie)
        except Exception as e:
            logger.error(f"Error top rated: {e}")
            await query.message.reply_text("⚠️ خطأ في الاتصال بخادم الأفلام.")

    elif data == "random_movie":
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=ar-SA&sort_by=popularity.desc&page={random.randint(1, 5)}"
        try:
            res = requests.get(url, timeout=5).json()
            results = res.get("results", [])
            if results:
                movie = random.choice(results)
                await send_movie_card(context, chat_id, movie)
        except Exception as e:
            logger.error(f"Error random movie: {e}")

    elif data.startswith("add_fav_"):
        # format: add_fav_{media_type}_{id}
        parts = data.split("_")
        if len(parts) >= 3:
            media_type = parts[2]
            media_id = parts[3] if len(parts) > 3 else None
            try:
                url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={TMDB_API_KEY}&language=ar"
                res = requests.get(url, timeout=5).json()
                title = res.get("title") or res.get("name") or "عمل غير معروف"
                if user_id not in USER_FAVORITES:
                    USER_FAVORITES[user_id] = []
                if title not in USER_FAVORITES[user_id]:
                    USER_FAVORITES[user_id].append(title)
                    await query.message.reply_text(f"✅ تم إضافة **{title}** إلى مفضلتك! ❤️", parse_mode="Markdown")
                else:
                    await query.message.reply_text(f"ℹ️ **{title}** موجود بالفعل في مفضلتك.", parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Error add fav: {e}")

    elif data == "show_favorites":
        favs = USER_FAVORITES.get(user_id, [])
        if not favs:
            fav_text = "❤️ **قائمتك المفضلة فارغة حالياً.**\nابحث عن أعمال وأضفها عبر زر الحفظ!"
        else:
            fav_text = "⭐ **قائمتك المفضلة في فِلْمَه:**\n\n" + "\n".join([f"🍿 - {item}" for item in favs])
        await query.message.reply_text(fav_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]]))

    elif data == "main_menu":
        try:
            await query.message.delete()
        except:
            pass
        await start(update, context)

    # ===== Pagination and toggle handlers =====
    elif data.startswith("page|"):
        # data: page|{enc_query}|{media_type}|{p}
        try:
            _, enc_query, media_type, p = data.split("|", 3)
            query_text = urllib.parse.unquote_plus(enc_query)
            page = int(p)
        except Exception as e:
            logger.error(f"Invalid page callback data: {e}")
            await query.answer("خطأ في بيانات الصفحة.")
            return

        # choose endpoint
        endpoint = f"https://api.themoviedb.org/3/search/{media_type}"
        url = f"{endpoint}?api_key={TMDB_API_KEY}&query={urllib.parse.quote_plus(query_text)}&language=ar&page={page}"
        try:
            res = requests.get(url, timeout=5).json()
            total = res.get("total_results", 0)
            results = res.get("results", [])[:PAGE_SIZE]
            text = format_results_list(results, media_type, page, total)
            kb = build_pagination_keyboard(query_text, media_type, page, total)
            # try to edit the message (if original was text)
            try:
                await query.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
            except:
                # fallback: send new message
                await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
            await query.answer()
        except Exception as e:
            logger.error(f"Pagination search error: {e}")
            await query.answer("حدث خطأ أثناء جلب الصفحة.")

    elif data.startswith("toggle|"):
        # data: toggle|{enc_query}|{page}|{current_media}
        try:
            _, enc_query, p, current_media = data.split("|", 3)
            query_text = urllib.parse.unquote_plus(enc_query)
            page = int(p)
        except Exception as e:
            logger.error(f"Invalid toggle callback data: {e}")
            await query.answer("خطأ في بيانات التبديل.")
            return

        new_media = "tv" if current_media == "movie" else "movie"
        endpoint = f"https://api.themoviedb.org/3/search/{new_media}"
        url = f"{endpoint}?api_key={TMDB_API_KEY}&query={urllib.parse.quote_plus(query_text)}&language=ar&page={page}"
        try:
            res = requests.get(url, timeout=5).json()
            total = res.get("total_results", 0)
            results = res.get("results", [])[:PAGE_SIZE]
            text = format_results_list(results, new_media, page, total)
            kb = build_pagination_keyboard(query_text, new_media, page, total)
            try:
                await query.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
            except:
                await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
            await query.answer()
        except Exception as e:
            logger.error(f"Toggle search error: {e}")
            await query.answer("حدث خطأ أثناء تبديل النوع.")

# Handle text messages (search)
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_query = update.message.text.strip()
    search_type = context.user_data.get('search_type', 'multi')  # movie, tv, or multi
    chat_id = update.message.chat_id

    await update.message.reply_text(f"🔍 جاري البحث عن: *{search_query}* في سيرفرات فِلْمَه...", parse_mode="Markdown")

    # default to page 1
    page = 1
    # choose endpoint
    endpoint = f"https://api.themoviedb.org/3/search/{search_type}"
    url = f"{endpoint}?api_key={TMDB_API_KEY}&query={urllib.parse.quote_plus(search_query)}&language=ar&page={page}"

    try:
        response = requests.get(url, timeout=5).json()
        total = response.get("total_results", 0)
        results = response.get("results", [])[:PAGE_SIZE]

        if not results:
            await update.message.reply_text("❌ لم أتمكن من العثور على نتائج، تأكد من صحة الاسم.")
            context.user_data['search_type'] = 'multi'
            return

        # send a single message with list + pagination keyboard
        text = format_results_list(results, search_type, page, total)
        kb = build_pagination_keyboard(search_query, search_type, page, total)
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

        # reset search_type to default
        context.user_data['search_type'] = 'multi'

    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء الاتصال بالخادم الافتراضي.")

# Startup: register handlers and run polling
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

        # start polling in background
        asyncio.create_task(application.updater.start_polling())

        logger.info("تم تفعيل البوت مع دعم البحث الموسع والصفحات!")

    except Exception as e:
        logger.error(f"Startup error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
