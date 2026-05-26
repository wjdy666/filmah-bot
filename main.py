import os
import logging
import request
import threading
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def home():
    return "Bot is alive and running!"

def run_web():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

# تشغيل السيرفر الوهمي في الخلفية
threading.Thread(target=run_web, daemon=True).start()
 
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# إعداد الـ Logs لمراقبة أداء البوت
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الإعدادات الأساسية
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("API_KEY")
ADMIN_ID = 1436656132  # الآي دي الخاص بك كأدمن

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """رسالة الترحيب الأصلية للبوت."""
    welcome = (
        "🎬 **أهلاً بك في بوت الأفلام والمسلسلات الاحترافي!**\n\n"
        "🍿 أرسل اسم أي فيلم أو مسلسل، وسأحضر لك البوستر، القصة، "
        "وخيارات التحكم والمشاهدة مباشرة داخل تليجرام!"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """البحث عن الفيلم وجلب بياناته من TMDB."""
    movie_name = update.message.text
    user_id = update.effective_user.id
    await update.message.reply_chat_action(action="upload_photo")

    if not TMDB_API_KEY:
        await update.message.reply_text("⚠️ خطأ: لم يتم ضبط الـ API_KEY في إعدادات Render.")
        return

    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={movie_name}&language=ar"
    
    try:
        response = requests.get(search_url).json()
        results = response.get('results', [])

        if not list(results):
            await update.message.reply_text("❌ لم يتم العثور على هذا العمل، تأكد من كتابة الاسم بالشكل الصحيح.")
            return

        item = results[0]
        tmdb_id = str(item.get('id'))
        title = item.get('title') or item.get('name') or "عنوان غير معروف"
        overview = item.get('overview') or "لا يوجد وصف متوفر باللغة العربية لهذا العمل حالياً."
        release_date = item.get('release_date') or item.get('first_air_date') or "غير محدد"
        rating = item.get('vote_average', 'غير مقيم')
        
        caption = (
            f"🎬 **الاسم:** {title}\n"
            f"📅 **تاريخ العرض:** {release_date}\n"
            f"⭐️ **التقييم:** {rating}/10\n\n"
            f"📝 **القصة:**\n{overview}"
        )

        poster_path = item.get('poster_path')
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

        # استخدام الذاكرة المؤقتة (Bot context) لفحص الروابط بدلاً من قاعدة البيانات المحلية
        saved_video = context.bot_data.get(f"vid_{tmdb_id}")

        keyboard = []
        if user_id == ADMIN_ID:
            if saved_video:
                keyboard.append([InlineKeyboardButton("🗑️ مسح الفيديو الحالي", callback_data=f"del_{tmdb_id}")])
            else:
                keyboard.append([InlineKeyboardButton("📥 ربط ملف فيديو", callback_data=f"link_{tmdb_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        # إرسال البوستر والمعلومات
        if poster_url:
            await update.message.reply_photo(photo=poster_url, caption=caption, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(caption, reply_markup=reply_markup, parse_mode="Markdown")
        
        # إرسال الفيديو إذا كان مربوطاً ومخزناً في ذاكرة البوت الحالية
        if saved_video:
            await update.message.reply_video(video=saved_video, caption=f"🍿 مشاهدة ممتعة لـ: {title}")
        elif user_id != ADMIN_ID:
            await update.message.reply_text("⏳ **هذا الفيلم غير متوفر حالياً، سيقوم الأدمن بتوفيره قريباً!**")

    except Exception as e:
        logger.error(f"Search Error: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء معالجة البحث يرجى المحاولة مرة أخرى.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة الضغط على أزرار الربط والمسح التفاعلية للـ الأدمن."""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return

    data = query.data
    if data.startswith("link_"):
        tmdb_id = data.split("_")[1]
        context.user_data['waiting_for_video'] = tmdb_id
        await query.message.reply_text("🔄 **وضع الربط نشط الآن!**\nقم بعمل توجيه (Forward) لملف الفيلم المُراد ربطه إلى هنا مباشرة كملف فيديو.", parse_mode="Markdown")
    
    elif data.startswith("del_"):
        tmdb_id = data.split("_")[1]
        if f"vid_{tmdb_id}" in context.bot_data:
            del context.bot_data[f"vid_{tmdb_id}"]
        await query.message.reply_text("🗑️ تم مسح الفيديو المرتبط بالعمل بنجاح من الذاكرة.")

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """استقبال ملف الفيديو الأصلي من الأدمن وتثبيته ديناميكياً."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID or 'waiting_for_video' not in context.user_data:
        return

    tmdb_id = context.user_data['waiting_for_video']
    file_id = update.message.video.file_id

    # حفظ في ذاكرة البوت المستقرة أثناء التشغيل (bot_data)
    context.bot_data[f"vid_{tmdb_id}"] = file_id
    del context.user_data['waiting_for_video']
    
    await update.message.reply_text("✅ تم ربط وحفظ ملف الفيديو بنجاح! جرب البحث عن الفيلم الآن وستجده يعمل كاملاً.")

def main() -> None:
    """تشغيل البوت المستقر."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN غير موجود في البيئة.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.VIDEO, receive_video))

    logger.info("تم بدء تشغيل البوت بنجاح...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
