import os
import logging
import asyncio
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from pyrogram import Client

# 1. إعدادات الـ Logs لمراقبة أداء وثبات السيرفر
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. الإعدادات والمعرفات الخاصة بك
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 1436656132
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "36214571cc6d6b8b0e78453a57cc49ae")

# بيانات الحساب المساعد الخاص بك
API_ID = 37617537
API_HASH = "453a57cc49aed64b6ebbfd1eb11645da"

# مصادر قنوات الأفلام العامة
MOVIE_CHANNELS = ["wecimaR", "HI_VZ", "jdjdiso0", "runawayz1"]

# الذاكرة المؤقتة لحفظ حالات الجلسات والبحث
BOT_USERS = set()
USER_SEARCHES = {} 
SESSION_DATA = {"phone_code_hash": None, "phone": None}

# 3. إعداد سيرفر الويب FastAPI لمنع إغلاق السيرفر في Render
app = FastAPI()

@app.get("/")
@app.head("/")
def home():
    return "Filmh Hybrid Bot is perfectly alive!"

# 4. إعداد الحساب المساعد (بدون تشغيل تلقائي لتفادي الأخطاء)
userbot = Client("filmh_userbot", api_id=API_ID, api_hash=API_HASH, in_memory=False)

# 5. دالة البحث في الـ API (TMDB) لجلب البوستر والقصة
def search_tmdb(query_text):
    try:
        url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query_text}&language=ar"
        response = requests.get(url).json()
        return response.get("results", [])
    except Exception as e:
        logger.error(f"TMDB API Error: {e}")
        return []

# 6. محرك قش الرسائل من قنوات تليجرام عبر الـ Userbot
async def search_movies_in_channels(query_text):
    found_messages = []
    # نتأكد أن الحساب المساعد متصل ومسجل دخول أولاً
    if not userbot.is_initialized:
        return found_messages
    try:
        if not userbot.is_connected:
            await userbot.start()
            
        for channel in MOVIE_CHANNELS:
            try:
                async range_msg in userbot.search_messages(chat_id=channel, query=query_text, limit=5):
                    if message.video or message.document or message.text:
                        found_messages.append({
                            "channel": channel,
                            "msg_id": message.id,
                            "text": message.caption or message.text or "ملف سينمائي تليجرام"
                        })
            except Exception as channel_err:
                logger.error(f"Error searching in channel {channel}: {channel_err}")
    except Exception as e:
        logger.error(f"Global Userbot search error: {e}")
    return found_messages

