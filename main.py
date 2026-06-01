import os
import logging
import asyncio
import random
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from pyrogram import Client

# 1. إعدادات الـ Logs لمراقبة الأداء بدقة وثبات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. الإعدادات والرموز الأساسية (تم دمج إعدادات الحساب المساعد)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7965754682:AAGGBGIUBG_-_ALb8R3624bpycP4iiH_Jdg")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "36214571cc6d6b8b0e78453a57cc49ae")
ADMIN_ID = 1436656132

# بيانات الـ Userbot لقش القنوات
API_ID = int(os.environ.get("API_ID", 37617537))
API_HASH = os.environ.get("API_HASH", "453a57cc49aed64b6ebbfd1eb11645da")
MOVIE_CHANNELS = ["wecimaR", "HI_VZ", "jdjdiso0", "runawayz1"]
SESSION_STRING = os.environ.get("STRING_SESSION", None)

# ذاكرة مؤقتة للمفضلة ولنتائج البحث الهجين
USER_FAVORITES = {}
USER_SEARCHES = {}

# قاموس لمعرفات تصنيفات الأفلام في TMDB
GENRES = {
    "action": {"id": 28, "name": "💥 أكشن"},
    "horror": {"id": 27, "name": "👻 رعب"},
    "comedy": {"id": 35, "name": "🍿 كوميدي"},
    "drama": {"id": 18, "name": "🎭 دراما"},
    "scifi": {"id": 878, "name": "🛸 خيال علمي"}
}

# 3. إعداد سيرفر الويب FastAPI للحفاظ على استقرار السيرفر من النوم
app = FastAPI()

@app.get("/")
@app.head("/")
def home():
    return "Filmh Hybrid Bot is alive and running!"

