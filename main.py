import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

BASE_URL = "https://api.themoviedb.org/3"


# Search function
def search_tmdb(query):
    url = f"{BASE_URL}/search/multi"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "en-US"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        return response.json().get("results", [])
    except Exception as e:
        print("Search error:", e)
        return []


# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎬 Search", callback_data="search")],
        [InlineKeyboardButton("⭐ Top Rated", callback_data="top")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome to Movie Bot 🎥",
        reply_markup=reply_markup
    )


# Button handler
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "search":
        await query.edit_message_text("Send a movie or series name 🎬")

    elif query.data == "top":
        url = f"{BASE_URL}/movie/top_rated"
        response = requests.get(url, params={
            "api_key": TMDB_API_KEY,
            "language": "en-US"
        }).json()

        message = "⭐ Top Rated Movies:\n\n"

        for movie in response.get("results", [])[:10]:
            title = movie.get("title", "N/A")
            rating = movie.get("vote_average", 0)
            message += f"🎬 {title} ⭐ {rating}\n"

        await query.edit_message_text(message)


# Text handler
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    results = search_tmdb(text)

    if not results:
        await update.message.reply_text("No results found 😕")
        return

    movie = results[0]
    title = movie.get("title") or movie.get("name")
    overview = movie.get("overview", "No description available")
    rating = movie.get("vote_average", 0)

    await update.message.reply_text(
        f"🎬 {title}\n⭐ {rating}\n\n{overview}"
    )


# Run bot
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

print("Bot is running...")
app.run_polling()