# --- 🛠️ نظام تصفح الصفحات الهجين والمطابق للتصميم الهندسي المطلوب 🛠️ ---
async def show_page_results(context, chat_id, user_id, page):
    results = USER_SEARCHES.get(user_id, {})
    tmdb_results = results.get("tmdb", [])
    tg_results = results.get("tg", [])

    total_pages = max(len(tmdb_results), len(tg_results), 1)
    
    if page > total_pages or page < 1:
        await context.bot.send_message(chat_id, "❌ لا توجد صفحات أخرى للعرض.")
        return

    caption_text = "🎬 **نتائج بحث فِلْمَه الذكية:**\n\n"
    poster_url = None

    if page <= len(tmdb_results):
        item = tmdb_results[page - 1]
        title = item.get("title") or item.get("name") or "عنوان غير معروف"
        overview = item.get("overview") or "لا يوجد وصف متوفر حالياً لهذا العمل."
        rate = item.get("vote_average", "غير مقيم")
        date = item.get("release_date") or item.get("first_air_date") or "غير معروف"
        
        caption_text += f"📌 **الاسم:** {title}\n🗓️ **التاريخ:** {date}\n⭐️ **التقييم:** {rate}/10\n\n📝 **القصة:**\n_{overview}_\n\n"
        if item.get("poster_path"):
            poster_url = f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}"
    else:
        caption_text += "📦 **تم العثور على هذا العمل داخل قنوات تليجرام مباشرة:**\n\n"

    has_tg_file = False
    if page <= len(tg_results):
        has_tg_file = True
        tg_item = tg_results[page - 1]
        if page > len(tmdb_results):
            caption_text += f"📄 _{tg_item['text'][:300]}..._\n\n"

    caption_text += "💡 _تصفح النتائج بالأزرار في الأسفل!_"

    keyboard = []
    if has_tg_file:
        keyboard.append([InlineKeyboardButton("📥 مشاهدة وتحميل مباشر (داخل تليجرام)", callback_data=f"get_tg_{page-1}")])
    else:
        keyboard.append([InlineKeyboardButton("🌐 جاري البحث عن سيرفرات مشاهدة خارجية...", callback_data="no_file")])
    
    nav_row = []
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("الصفحة التالية ➡️", callback_data=f"hybrid_page_{page + 1}"))
    if page > 1:
        nav_row.append(InlineKeyboardButton("السابقة ⬅️", callback_data=f"hybrid_page_{page - 1}"))
        
    if nav_row:
        keyboard.append(nav_row)
        
    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])
        
    try:
        if poster_url:
            await context.bot.send_photo(chat_id=chat_id, photo=poster_url, caption=caption_text[:1024], parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=chat_id, text=caption_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as send_err:
        logger.error(f"Error sending results: {send_err}")
    
    await context.bot.send_message(chat_id=chat_id, text=f"📄 صفحة البحث الحالية: {page} من {total_pages}")

# 7. دالة الترحيب الأصلية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    BOT_USERS.add(update.effective_user.id)
    welcome = (
        "🎬 **مرحباً بك في بوت فِلْمَه الهجين المطور!**\n\n"
        "النظام الأقوى الذي يدمج بين قاعدة بيانات الأفلام العالمية وقش ملفات التليجرام السحابية المباشرة 🍿\n\n"
        "💡 **اكتب اسم أي فيلم أو مسلسل، وسأجلب لك تفاصيله فوراً!**"
    )
    keyboard = [
        [InlineKeyboardButton("🔍 ابدأ البحث المباشر", callback_data="trigger_search")],
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="bot_stats")]
    ]
    await update.effective_message.reply_text(welcome, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# --- 📱 نظام الـ Login الداخلي والمختصر لتفعيل الحساب المساعد 📱 ---
async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    context.user_data["login_step"] = "waiting_phone"
    await update.message.reply_text("📱 **مرحباً بك في نظام التفعيل السريع!**\n\nأرسل الآن رقم هاتف الحساب المساعد مع رمز الدولة كاملاً.\nمثال: `+9665xxxxxxxx`")

async def handle_admin_inputs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.message.chat_id
    text = update.message.text

    if user_id != ADMIN_ID:
        # إذا لم يكن الآدمن، نعتبر الرسالة بحث عادي عن الأفلام
        await handle_search(update, context)
        return

    step = context.user_data.get("login_step")

    if step == "waiting_phone":
        SESSION_DATA["phone"] = text
        await update.message.reply_text("⏳ جاري الاتصال بتليجرام وإرسال كود التفعيل...")
        try:
            await userbot.connect()
            code_data = await userbot.send_code(text)
            SESSION_DATA["phone_code_hash"] = code_data.phone_code_hash
            context.user_data["login_step"] = "waiting_code"
            await update.message.reply_text("📩 وصلك الآن كود من شركة تليجرام على حسابك المساعد.\n\n**قم بكتابة الكود هنا في المحادثة فوراً.**")
        except Exception as e:
            await update.message.reply_text(f"❌ حدث خطأ أثناء إرسال الكود:\n`{e}`\n\nأرسل /login للمحاولة مرة أخرى.")
            context.user_data["login_step"] = None

    elif step == "waiting_code":
        await update.message.reply_text("⏳ جاري التحقق من الكود وإنشاء الجلسة السحابية...")
        try:
            await userbot.sign_in(
                phone_number=SESSION_DATA["phone"],
                phone_code_hash=SESSION_DATA["phone_code_hash"],
                phone_code=text
            )
            await update.message.reply_text("✅ **تهانينا! تم تفعيل وتدشين الحساب المساعد بنجاح أسطوري!**\n\nنظام قش القنوات شغال الحين بكامل قوته السحابية 🚀")
        except Exception as e:
            await update.message.reply_text(f"❌ الكود خاطئ أو انتهت صلاحيته:\n`{e}`\n\nأرسل /login للبدء من جديد.")
        context.user_data["login_step"] = None
    else:
        # إذا لم يكن هناك خطوة تسجيل دخول، يتم التعامل مع النص كبحث عن الأفلام
        await handle_search(update, context)

# 8. دالة استقبال مدخلات البحث عن الأفلام
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.message.chat_id
    search_query = update.message.text

    status_msg = await update.message.reply_text(f"🕵️‍♂️ جاري الفحص والقش عن *{search_query}*...", parse_mode="Markdown")

    tmdb_results = search_tmdb(search_query)
    tg_results = await search_movies_in_channels(search_query)

    try: await status_msg.delete()
    except: pass

    if not tmdb_results and not tg_results:
        await update.message.reply_text("❌ عذراً، لم أجد هذا العمل حالياً لا في الموقع ولا في قنوات التليجرام المربوطة.")
        return

    USER_SEARCHES[user_id] = {"tmdb": tmdb_results, "tg": tg_results}
    await show_page_results(context, chat_id, user_id, 1)

# 9. معالج الأزرار والتنقل والتوجيه
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    data = query.data

    if data == "main_menu" or data == "trigger_search":
        await start(update, context)
    elif data == "bot_stats":
        await query.message.reply_text(f"📊 **إحصائيات فِلْمَه:**\n\n👥 عدد المشتركين النشطين: `{len(BOT_USERS)}` مستخدم.\n📡 نظام البحث: هجين ومستقر.")
    elif data.startswith("hybrid_page_"):
        next_page = int(data.split("_")[2])
        try: await query.message.delete()
        except: pass
        await show_page_results(context, chat_id, user_id, next_page)
    elif data.startswith("get_tg_"):
        idx = int(data.split("_")[2])
        results = USER_SEARCHES.get(user_id, {}).get("tg", [])
        if idx < len(results):
            movie = results[idx]
            await context.bot.send_message(chat_id, "⏳ جاري سحب وتوجيه الفيديو لك مباشرة...")
            try:
                await context.bot.forward_message(chat_id=chat_id, from_chat_id=movie["channel"], message_id=movie["msg_id"])
            except Exception as e:
                await context.bot.send_message(chat_id, "⚠️ تعذر توجيه هذا الملف، جرب الصفحة التالية.")
        else:
            await query.message.reply_text("❌ انتهت صلاحية هذه الجلسة.")

# 10. تشغيل البوت الرسمي عند إقلاع السيرفر
@app.on_event("startup")
async def startup_event():
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("login", admin_login))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_inputs))

        await application.initialize()
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.start()
        await application.bot.set_my_commands([
            BotCommand("start", "🚀 القائمة الرئيسية"),
            BotCommand("login", "📱 تفعيل الحساب المساعد (للمشرف فقط)")
        ])
        asyncio.create_task(application.updater.start_polling(drop_pending_updates=True))
        logger.info("Main Bot Application is running. Awaiting /login from admin.")
    except Exception as e:
        logger.error(f"Main application crash: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