# إعداد كائن الحساب المساعد الذكي آمن الإقلاع
if SESSION_STRING:
    userbot = Client("filmh_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
else:
    userbot = Client("filmh_userbot", api_id=API_ID, api_hash=API_HASH, in_memory=True)

# فحص حالة اتصال الحساب المساعد
def user_bot_is_live():
    try: return userbot.is_connected
    except: return False

# دالة مساعدة رئيسية ومطورة لجلب رابط التريلر من TMDB بشكل آمن لمنع التعليق
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

# دالة مطورة وموحدة لتوليد روابط المشاهدة الخارجية الآمنة
def generate_watch_url(media_type, media_id):
    if media_type == "movie":
        return f"https://vidsrc.me/embed/movie?tmdb={media_id}"
    else:
        return f"https://vidsrc.me/embed/tv?tmdb={media_id}"

# محرك البحث الذكي داخل قنوات تليجرام السحابية عبر الـ Userbot
async def search_movies_in_channels(query_text):
    found_messages = []
    if not user_bot_is_live():
        return found_messages
    try:
        for channel in MOVIE_CHANNELS:
            try:
                async for message in userbot.search_messages(chat_id=channel, query=query_text, limit=3):
                    if message.video or message.document:
                        found_messages.append({
                            "channel": channel,
                            "msg_id": message.id,
                            "text": message.caption or "ملف سينمائي مباشر تليجرام"
                        })
            except Exception as ce:
                logger.error(f"Channel {channel} search error: {ce}")
    except Exception as e:
        logger.error(f"Global Userbot search error: {e}")
    return found_messages

# --- 🌟 الدالة الاحترافية المحمية تماماً من التعليق لإرسال بطاقات الأفلام الهجينة 🌟 ---
async def send_movie_card(context, chat_id, movie, tg_files=None):
    try:
        movie_id = movie.get("id")
        user_id = chat_id # في المحادثات المباشرة الـ chat_id هو الـ user_id
        actual_media_type = "movie" if "title" in movie else "tv"

        title = movie.get("title") or movie.get("name") or "عمل غير معروف"
        rating = movie.get("vote_average", 0.0)
        poster_path = movie.get("poster_path")

        overview = movie.get("overview") or "لا يوجد وصف متوفر حالياً باللغة العربية لهذا العمل السينمائي."
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

        keyboard = []
        
        # إذا وجد محرك البحث ملفات تليجرام مطابقة، يدمج زر التحميل المباشر أول سطر للتميز هندسياً
        if tg_files:
            if user_id not in USER_SEARCHES:
                USER_SEARCHES[user_id] = []
            USER_SEARCHES[user_id] = tg_files
            keyboard.append([InlineKeyboardButton("📥 مشاهدة وتحميل مباشر (داخل تليجرام)", callback_data="get_tg_file_0")])

        keyboard.append([InlineKeyboardButton("🍿 مشاهدة العمل الآن (سيرفر خارجي)", url=watch_url)])

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

    except Exception as card_error:
        logger.error(f"Critical error inside send_movie_card: {card_error}")

# 4. رسالة الترحيب الأصلية لبوت فِلْمَه
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
        try: await update.callback_query.message.delete()
        except: pass
        await update.callback_query.message.reply_text(welcome, parse_mode="Markdown", reply_markup=reply_markup)

# أمر المساعدة
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🍿 **دليل استخدام بوت فِلْمَه:**\n\n"
        "🔹 **البحث المباشر:** أرسل اسم أي فيلم أو مسلسل في المحادثة مباشرة.\n"
        "🔹 **المشاهدة:** سيظهر لك زر '🍿 مشاهدة العمل الآن' يأخذك لسيرفر خارجي يدعم الترجمة العربية.\n"
        "💡 _تنويه للمشاهدة:_ لتجربة خالية من الإعلانات المنبثقة المزعجة، يفضل فتح روابط المشاهدة عبر متصفح يدعم حظر الإعلانات مثل **Brave**.\n"
        "🔹 **المفضلة:** اضغط '❤️ للمفضلة' لحفظ عملك والرجوع له لاحقاً.\n\n"
        "💬 للعودة للبداية أرسل: /start"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# أمر الـ /login التفاعلي لتنشيط الـ Userbot مباشرة من تليجرام
async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الأمر مخصص لمالك البوت فقط.")
        return
    if user_bot_is_live():
        await update.message.reply_text("✅ الحساب المساعد متصل بالفعل وشغال كفاءة!")
        return
    context.user_data["login_step"] = "phone"
    await update.message.reply_text("📱 يرجى إرسال رقم هاتف الحساب المساعد مع رمز الدولة المباشر.\nمثال: `+966500000000`", parse_mode="Markdown")

# 5. دالة معالجة الضغط على الأزرار التفاعلية
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
        genre_text = "🎭 **اختر تصنيفك المفضّل الليلة:**\n\nسأجلب لك باقة من أفضل الأفلام العالمية بناءً على اختيارك ببطاقات كاملة!"
        keyboard = []
        genre_list = list(GENRES.items())
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
        status_msg = await query.message.reply_text(f"🔄 جاري جلب أفلام {genre_name}...")
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=ar-SA&sort_by=popularity.desc&with_genres={genre_id}&page=1"
        try:
            response = requests.get(url, timeout=5).json()
            movies = response.get("results", [])
            try: await status_msg.delete()
            except: pass
            if not movies:
                await query.message.reply_text("❌ لم أتمكن من العثور على أعمال في هذا التصنيف حالياً.")
                return
            for movie in movies[:3]:
                await send_movie_card(context, chat_id, movie)
        except Exception as e:
            logger.error(f"Error fetching genre films: {e}")
            await query.message.reply_text("⚠️ خطأ في الاتصال بالخادم، حاول مجدداً.")

    elif data == "top_rated":
        status_msg = await query.message.reply_text("🔄 جاري جلب أعلى الأفلام تقييماً...")
        url = f"https://api.themoviedb.org/3/movie/top_rated?api_key={TMDB_API_KEY}&language=ar-SA&page=1"
        try:
            response = requests.get(url, timeout=5).json()
            movies = response.get("results", [])
            try: await status_msg.delete()
            except: pass
            if not movies:
                await query.message.reply_text("❌ لم أتمكن من جلب الأفلام حالياً.")
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
                await query.message.reply_text(f"ℹ️ **{title}** موجود بالفعل في مفضلتك.", parse_mode="Markdown")
        except: pass

    elif data == "show_favorites":
        favs = USER_FAVORITES.get(user_id, [])
        if not favs:
            fav_text = "❤️ **قائمتك المفضلة فارغة حالياً.**\nابحث عن أعمال وأضفها عبر زر الحفظ!"
        else:
            fav_text = "⭐ **قائمتك المفضلة في فِلْمَه:**\n\n" + "\n".join([f"🍿 - {item}" for item in favs])
        await query.message.reply_text(fav_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 الرئيسية", callback_data="main_menu")]]))

    elif data == "main_menu":
        try: await query.message.delete()
        except: pass
        await start(update, context)

    elif data == "get_tg_file_0":
        # توجيه الملف المكتشف مباشرة للمستخدم من القنوات السحابية حقتنا
        files = USER_SEARCHES.get(user_id, [])
        if files:
            target = files[0]
            await context.bot.send_message(chat_id, "⏳ جاري توجيه ملف الفيديو لك سحابياً ومباشرة من تليجرام...")
            try:
                await context.bot.forward_message(chat_id=chat_id, from_chat_id=target["channel"], message_id=target["msg_id"])
            except Exception as fe:
                logger.error(f"Forward film error: {fe}")
                await context.bot.send_message(chat_id, "⚠️ تعذر سحب هذا الملف، يرجى الاستعانة بزر المشاهدة الخارجي حالياً.")

# 6. دالة استقبال نصوص البحث والربط الشامل بالبطاقات والبوسترات وقش القنوات السحابية بالتوازي
async def handle_message_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text_input = update.message.text
    step = context.user_data.get("login_step")

    # [مطور]: معالجة خطوات التحقق المباشر عند طلب الـ /login
    if step == "phone" and user_id == ADMIN_ID:
        context.user_data["phone"] = text_input.strip()
        await update.message.reply_text("⏳ جاري إرسال رمز تسجيل الدخول لحسابك المساعد...")
        try:
            if not user_bot_is_live():
                await userbot.connect()
            code_hash = await userbot.send_code(text_input.strip())
            context.user_data["code_hash"] = code_hash.phone_code_hash
            context.user_data["login_step"] = "code"
            await update.message.reply_text("📥 وصلك الرمز الحين من تليجرام! أرسله لي هنا (إذا فيه فواصل حط بين الأرقام مسافات).")
        except Exception as e:
            logger.error(f"Send code error: {e}")
            await update.message.reply_text(f"❌ فشل الإرسال: `{e}`\nأرسل الرقم مرة ثانية بشكل صحيح.")
        return

    elif step == "code" and user_id == ADMIN_ID:
        phone = context.user_data.get("phone")
        code_hash = context.user_data.get("code_hash")
        pure_code = text_input.strip().replace(" ", "")
        await update.message.reply_text("⚙️ جاري التوثيق وتوليد الجلسة السحابية الحين...")
        try:
            await userbot.sign_in(phone_number=phone, phone_code_hash=code_hash, phone_code=pure_code)
            exported_session = await userbot.export_session_string()
            context.user_data["login_step"] = None
            await update.message.reply_text(
                f"✅ **تم ربط وتفعيل الحساب المساعد بنجاح!**\n\n"
                f"لضمان عدم تسجيل الخروج مستقبلاً، انسخ هذا الكود وضعه في إعدادات Render باسم `STRING_SESSION`:\n\n"
                f"`{exported_session}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Sign in error: {e}")
            await update.message.reply_text(f"❌ رمز التحقق غير صحيح: `{e}`\nأعد المحاولة.")
        return

    # محرك البحث الطبيعي الأصلي للفيلم والمسلسل
    search_type = context.user_data.get('search_type', 'multi')
    chat_id = update.message.chat_id

    await update.message.reply_text(f"🔍 جاري البحث عن: *{text_input}* في سيرفرات وقنوات فِلْمَه...", parse_mode="Markdown")

    url = f"https://api.themoviedb.org/3/search/{search_type}?api_key={TMDB_API_KEY}&query={text_input}&language=ar"

    try:
        response = requests.get(url, timeout=5).json()
        results = response.get("results", [])

        if not results:
            await update.message.reply_text("❌ لم أتمكن من العثور على نتائج بالموقع، تأكد من صحة الاسم.")
            return

        # [تطوير]: تشغيل البحث في قنوات تليجرام بالتوازي بالتزامن مع الموقع حافاً على السرعة
        tg_files = await search_movies_in_channels(text_input)

        await send_movie_card(context, chat_id, results[0], tg_files=tg_files)
        context.user_data['search_type'] = 'multi'

    except Exception as e:
        logger.error(f"Search error: {e}")
        await update.message.reply_text("⚠️ حدث خطأ أثناء الاتصال بالخادم، جرب مرة أخرى.")

# 7. تشغيل البوت متزامن بالكامل ومربوط مع FastAPI لـ Render
@app.on_event("startup")
async def startup_event():
    if SESSION_STRING:
        try:
            await userbot.start()
            logger.info("Userbot started with saved session!")
        except Exception as e:
            logger.error(f"Failed to start userbot with session: {e}")

    try:
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("login", login_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_all))

        await application.initialize()
        await application.start()

        await application.bot.set_my_commands([
            BotCommand("start", "🚀 تشغيل البوت والتحكم الرئيسي"),
            BotCommand("help", "🔍 شرح طريقة استخدام البوت"),
            BotCommand("login", "📱 ربط الحساب المساعد وتفعيل قش القنوات")
        ])

        asyncio.create_task(application.updater.start_polling())
        logger.info("تم تفعيل كود فِلْمَه الهجين المتكامل بنجاح!")

    except Exception as e:
        logger.error(f"Startup error: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
