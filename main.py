import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# مفاتيح البيئة
BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

BASE_URL = "https://api.themoviedb.org/3"


# بحث في TMDB
def search_tmdb(query):
    url = f"{BASE_URL}/search/multi"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "ar"
    }
    return requests.get(url, params=params).json().get("results", [])


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 بحث", callback_data="search")],
        [InlineKeyboardButton("⭐ الأعلى", callback_data="top")]
    ]

    await update.message.reply_text(
        "هلا بك في فِلْمَه 🎥",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# أزرار الكيبورد
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "search":
        await query.edit_message_text("اكتب اسم فيلم أو مسلسل 🎬")

    elif query.data == "top":
        url = f"{BASE_URL}/movie/top_rated"
        r = requests.get(url, params={
            "api_key": TMDB_API_KEY,
            "language": "ar"
        }).json()

        msg = "⭐ الأعلى تقييمًا:\n\n"
        for m in r.get("results", [])[:10]:
            msg += f"🎬 {m.get('title','')} ⭐ {m.get('vote_average',0)}\n"

        await query.edit_message_text(msg)


# معالجة الرسائل
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    results = search_tmdb(text)

    if not results:
        await update.message.reply_text("ما لقيت نتائج 😕")
        return

    m = results[0]
    title = m.get("title") or m.get("name")
    overview = m.get("overview", "")
    rating = m.get("vote_average", 0)

    await update.message.reply_text(
        f"🎬 {title}\n⭐ {rating}\n\n{overview}"
    )


# تشغيل البوت
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

print("Bot is running...")
app.run_polling()
