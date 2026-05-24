import os
import logging
import sqlite3
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد الـ Logs لمراقبة البوت
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الإعدادات الأساسية
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("API_KEY")
ADMIN_ID = 1436656132  # الآيدي الخاص بك كأدمن

def init_db():
    conn = sqlite3.connect('movies_db.sqlite')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            tmdb_id TEXT PRIMARY KEY,
            title TEXT,
            file_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دالة الترحيب."""
    welcome = (
        "🎬 **أهلاً بك في بوت الأفلام للمشاهدة المباشرة داخل تليجرام!**\n\n"
        "🍿 أرسل اسم أي فيلم، وسأحضره لك كاملاً للمشاهدة فوراً بدون روابط خارجية!"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """البحث المباشر عن الفيلم."""
    movie_name = update.message.text
    user_id = update.effective_user.id
    
    # إذا كان الأدمن يرسل نصاً ويبدأ بكلمة "ربط"، نتجاهله هنا لأنه مخصص للرفع
    if context.user_data.get('waiting_for_video'):
        await update.message.reply_text("⚠️ أنت في وضع ربط الفيلم، أرسل ملف الفيديو (فيديو أصلي) أو أرسل /start للإلغاء.")
        return

    await update.message.reply_chat_action(action="upload_photo")

    if not TMDB_API_KEY:
        await update.message.reply_text("⚠️ خطأ: لم يتم ضبط الـ API_KEY.")
        return

    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={movie_name}&language=ar"
    
    try:
        response = requests.get(search_url).json()
        results = response.get('results', [])

        if not map or not results:
            await update.message.reply_text("❌ لم يتم العثور على هذا العمل، تأكد من كتابة الاسم بالشكل الصحيح.")
            return

        item = results[0]
        tmdb_id = str(item.get('id'))
        title = item.get('title') or item.get('name') or "عنوان غير معروف"
        overview = item.get('overview') or "لا يوجد وصف متوفر باللغة العربية."
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

        # الفحص في قاعدة البيانات
        conn = sqlite3.connect('movies_db.sqlite')
        cursor = conn.cursor()
        cursor.execute("SELECT file_id FROM movies WHERE tmdb_id = ?", (tmdb_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            # إذا الفيلم موجود نرسل البوستر ثم الفيديو فوراً
            file_id = row[0]
            if poster_url:
                await update.message.reply_photo(photo=poster_url, caption=caption, parse_mode="Markdown")
            else:
                await update.message.reply_text(caption, parse_mode="Markdown")
            
            await update.message.reply_video(video=file_id, caption=f"🍿 مشاهدة ممتعة لفيلم: {title}")
        else:
            # إذا الفيلم غير موجود
            if user_id == ADMIN_ID:
                context.user_data['waiting_for_video'] = tmdb_id
                context.user_data['waiting_title'] = title
                caption += f"\n\n⚙️ **(تنبيه الأدمن):** هذا الفيلم غير متوفر. لربطه الآن، قم بعمل توجيه (Forward) لملف الفيديو الأصلي الخاص بالفيلم إلى هنا فوراً."
            else:
                caption += "\n\n⏳ **هذا الفيلم غير متوفر حالياً، سيتم توفيره قريباً من قِبل الإدارة!**"

            if poster_url:
                await update.message.reply_photo(photo=poster_url, caption=caption, parse_mode="Markdown")
            else:
                await update.message.reply_text(caption, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Search Error: {e}")
        await update.message.reply_text("❌ حدث خطأ في السيرفر أثناء معالجة البحث.")

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """استقبل الفيديو من الأدمن واحفظه."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID or 'waiting_for_video' not in context.user_data:
        return

    tmdb_id = context.user_data['waiting_for_video']
    title = context.user_data['waiting_title']
    
    # جلب معرف الملف
    file_id = update.message.video.file_id

    # الحفظ في قاعدة البيانات
    conn = sqlite3.connect('movies_db.sqlite')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO movies (tmdb_id, title, file_id) VALUES (?, ?, ?)", (tmdb_id, title, file_id))
    conn.commit()
    conn.close()

    del context.user_data['waiting_for_video']
    del context.user_data['waiting_title']
    
    await update.message.reply_text(f"✅ تم ربط وحفظ فيلم ({title}) بنجاح داخل تليجرام!")

def main() -> None:
    """تشغيل البوت."""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie))
    application.add_handler(MessageHandler(filters.VIDEO, receive_video))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
