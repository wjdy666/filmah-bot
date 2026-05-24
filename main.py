import os
import sys
import html
import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

if not BOT_TOKEN or not TMDB_API_KEY:
    logger.error("BOT_TOKEN or TMDB_API_KEY environment variables are missing.")
    sys.exit(1)


async def fetch_tmdb(endpoint: str, params: dict) -> dict:
    url = f"https://api.themoviedb.org/3{endpoint}"
    params["api_key"] = TMDB_API_KEY
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"TMDB API Error: {e}")
        return {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [
            InlineKeyboardButton("Search Movies", callback_data="search"),
            InlineKeyboardButton("Top Rated", callback_data="top_rated"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome! Choose an option below or directly type a movie name to search:",
        reply_markup=reply_markup,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "search":
        await query.edit_message_text(
            "Send me the name of the movie you want to search for:"
        )

    elif query.data == "top_rated":
        data = await fetch_tmdb("/movie/top_rated", {"language": "en-US", "page": 1})
        results = data.get("results")

        if not results:
            await query.edit_message_text("Could not fetch top-rated movies at this time.")
            return

        text = "🌟 <b>Top Rated Movies:</b>\n\n"
        for movie in results[:5]:
            title = movie.get("title") or "Unknown Title"
            rating = movie.get("vote_average") or 0.0
            release_date = movie.get("release_date") or ""
            year = release_date[:4] if release_date else "N/A"

            text += f"• <b>{html.escape(title)}</b> ({html.escape(year)}) - ⭐ {rating}/10\n"

        await query.edit_message_text(text, parse_mode="HTML")


async def search_movies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_input = update.message.text
    if not user_input:
        return

    data = await fetch_tmdb("/search/movie", {"query": user_input, "language": "en-US", "page": 1})
    results = data.get("results")

    if not results:
        await update.message.reply_text(f"No results found for '{html.escape(user_input)}'.")
        return

    text = f"🔍 <b>Search results for '{html.escape(user_input)}':</b>\n\n"
    for movie in results[:5]:
        title = movie.get("title") or "Unknown Title"
        rating = movie.get("vote_average") or 0.0
        release_date = movie.get("release_date") or ""
        year = release_date[:4] if release_date else "N/A"
        overview = movie.get("overview") or "No description available."
        overview_snippet = (overview[:100] + "...") if len(overview) > 100 else overview

        text += (
            f"🎬 <b>{html.escape(title)}</b> ({html.escape(year)})\n"
            f"⭐ {rating}/10\n"
            f"📝 {html.escape(overview_snippet)}\n\n"
        )

    await update.message.reply_text(text, parse_mode="HTML")


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movies))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
