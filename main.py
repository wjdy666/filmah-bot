import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

BASE_URL = "https://api.themoviedb.org/3"

def search_tmdb(query):
    url = f"{BASE_URL}/search/multi"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "ar"
    }
    return requests.get(url, params=params).json().get("results", [])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 بحث", callback_data="search")],
        [InlineKeyboardButton("⭐ الأفضل", callback_data="top")]
    ]

    await update.message.reply_text(
        "هلا بك في فِلْمَه 🎥",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "search":
        await q.edit_message_text("اكتب اسم فيلم أو مسلسل 🎬")

    elif q.data == "top":
        url = f"{BASE_URL}/movie/top_rated"
        r = requests.get(url, params={"api_key": TMDB_API_KEY, "language": "ar"}).json()

        msg = "⭐ الأفضل:\n\n"
        for m in r["results"][:10]:
            msg += f"🎬 {m['title']} ⭐ {m['vote_average']}\n"

        await q.edit_message_text(msg)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text
    results = search_tmdb(q)

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

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

print("Bot running...")
app.run_polling()
