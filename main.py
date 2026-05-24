import os
import logging
import sqlite3
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد الـ Logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# الإعدادات الأساسية
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TMDB_API_KEY = os.environ.get("API_KEY")
ADMIN_ID = 1436656132  # الآيدي الخاص بك كأدمن ومطور

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
    welcome = (
        "🎬 **أهلاً بك في بوت الأفلام والمسلسلات للمشاهدة المباشرة!**\n\n"
        "🍿 أرسل اسم أي فيلم أو مسلسل، وسأحضره لك كاملاً للمشاهدة داخل تليجرام فوراً بدون روابط خارجية!"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    movie_name = update.message.text
    user_id = update.effective_user.id
    await update.message.reply_chat_action(action="upload_photo")

    if not TMDB_API_KEY:
        await update.message.reply_text("⚠️ خطأ: لم يتم ضبط الـ API_KEY في الإعدادات.")
        return

    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={movie_name}&language=ar"
    
    try:
        response = requests.get(search_url).json()
        results = response.get('results', [])

        if not results:
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

        # فحص قاعدة البيانات
        conn = sqlite3.connect('movies_db.sqlite')
        cursor = conn.cursor()
        cursor.execute("SELECT file_id FROM movies WHERE tmdb_id = ?", (tmdb_id,))
        row = cursor.fetchone()
        conn.close()

        # أزرار الإدارة للأدمن تظهر دائماً تحت البطاقة للتحكم الكامل
        keyboard = []
        if user_id == ADMIN_ID:
            if row:
                keyboard.append([InlineKeyboardButton("🗑️ مسح الفيديو الحالي", callback_data=f"del_{tmdb_id}_{title[:20]}")])
            else:
                keyboard.append([InlineKeyboardButton("📥 ربط ملف فيديو", callback_data=f"link_{tmdb_id}_{title[:20]}")])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        if poster_url:
            await update.message.reply_photo(photo=poster_url, caption=caption, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(caption, reply_markup=reply_markup, parse_mode="Markdown")
        
        # إذا كان الفيلم موجوداً نرسل الفيديو فوراً للمشاهدة
        if row:
            file_id = row[0]
            await update.message.reply_video(video=file_id, caption=f"🍿 مشاهدة ممتعة لـ: {title}")
        elif user_id != ADMIN_ID:
            await update.message.reply_text("⏳ **هذا الفيلم غير متوفر حالياً، سيقوم الأدمن بتوفيره قريباً!**")

    except Exception as e:
        logger.error(f"Search Error: {e}")
        await update.message.reply_text("❌ حدث خطأ أثناء معالجة البحث.")

async def admin_delete_movie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """أمر مسح مباشر عبر الكتابة للأدمن."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("⚠️ اكتب اسم الفيلم المراد حذفه بعد الأمر. مثال:\n`/delete اسم الفيلم`", parse_mode="Markdown")
        return

    movie_name = " ".join(context.args)
    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={movie_name}&language=ar"
    
    try:
        response = requests.get(search_url).json()
        results = response.get('results', [])

        if not results:
            await update.message.reply_text("❌ لم يتم العثور على الفيلم لحذفه من قاعدة البيانات.")
            return

        item = results[0]
        tmdb_id = str(item.get('id'))
        title = item.get('title') or item.get('name')

        conn = sqlite3.connect('movies_db.sqlite')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movies WHERE tmdb_id = ?", (tmdb_id,))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"🗑️ تم حذف ملف الفيديو المرتبط بـ ({title}) بنجاح! يمكنك الآن البحث عنه وربطه من جديد.")
    except Exception as e:
        await update.message.reply_text("❌ حدث خطأ أثناء محاولة الحذف.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """معالجة ضغط الأزرار الشفافة للأدمن."""
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return

    data = query.data
    if data.startswith("link_"):
        _, tmdb_id, movie_title = data.split("_", 2)
        context.user_data['waiting_for_video'] = tmdb_id
        context.user_data['waiting_title'] = movie_title
        await query.message.reply_text(f"🔄 وضع الربط نشط لـ: **{movie_title}**\nقم الآن بعمل توجيه (Forward) لملف الفيلم المُراد ربطه إلى هنا مباشرة.", parse_mode="Markdown")
    
    elif data.startswith("del_"):
        _, tmdb_id, movie_title = data.split("_", 2)
        conn = sqlite3.connect('movies_db.sqlite')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movies WHERE tmdb_id = ?", (tmdb_id,))
        conn.commit()
        conn.close()
        await query.message.reply_text(f"🗑️ تم حذف الفيديو المرتبط بـ ({movie_title}) بنجاح من قاعدة البيانات.")

async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != ADMIN_ID or 'waiting_for_video' not in context.user_data:
        return

    tmdb_id = context.user_data['waiting_for_video']
    title = context.user_data['waiting_title']
    file_id = update.message.video.file_id

    conn = sqlite3.connect('movies_db.sqlite')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO movies (tmdb_id, title, file_id) VALUES (?, ?, ?)", (tmdb_id, title, file_id))
    conn.commit()
    conn.close()

    del context.user_data['waiting_for_video']
    del context.user_data['waiting_title']
    
    await update.message.reply_text(f"✅ تم ربط وحفظ فيلم ({title}) بالفيديو الجديد بنجاح!")

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("delete", admin_delete_movie))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie))
    application.add_handler(Update.handler_class(handle_callback))
    application.add_handler(MessageHandler(filters.VIDEO, receive_video))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
