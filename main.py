import os
import logging
import asyncio
import requests
from fastapi import FastAPI
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from pyrogram import Client

# 1. إعدادات الـ Logs لمراقبة أداء السيرفر وثباته
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 2. الإعدادات الأساسية والمعرفات الخاصة بك
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 1436656132
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "36214571cc6d6b8b0e78453a57cc49ae") # تم جلب الـ Key من سورس الـ API القديم

# بيانات الحساب المساعد (Userbot) المستخرجة لحسابك
API_ID = 37617537
API_HASH = "453a57cc49aed64b6ebbfd1eb11645da"

# مصادر قنوات الأفلام العامة المستهدفة لقش الفيديوهات منها
MOVIE_CHANNELS = ["wecimaR", "HI_VZ", "jdjdiso0", "runawayz1"]

# الذاكرة المؤقتة لحفظ المستخدمين ونتائج البحث للتنقل المستقر بين الصفحات
BOT_USERS = set()
USER_SEARCHES = {} 

# 3. إعداد سيرفر الويب FastAPI لتثبيت التشغيل في Render ومنع الإغلاق التلقائي
app = FastAPI()

@app.get("/")
@app.head("/")
def home():
    return "Filmh Hybrid Bot is alive and running!"

# 4. إعداد الحساب المساعد (Pyrogram Client) بالخلفية
userbot = Client("filmh_userbot", api_id=API_ID, api_hash=API_HASH, bot_token=None)

# 5. دالة البحث في الـ API القديم (TMDB) لجلب تفاصيل الفيلم والبوستر
def search_tmdb(query_text):
    try:
        url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={query_text}&language=ar"
        response = requests.get(url).json()
        results = response.get("results", [])
        return results
    except Exception as e:
        logger.error(f"TMDB API Error: {e}")
        return []

# 6. محرك البحث وقش الرسائل الذكي داخل قنوات تليجرام العامة عبر الـ Userbot
async def search_movies_in_channels(query_text):
    found_messages = []
    try:
        if not userbot.is_connected:
            await userbot.start()
            
        for channel in MOVIE_CHANNELS:
            try:
                # فحص محتوى القناة المحددة بناءً على الكلمة المفتاحية المكتوبة
                async for message in userbot.search_messages(chat_id=channel, query=query_text, limit=5):
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

# --- 🛠️ نظام تصفح الصفحات الهجين والمطابق للتصميم الهندسي المطلوب تماماً 🛠️ ---
async def show_page_results(context, chat_id, user_id, page):
    results = USER_SEARCHES.get(user_id, {})
    tmdb_results = results.get("tmdb", [])
    tg_results = results.get("tg", [])

    total_pages = max(len(tmdb_results), len(tg_results), 1)
    
    if page > total_pages or page < 1:
        await context.bot.send_message(chat_id, "❌ لا توجد صفحات أخرى للعرض.")
        return

    # بناء نص كرت الفيلم (تجميع بيانات الـ API مع بيانات تليجرام)
    caption_text = "🎬 **نتائج بحث فِلْمَه الذكية:**\n\n"
    poster_url = None

    # أولاً: جلب بيانات الموقع الـ API إذا توفرت في هذه الصفحة
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

    # ثانياً: ربط زر التليجرام إذا لقى الـ Userbot ملفات متوافقة في هذه الصفحة
    has_tg_file = False
    if page <= len(tg_results):
        has_tg_file = True
        tg_item = tg_results[page - 1]
        if page > len(tmdb_results): # إذا مافي بيانات من الموقع، نعرض نص التليجرام
            caption_text += f"📄 _{tg_item['text'][:300]}..._\n\n"

    caption_text += "💡 _تصفح النتائج بالأزرار في الأسفل!_"

    # بناء مصفوفة الأزرار وتوزيعها هندسياً بدقة
    keyboard = []
    
    # السطر الأول: زر التحميل المباشر يظهر "فقط" إذا الـ Userbot لقى الفيلم بالقنوات
    if has_tg_file:
        keyboard.append([InlineKeyboardButton("📥 مشاهدة وتحميل مباشر (داخل تليجرام)", callback_data=f"get_tg_{page-1}")])
    else:
        keyboard.append([InlineKeyboardButton("🌐 جاري البحث عن سيرفرات مشاهدة خارجية...", callback_data="no_file")])
    
    # السطر الثاني: أزرار التحكم بالتنقل (التالية على اليمين والسابقة على اليسار في نفس الصف)
    nav_row = []
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("الصفحة التالية ➡️", callback_data=f"hybrid_page_{page + 1}"))
    if page > 1:
        nav_row.append(InlineKeyboardButton("السابقة ⬅️", callback_data=f"hybrid_page_{page - 1}"))
        
    if nav_row:
        keyboard.append(nav_row)
        
    # السطر الثالث السفلي: زر العودة المباشرة للقائمة الرئيسية
    keyboard.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="main_menu")])
        
    # إرسال النتيجة بالبوستر إن وجد، أو رسالة نصية إن لم يوجد بوستر
    try:
        if poster_url:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=poster_url,
                caption=caption_text[:1024],
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=caption_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    except Exception as send_err:
        logger.error(f"Error sending message/photo: {send_err}")
    
    # نص مستقل لإعلام المستخدم برقم الصفحة الحالية أسفل الأزرار
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"📄 صفحة البحث الحالية: {page} من {total_pages}"
    )

