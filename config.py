import logging
import os
import yt_dlp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === CONFIG ===
BOT_TOKEN = "7533322406:AAE9ZUjY2DBgTalBqAUIx4djFjkGa6dX6ZU"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# === COMMAND HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a YouTube URL (or any supported site link) and I’ll list available formats!"
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    msg = await update.message.reply_text("Fetching formats…")
    ydl_opts = {"quiet": True, "skip_download": True, "listformats": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        formats = info.get("formats", [])
        # Build inline keyboard
        keyboard = []
        for fmt in formats:
            code = fmt.get("format_id")
            desc = fmt.get("format_note", fmt.get("ext"))
            size = fmt.get("filesize") or fmt.get("filesize_approx") or 0
            label = f"{code} — {desc} ({size//1024//1024}MiB)"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"{url}|{code}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text("Select a format:", reply_markup=reply_markup)
    except Exception as e:
        logger.error("Error fetching formats: %s", e)
        await msg.edit_text("❌ Failed to fetch formats. Please check the URL and try again.")

async def download_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    url, fmt_code = query.data.split("|", 1)
    status_msg = await query.edit_message_text(f"Downloading format {fmt_code}…")
    # Prepare download options
    out_template = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    ydl_opts = {
        "format": fmt_code,
        "outtmpl": out_template,
        "quiet": True,
        "merge_output_format": "mp4",  # fallback container
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        await status_msg.edit_text("Uploading...")
        # Send video or audio file
        if filename.lower().endswith((".mp4", ".mkv", ".webm")):
            await query.message.reply_video(open(filename, "rb"))
        else:
            await query.message.reply_document(open(filename, "rb"))
        await status_msg.delete()
    except Exception as e:
        logger.error("Download error: %s", e)
        await status_msg.edit_text("❌ Download failed. Please try another format.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(download_format))
    app.run_polling()

if __name__ == "__main__":
    main()
