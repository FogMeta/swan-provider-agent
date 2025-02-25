import asyncio
import os
import telegramify_markdown
import telegramify_markdown.customize as customize
from telegram import Update, MessageEntity
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import logging
from dotenv import load_dotenv
from agent import process_question  # Import the agent function
customize.strict_markdown = False
# Configure logging.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the /start command is issued."""
    await update.message.reply_text("Welcome to the SwanChain Bot! Ask me any question about Swan Chain.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process user messages by calling the agent."""
    user_question = update.message.text
    await update.message.reply_text("Processing your question, please wait...")
    try:
        # Call the process_question function from the agent module.
        answer = await process_question(user_question)
        logging.info("answer: %s", answer)
    except Exception as e:
        logging.error("Error processing question: %s", e)
        answer = "There was an error processing your question. Please try again later."
    chunk_size = 4096
    for i in range(0, len(answer), chunk_size):
        await update.message.reply_text(text=telegramify_markdown.markdownify(answer[i:i + chunk_size]),
                                        parse_mode="MarkdownV2")


if __name__ == '__main__':
    load_dotenv()  # Load environment variables from .env file
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Get the token from the .env file
    logging.info("TELEGRAM_BOT_TOKEN: %s", TELEGRAM_BOT_TOKEN)
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.Entity(MessageEntity.MENTION), handle_message))
    application.run_polling()
