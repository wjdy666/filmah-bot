import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد الـ Logs لمراقبة البوت
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# جلب التوكنات بأمان من إعدادات Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("API_KEY")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دالة الترحيب عند تشغيل البوت."""
    welcome_text = (
        "🎬 أهلاً بك في بوت الأفلام والمسلسلات!\n\n"
        "🍿 كل ما عليك فعله هو إرسال **اسم الفيلم أو المسلسل** باللغة العربية أو الإنجليزية، "
        "وسأقوم بجلب كامل تفاصيله وبوستر العرض الخاص به فوراً."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """الدالة الذكية للبحث عن الأفلام والرد بالتفاصيل والبوستر."""
    movie_name = update.message.text
    await update.message.reply_chat_action(action="upload_photo")

    if not TMDB_API_KEY:
        await update.message.reply_text("⚠️ خطأ: لم يتم ضبط مفتاح الـ API الخاص بالأفلام في السيرفر.")
        return

    # رابط البحث في موقع TMDB مع دعم اللغة العربية
    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={movie_name}&language=ar"

    try:
        response = requests.get(search_url).json()
        results = response.get('results', [])

        if not results:
            await update.message.reply_text("❌ عذراً، لم أعثر على أي نتائج مطابقة لهذا الاسم. تأكد من كتابته بشكل صحيح.")
            return

        # جلب أول نتيجة تظهر في البحث
        item = results[0]
        title = item.get('title') or item.get('name') or "عنوان غير معروف"
        overview = item.get('overview') or "لا يوجد وصف متوفر باللغة العربية لهذا العمل حالياً."
        release_date = item.get('release_date') or item.get('first_air_date') or "غير محدد"
        media_type = "فيلم 🎬" if item.get('media_type') == 'movie' else "مسلسل 📺"
        rating = item.get('vote_average', 'غير مقيم')

        # تجهيز نص الرسالة
        caption = (
            f"🎬 **الاسم:** {title}\n"
            f"📌 **النوع:** {media_type}\n"
            f"📅 **تاريخ العرض:** {release_date}\n"
            f"⭐️ **التقييم:** {rating}/10\n\n"
            f"📝 **القصة:**\n{overview}"
        )

        # جلب بوستر الفيلم إذا كان متوفراً
        poster_path = item.get('poster_path')
        if poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
            await update.message.reply_photo(photo=poster_url, caption=caption, parse_mode="Markdown")
        else:
            await update.message.reply_text(caption, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error during search: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء الاتصال بسيرفر الأفلام، يرجى المحاولة لاحقاً.")

def main() -> None:
    """تشغيل البوت."""
    if not BOT_TOKEN:
        logger.error("لم يتم العثور على BOT_TOKEN")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # ربط الأوامر والرسائل بالذكاء الجديد
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie))

    logger.info("البوت الذكي يعمل الآن...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
