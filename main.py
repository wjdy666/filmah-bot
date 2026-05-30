import os
import logging
import asyncio
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from pyrogram import Client

# 1. إعدادات الـ Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. الإعدادات الأساسية (تعديل التوكن والمعرفات)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7965754682:AAGGBGIUBG_-_ALb8R3624bpycP4iiH_Jdg")
ADMIN_ID = 1436656132
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "36214571cc6d6b8b0e78453a57cc49ae")
API_ID = int(os.environ.get("API_ID", 37617537))
API_HASH = os.environ.get("API_HASH", "453a57cc49aed64b6ebbfd1eb11645da")
MOVIE_CHANNELS = ["wecimaR", "HI_VZ", "jdjdiso0", "runawayz1"]

BOT_USERS = set()
USER_SEARCHES = {} 

# نظام حفظ الجلسة مؤقتاً بالذاكرة لتفادي مشاكل الـ EOF
SESSION_STRING = os.environ.get("STRING_SESSION", None)

app = FastAPI()

@app.get("/")
@app.head("/")
def home():
    return "Filmh Hybrid Bot is alive and running!"

# إنشاء كائن الـ Userbot (إذا متوفرة الجلسة يشتغل فوراً، وإلا ينتظر التفعيل عبر الحوار)
if SESSION_STRING:
    userbot = Client("filmh_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
else:
    userbot = Client("filmh_userbot", api_id=API_ID, api_hash=API_HASH, in_memory=True)

# دالة البحث في موقع الأفلام TMDB
def search_tmdb(query_text):
    try:
        url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query_text}&language=ar"
        response = requests.get(url).json()
        return response.get("results", [])
    except Exception as e:
        logger.error(f"TMDB API Error: {e}")
        return []

# محرك قش الملفات من القنوات عبر الـ Userbot
async def search_movies_in_channels(query_text):
    found_messages = []
    # إذا الحساب المساعد مش متصل، ما نخليه يعلق السيرفر، يتخطى ويبحث بالموقع بس
    if not userbot.is_connected:
        logger.warning("Userbot is not connected yet. Skipping channel search.")
        return found_messages
        
    try:
        for channel in MOVIE_CHANNELS:
            try:
                async for message in userbot.search_messages(chat_id=channel, query=query_text, limit=5):
                    if message.video or message.document or message.text:
                        found_messages.append({
                            "channel": channel,
                            "msg_id": message.id,
                            "text": message.caption or message.text or "ملف سينمائي تليجرام"
                        })
            except Exception as ce:
                logger.error(f"Channel {channel} search error: {ce}")
    except Exception as e:
        logger.error(f"Global Userbot search error: {e}")
    return found_messages

# دالة عرض وتصفح النتائج الهجينة
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

