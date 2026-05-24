import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد الـ Logs لمراقبة البوت من لوحة تحكم Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# جلب التوكن بأمان من إعدادات Environment المتواجدة في Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# دالة الترحيب عند الضغط على أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('أهلاً بك! البوت يعمل الآن بنجاح على منصة Render. 🚀')

# دالة تكرار الرسائل النصية (Echo)
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"وصلتني رسالتك: {update.message.text}")

def main() -> None:
    """تشغيل وبناء البوت."""
    if not BOT_TOKEN:
        logger.error("خطأ حرج: لم يتم العثور على المتغير 'BOT_TOKEN' في إعدادات المنصة!")
        return

    # بناء تطبيق البوت بالتوكن الخاص بك
    application = Application.builder().token(BOT_TOKEN).build()

    # ربط الأوامر والرسائل بالدوال البرمجية
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # بدء استقبال التحديثات من سيرفرات تليجرام
    logger.info("جاري بدء تشغيل البوت واستقبال الرسائل...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
