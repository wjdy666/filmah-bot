import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# 🔑 Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

# 🧪 اختبار التوكن (مهم للتشخيص)
print("BOT_TOKEN =", BOT_TOKEN)
print("TMDB_API_KEY =", TMDB_API_KEY)

BASE_URL = "https://api.themoviedb.org/3"


# 🔍 بحث TMDB
def search_tmdb(query):
    url = f"{BASE_URL}/search/multi"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "en-US"
    }
    try:
        return requests.get(url, params=params, timeout=10).json().get("results", [])
    except Exception as e:
        print("Error:", e)
        return []


# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 Search", callback_data="search")],
        [InlineKeyboardButton("⭐ Top Rated", callback_data="top")]
    ]

    await update.message.reply_text(
        "Welcome to Movie Bot 🎥",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# الأزرار
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "search":
        await query.edit_message_text("Send movie or series name 🎬")

    elif query.data == "top":
        url = f"{BASE_URL}/movie/top_rated"
        r = requests.get(url, params={
            "api_key": TMDB_API_KEY,
            "language": "en-US"
        }).json()

        msg = "⭐ Top Rated Movies:\n\n"

        for m in r.get("results", [])[:10]:
            msg += f"🎬 {m.get('title','N/A')} ⭐ {m.get('vote_average',0)}\n"

        await query.edit_message_text(msg)


# الرسائل
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    results = search_tmdb(text)

    if not results:
        await update.message.reply_text("No results found 😕")
        return

    m = results[0]
    title = m.get("title") or m.get("name")
    overview = m.get("overview", "No description")
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
