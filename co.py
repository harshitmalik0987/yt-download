import os
import asyncio
from yt_dlp import YoutubeDL
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants as tg_constants
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

API_TOKEN = '7952616197:AAGQ8kJBVUcL17cUHs8bXLbPGTe9WRxhe20'
DOWNLOAD_DIR = 'downloads'
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Download Video", callback_data="choose_video"),
         InlineKeyboardButton("Download Audio (MP3)", callback_data="choose_audio")]
    ]
    text = "👋 Welcome! Send a YouTube or other video URL and choose download format."
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith('http'):
        context.chat_data['url'] = text
        ydl_opts = {"quiet": True, "no_warnings": True, "nocheckcertificate": True}
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(text, download=False)
        except Exception:
            await update.message.reply_text("❌ Failed to fetch video info.")
            return
        context.chat_data['info'] = info
        keyboard = [
            [InlineKeyboardButton("📹 Video (MP4)", callback_data="choose_video"),
             InlineKeyboardButton("🎵 Audio (MP3)", callback_data="choose_audio")]
        ]
        await update.message.reply_text(
            f"🎬 *{info.get('title', 'Video')}*\nChoose format:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=tg_constants.ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("Please send a valid video URL.")

def build_quality_buttons(info):
    formats = info.get('formats', [])
    qualities = {}
    for f in formats:
        if f.get('vcodec') != 'none' and f.get('acodec') == 'none':
            height = f.get('height') or 0
            size = f.get('filesize') or 0
            if height and size:
                qualities[height] = size
    buttons = []
    for height in sorted(qualities.keys(), reverse=True):
        size_mb = qualities[height] / (1024 * 1024)
        label = f"{height}p ({size_mb:.1f} MB)"
        buttons.append([InlineKeyboardButton(label, callback_data=f"dl_video_{height}")])
    buttons.append([InlineKeyboardButton("Cancel ❌", callback_data="cancel")])
    return InlineKeyboardMarkup(buttons)

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    info = context.chat_data.get('info', {})
    
    if data == "choose_video":
        if not info:
            await query.edit_message_text("Error: No video info found.")
            return
        keyboard = build_quality_buttons(info)
        await query.edit_message_text("Select video quality:", reply_markup=keyboard)

    elif data.startswith("dl_video_"):
        height = int(data.split("_")[-1])
        await query.edit_message_text(f"Downloading {height}p video...")
        await download_video(update, context, height)

    elif data == "choose_audio":
        await query.edit_message_text("Downloading audio (MP3)...")
        await download_audio(update, context)

    elif data == "cancel":
        await query.edit_message_text("Operation canceled.")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE, height: int):
    chat_id = update.effective_chat.id
    url = context.chat_data.get('url')
    if not url:
        await context.bot.send_message(chat_id, "Error: URL not found.")
        return

    ydl_opts = {
        'format': f"bestvideo[height={height}]+bestaudio/best",
        'merge_output_format': 'mp4',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
    }
    loop = asyncio.get_running_loop()
    try:
        file_path = await loop.run_in_executor(None, run_yt_dlp, url, ydl_opts)
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Download error: {e}")
        return

    if not file_path or not os.path.exists(file_path):
        await context.bot.send_message(chat_id, "❌ Failed to download.")
        return

    try:
        await context.bot.send_video(chat_id=chat_id, video=open(file_path, 'rb'), supports_streaming=True)
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Error sending video: {e}")
    finally:
        os.remove(file_path)

async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    url = context.chat_data.get('url')
    if not url:
        await context.bot.send_message(chat_id, "Error: URL not found.")
        return

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'quiet': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    loop = asyncio.get_running_loop()
    try:
        file_path = await loop.run_in_executor(None, run_yt_dlp, url, ydl_opts)
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Download error: {e}")
        return

    if not file_path or not os.path.exists(file_path):
        await context.bot.send_message(chat_id, "❌ Failed to download audio.")
        return

    try:
        await context.bot.send_audio(chat_id=chat_id, audio=open(file_path, 'rb'))
    except Exception as e:
        await context.bot.send_message(chat_id, f"❌ Error sending audio: {e}")
    finally:
        os.remove(file_path)

def run_yt_dlp(url, ydl_opts):
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        ext = info.get('ext')
        if ext == 'webm' and os.path.exists(filename.replace('.webm', '.mp3')):
            filename = filename.replace('.webm', '.mp3')
        return filename

def main():
    app = ApplicationBuilder().token(API_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_choice))
    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