# دالة الترحيب /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    BOT_USERS.add(update.effective_user.id)
    welcome = (
        "🎬 **مرحباً بك في بوت فِلْمَه الهجين المطور!**\n\n"
        "النظام الأقوى الذي يدمج بين قاعدة بيانات الأفلام العالمية وقش ملفات التليجرام السحابية المباشرة 🍿\n\n"
        "💡 **اكتب اسم أي فيلم أو مسلسل، وسأجلب لك تفاصيله مع روابط التحميل المباشرة فوراً!**"
    )
    keyboard = [
        [InlineKeyboardButton("🔍 ابدأ البحث المباشر", callback_data="trigger_search")],
        [InlineKeyboardButton("📊 إحصائيات البوت", callback_data="bot_stats")]
    ]
    await update.effective_message.reply_text(welcome, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# --- 📱 نظام تسجيل الدخول التفاعلي للحساب المساعد من داخل التليجرام 📱 ---
async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الأمر مخصص لمالك البوت فقط.")
        return
    
    if user_bot_is_live():
        await update.message.reply_text("✅ الحساب المساعد متصل بالفعل وشغال تمام!")
        return

    context.user_data["login_step"] = "phone"
    await update.message.reply_text("📱 أهلاً بك يا مطورنا. يرجى إرسال رقم هاتف الحساب المساعد مع رمز الدولة.\nمثال: `+966500000000`", parse_mode="Markdown")

def user_bot_is_live():
    try: return userbot.is_connected
    except: return False

# استقبال نصوص المحادثة (البحث + خطوات تسجيل الدخول)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    step = context.user_data.get("login_step")

    # معالجة خطوات تسجيل الدخول للـ Userbot
    if step == "phone" and user_id == ADMIN_ID:
        context.user_data["phone"] = text.strip()
        await update.message.reply_text("⏳ جاري إرسال رمز التحقق إلى حسابك في تليجرام...")
        try:
            if not userbot.is_connected:
                await userbot.connect()
            code_hash = await userbot.send_code(text.strip())
            context.user_data["code_hash"] = code_hash.phone_code_hash
            context.user_data["login_step"] = "code"
            await update.message.reply_text("📥 تم إرسال الرمز بنجاح! أرسل لي رمز التحقق الحين (إذا الرمز فيه فواصل حط بينها مسافات).")
        except Exception as e:
            logger.error(f"Send code error: {e}")
            await update.message.reply_text(f"❌ فشل إرسال الرمز بسبب:\n`{e}`\nأعد إرسال الرقم للمحاولة مرة أخرى.", parse_mode="Markdown")
        return

    elif step == "code" and user_id == ADMIN_ID:
        phone = context.user_data.get("phone")
        code_hash = context.user_data.get("code_hash")
        pure_code = text.strip().replace(" ", "")
        
        await update.message.reply_text("⚙️ جاري تسجيل الدخول وإنشاء الجلسة السحابية...")
        try:
            await userbot.sign_in(phone_number=phone, phone_code_hash=code_hash, phone_code=pure_code)
            exported_session = await userbot.export_session_string()
            context.user_data["login_step"] = None
            
            await update.message.reply_text(
                f"✅ **تم تفعيل الحساب المساعد بنجاح خارق!**\n\n"
                f"لضمان استقرار البوت ومنع تسجيل الخروج مستقبلاً، انسخ هذا الكود الطويل وضعه في إعدادات Render باسم `STRING_SESSION`:\n\n"
                f"`{exported_session}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Sign in error: {e}")
            await update.message.reply_text(f"❌ فشل التحقق من الرمز:\n`{e}`\nأعد إرسال الرمز الصحيح المكون من 5 أرقام.")
        return

    # معالجة محرك البحث الطبيعي للأفلام
    chat_id = update.message.chat_id
    status_msg = await update.message.reply_text(f"🕵️‍♂️ جاري الفحص في موقع الأفلام وقش *{text}* من السحابة...", parse_mode="Markdown")
    
    tmdb_results = search_tmdb(text)
    tg_results = await search_movies_in_channels(text)

    try: await status_msg.delete()
    except: pass

    if not tmdb_results and not tg_results:
        await update.message.reply_text("❌ عذراً، لم أجد هذا العمل حالياً.")
        return

    USER_SEARCHES[user_id] = {"tmdb": tmdb_results, "tg": tg_results}
    await show_page_results(context, chat_id, user_id, 1)

# معالج النقرات للأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    data = query.data

    if data == "main_menu" or data == "trigger_search":
        await start(update, context)
    elif data == "bot_stats":
        status = "🟢 متصل" if user_bot_is_live() else "🔴 غير نشط (اكتب /login لتفعيله)"
        await query.message.reply_text(f"📊 **إحصائيات فِلْمَه:**\n\n👥 عدد المشتركين: `{len(BOT_USERS)}` مستخدم.\n📡 اتصال الحساب المساعد: {status}")
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
            except Exception as fe:
                logger.error(f"Forward failed: {fe}")
                await context.bot.send_message(chat_id, "⚠️ تعذر توجيه هذا الملف المحدّد.")
        else:
            await query.message.reply_text("❌ انتهت الجلسة.")

@app.on_event("startup")
async def startup_event():
    # تعديل الإقلاع: إذا في جلسة قديمة نشغلها، غير كذا السيرفر يقوم طبيعي بدون كراش وينتظر الـ /login
    if SESSION_STRING:
        try:
            await userbot.start()
            logger.info("Userbot successfully launched using STRING_SESSION!")
        except Exception as e:
            logger.error(f"Saved session login failed: {e}")
            
    try:
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("login", login_command))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        await application.initialize()
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.start()
        await application.bot.set_my_commands([
            BotCommand("start", "🚀 تشغيل القائمة الرئيسية"),
            BotCommand("login", "📱 تفعيل الحساب المساعد للبوت")
        ])
        asyncio.create_task(application.updater.start_polling(drop_pending_updates=True))
        logger.info("Main Bot Application is successfully running!")
    except Exception as e:
        logger.error(f"Main application crash: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
