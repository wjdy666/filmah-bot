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

def build_nav_callback(nav_type, nav_key, page, index):
    key_str = nav_key if nav_key else "x"
    return f"nav_{nav_type[:1]}_{key_str}_{page}_{index}"

# 🌟 دالة موحدة ومتطورة لإرسال بطاقات الأعمال مع السيرفرات وأزرار التنقل
async def send_media_card(
    context: ContextTypes.DEFAULT_TYPE, 
    chat_id: int, 
    item: dict, 
    nav_type: str = None, # 'genre', 'top', 'search'
    nav_key: str = None, 
    page: int = 1, 
    index: int = 0,
    total_in_page: int = 20
):
    try:
        media_id = item.get("id")
        actual_media_type = "movie" if ("title" in item or item.get("media_type") == "movie") else "tv"

        title = item.get("title") or item.get("name") or "عمل غير معروف"
        rating = item.get("vote_average", 0.0)
        poster_path = item.get("poster_path")

        genre_ids = item.get("genre_ids", [])
        genres_text = extract_genre_names(genre_ids, actual_media_type)

        overview = item.get("overview") or "لا يوجد وصف متوفر حالياً باللغة العربية لهذا العمل السينمائي."
        if len(overview) > 400:
            overview = overview[:400] + "..."

        year = (item.get("release_date") or item.get("first_air_date") or "----")[:4]

        result_text = (
            f"🎬 **الاسم:** {title} ({year})\n"
            f"🏷️ **النوع:** {genres_text}\n"
            f"⭐ **التقييم:** {rating}/10\n\n"
            f"📝 **قصة العمل:**\n{overview}\n\n"
            f"💡 _تنويه للمشاهدة:_ لتجنب الإعلانات المنبثقة المزعجة، يفضل فتح الروابط عبر متصفح يدعم حظر الإعلانات مثل **Brave**."
        )

        trailer_url = get_trailer_url(actual_media_type, media_id)

        url_main = generate_watch_url(actual_media_type, media_id)
        url_alt1 = generate_watch_url_alt1(actual_media_type, media_id)
        url_alt2 = generate_watch_url_alt2(actual_media_type, media_id)

        # 1. أزرار المشاهدة والسيرفرات البديلة
        keyboard = [
            [InlineKeyboardButton("🍿 مشاهدة العمل (سيرفر أساسي)", url=url_main)],
            [
                InlineKeyboardButton("💿 سيرفر بديل 1", url=url_alt1),
                InlineKeyboardButton("📀 سيرفر بديل 2", url=url_alt2)
            ]
        ]

        # 2. زر التريلر
        if trailer_url:
            keyboard.append([InlineKeyboardButton("🎬 مشاهدة الإعلان (التريلر)", url=trailer_url)])

        # 3. أزرار التنقل (السابق / التالي)
        if nav_type:
            nav_buttons = []
            
            # زر السابق
            if index > 0 or page > 1:
                prev_index = index - 1 if index > 0 else 19
                prev_page = page if index > 0 else page - 1
                cb_prev = build_nav_callback(nav_type, nav_key, prev_page, prev_index)
                nav_buttons.append(InlineKeyboardButton("⬅️ السابق", callback_data=cb_prev))

            # زر التالي
            if index < total_in_page - 1:
                next_index = index + 1
                next_page = page
                cb_next = build_nav_callback(nav_type, nav_key, next_page, next_index)
                nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=cb_next))
            elif total_in_page == 20: # احتمال وجود صفحات إضافية
                next_index = 0
                next_page = page + 1
                cb_next = build_nav_callback(nav_type, nav_key, next_page, next_index)
                nav_buttons.append(InlineKeyboardButton("التالي ➡️", callback_data=cb_next))

            if nav_buttons:
                keyboard.append(nav_buttons)

        # 4. أزرار التحكم الرئيسية
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

    except Exception as card_error:
        logger.error(f"Critical error inside send_media_card: {card_error}")

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
        "🔹 **المشاهدة:** سيظهر لك زر '🍿 مشاهدة العمل الآن' بالإضافة لسيرفرات بديلة.\n"
        "💡 _تنويه للمشاهدة:_ لتجربة خالية من الإعلانات المنبثقة المزعجة، يفضل فتح روابط المشاهدة عبر متصفح يدعم حظر الإعلانات مثل **Brave**.\n"
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
        await query.message.reply_text("📥 أرسل لي اسم **الفيلم** الذي تبحث عنه باللغة العربية أو الإنجليزية:")

    elif data == "search_tv":
        context.user_data['search_type'] = 'tv'
        await query.message.reply_text("📥 أرسل لي اسم **المسلسل** الذي تبحث عنه:")

    elif data == "search_general":
        context.user_data['search_type'] = 'multi'
        await query.message.reply_text("📥 اكتب كلمة البحث العامة وسأفتش لك في الأفلام والمسلسلات معاً:")

    elif data == "show_genres":
        genre_text = (
            "🎭 **اختر تصنيفك المفضّل الليلة:**\n\n"
            "سأجلب لك باقة من أفضل الأفلام العالمية بناءً على اختيارك ببطاقات كاملة!"
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

    elif data.startswith("genre_fetch_"):
        genre_key = data.split("_")[2]
        genre_id = GENRES[genre_key]["id"]

        url = (
            f"https://api.themoviedb.org/3/discover/movie"
            f"?api_key={TMDB_API_KEY}"
            f"&language=ar-SA"
            f"&sort_by=popularity.desc"
            f"&with_genres={genre_id}"
            f"&page=1"
        )

        try:
            response = requests.get(url, timeout=5).json()
            movies = response.get("results", [])

            if not movies:
                await query.message.reply_text("❌ لم أتمكن من العثور على أعمال في هذا التصنيف حالياً.")
                return

            try:
                await query.message.delete()
            except:
                pass

            await send_media_card(context, chat_id, movies[0], nav_type="genre", nav_key=genre_key, page=1, index=0, total_in_page=len(movies))

        except Exception as e:
            logger.error(f"Error fetching genre films: {e}")
            await context.bot.send_message(chat_id=chat_id, text="⚠️ خطأ في الاتصال بالخادم، حاول مجدداً.")

    # معالجة الضغط على أزرار التنقل (في التصنيفات، أفضل التقييمات، أو البحث)
    elif data.startswith("nav_"):
        parts = data.split("_")
        kind = parts[1] # 'g', 't', 's'
        key = parts[2]  # genre_key or 'x'
        page = int(parts[3])
        index = int(parts[4])

        try:
            await query.message.delete()
        except:
            pass

        if kind == 'g':
            genre_id = GENRES[key]["id"]
            url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=ar-SA&sort_by=popularity.desc&with_genres={genre_id}&page={page}"
            res = requests.get(url, timeout=5).json()
            results = res.get("results", [])
            if results and index < len(results):
                await send_media_card(context, chat_id, results[index], nav_type="genre", nav_key=key, page=page, index=index, total_in_page=len(results))

        elif kind == 't':
            url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=ar-SA&page={page}"
            res = requests.get(url, timeout=5).json()
            results = res.get("results", [])
            if results and index < len(results):
                await send_media_card(context, chat_id, results[index], nav_type="top", nav_key="x", page=page, index=index, total_in_page=len(results))

        elif kind == 's':
            search_query = context.user_data.get('last_search_query', '')
            search_type = context.user_data.get('search_type', 'multi')
            if search_query:
                url = f"https://api.themoviedb.org/3/search/{search_type}?api_key={TMDB_API_KEY}&query={search_query}&language=ar&page={page}"
                res = requests.get(url, timeout=5).json()
                results = res.get("results", [])
                if results and index < len(results):
                    await send_media_card(context, chat_id, results[index], nav_type="search", nav_key="x", page=page, index=index, total_in_page=len(results))

    elif data == "top_rated":
        url = (
            f"https://api.themoviedb.org/3/movie/top_rated"
            f"?api_key={TMDB_API_KEY}"
            f"&language=ar-SA"
            f"&page=1"
        )

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

            # عرض أول فيلم مع تفعيل أزرار التنقل والسيرفرات البديلة!
            await send_media_card(context, chat_id, movies[0], nav_type="top", nav_key="x", page=1, index=0, total_in_page=len(movies))

        except Exception as e:
            logger.error(f"Error top rated: {e}")
            await query.message.reply_text("⚠️ خطأ في الاتصال بخادم الأفلام.")

    elif data == "random_movie":
        url = (
            f"https://api.themoviedb.org/3/discover/movie"
            f"?api_key={TMDB_API_KEY}"
            f"&language=ar-SA"
            f"&sort_by=popularity.desc"
            f"&page={random.randint(1, 5)}"
        )

        try:
            res = requests.get(url, timeout=5).json()
            results = res.get("results", [])

            if results:
                movie = random.choice(results)
                await send_media_card(context, chat_id, movie)

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

# 6. دالة استقبال البحث مع تفعيل السيرفرات البديلة وأزرار التنقل بين نتائج البحث!
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_query = update.message.text
    search_type = context.user_data.get('search_type', 'multi')
    chat_id = update.message.chat_id

    # حفظ النص المبحوث عنه في ذاكرة الجلسة
    context.user_data['last_search_query'] = search_query

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

        # إرسال أول النتايج مع تفعيل أزرار التنقل والتنقل بين نتائج البحث وسيرفرات بديلة!
        await send_media_card(context, chat_id, results[0], nav_type="search", nav_key="x", page=1, index=0, total_in_page=len(results))
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
        logger.info("تم تفعيل الكود بنجاح مع كافة الأزرار والميزات في جميع الأقسام!")

    except Exception as e:
        logger.error(f"Startup error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