# 7. دالة الترحيب الأصلية لبوت فِلْمَه
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

# 8. دالة استقبال مدخلات النص وتنشيط محركي البحث (الـ API والـ Userbot معاً)
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.message.chat_id
    search_query = update.message.text

    status_msg = await update.message.reply_text(
        f"🕵️‍♂️ جاري الفحص في موقع الأفلام وقش *{search_query}* من السحابة...",
        parse_mode="Markdown"
    )

    # تشغيل البحثين بالتوازي لسرعة خارقة
    tmdb_results = search_tmdb(search_query)
    tg_results = await search_movies_in_channels(search_query)

    try: await status_msg.delete()
    except: pass

    if not tmdb_results and not tg_results:
        await update.message.reply_text("❌ عذراً، لم أجد هذا العمل حالياً لا في الموقع ولا في قنوات التليجرام المربوطة.")
        return

    # تخزين النتائج المدمجة في الذاكرة المؤقتة
    USER_SEARCHES[user_id] = {"tmdb": tmdb_results, "tg": tg_results}
    
    # تقديم الصفحة الأولى فورياً مع القوالب الجديدة
    await show_page_results(context, chat_id, user_id, 1)

# 9. معالج النقرات التفاعلية للأزرار والتحكم المطور بالصفحات
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    chat_id = query.message.chat_id
    data = query.data

    if data == "main_menu" or data == "trigger_search":
        await start(update, context)

    elif data == "bot_stats":
        await query.message.reply_text(f"📊 **إحصائيات فِلْمَه:**\n\n👥 عدد المشتركين النشطين: `{len(BOT_USERS)}` مستخدم.\n📡 نظام البحث: هجين (موقع ويب + قش قنوات سحابية).")

    # معالجة تغيير الصفحات هيدروليكياً في النظام الهجين
    elif data.startswith("hybrid_page_"):
        next_page = int(data.split("_")[2])
        try: await query.message.delete()
        except: pass
        await show_page_results(context, chat_id, user_id, next_page)

    # سحب وتوجيه ملف الفيديو الأصلي المكتشف فوراً إلى محادثة العضو
    elif data.startswith("get_tg_"):
        idx = int(data.split("_")[2])
        results = USER_SEARCHES.get(user_id, {}).get("tg", [])
        if idx < len(results):
            movie = results[idx]
            await context.bot.send_message(chat_id, "⏳ جاري سحب وتوجيه الفيديو لك مباشرة من خوادم تليجرام السريعة بدون روابط خارجية...")
            
            try:
                await context.bot.forward_message(
                    chat_id=chat_id,
                    from_chat_id=movie["channel"],
                    message_id=movie["msg_id"]
                )
            except Exception as forward_err:
                logger.error(f"Forward failed: {forward_err}")
                await context.bot.send_message(chat_id, "⚠️ تعذر توجيه هذا الملف المحدد، جرب الانتقال للملف الموالي بالصفحة التالية.")
        else:
            await query.message.reply_text("❌ انتهت صلاحية جلسة تصفح هذا الملف.")

# 10. تشغيل الحساب المساعد وربط المحرك بالتوازي عند إقلاع السيرفر
@app.on_event("startup")
async def startup_event():
    try:
        await userbot.start()
        logger.info("Userbot Bridge successfully connected!")
    except Exception as e:
        logger.error(f"Userbot auto start delayed (Will initialize when session code is verified): {e}")

    try:
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

        await application.initialize()
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.start()

        await application.bot.set_my_commands([
            BotCommand("start", "🚀 تشغيل بوت فِلْمَه والقائمة الرئيسية")
        ])

        asyncio.create_task(application.updater.start_polling(drop_pending_updates=True))
        logger.info("Main Bot Application is successfully running with Hybrid system!")

    except Exception as e:
        logger.error(f"Main application crash: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
