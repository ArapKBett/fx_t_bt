import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler
import discord
from discord.ext import tasks
import asyncio
import json
from trading_strategy import fetch_data, generate_signal, place_order
from graphics import generate_chart

# Load config
with open("config.json", "r") as f:
    config = json.load(f)

# Telegram setup
telegram_bot = telegram.Bot(token=config["telegram_token"])
updater = Updater(config["telegram_token"], use_context=True)
dp = updater.dispatcher

# Discord setup
intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents)

# Shared state
pair = config["pair"]
granularity = config["granularity"]

# Telegram handlers
def start(update, context):
    keyboard = [
        [InlineKeyboardButton("Check Signal", callback_data="signal")],
        [InlineKeyboardButton("Place Trade", callback_data="trade")],
        [InlineKeyboardButton("View Chart", callback_data="chart")],
        [InlineKeyboardButton("Start Hourly Updates", callback_data="start_updates")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Welcome to the Forex Bot! Choose an option:", reply_markup=reply_markup)

def button(update, context):
    query = update.callback_query
    query.answer()
    
    df = fetch_data(pair, granularity)
    signal = generate_signal(df)
    
    if query.data == "signal":
        query.edit_message_text(f"Current signal for {pair}: {signal}")
    elif query.data == "trade":
        result = place_order(signal, pair)
        query.edit_message_text(result)
    elif query.data == "chart":
        generate_chart(df, pair)
        with open("chart.png", "rb") as photo:
            query.message.reply_photo(photo=photo)
        query.edit_message_text("Chart sent!")
    elif query.data == "start_updates":
        query.edit_message_text("Hourly updates started! Check every 15 minutes.")
        # We'll simulate this with a manual trigger since Telegram doesn't run loops natively

def manual_update(update, context):
    df = fetch_data(pair, granularity)
    signal = generate_signal(df)
    generate_chart(df, pair)
    with open("chart.png", "rb") as photo:
        update.message.reply_photo(photo=photo)
    update.message.reply_text(f"Manual update for {pair}: Signal = {signal}")

# Discord task - 4 images per hour (every 15 minutes)
@tasks.loop(minutes=15)
async def post_chart():
    channel = discord_client.get_channel(int(config["discord_channel_id"]))
    df = fetch_data(pair, granularity)
    signal = generate_signal(df)
    generate_chart(df, pair)
    with open("chart.png", "rb") as photo:
        await channel.send(f"Update for {pair}: Signal = {signal}", file=discord.File(photo))

@discord_client.event
async def on_ready():
    print(f"Logged in as {discord_client.user}")
    if not post_chart.is_running():
        post_chart.start()

# Register Telegram handlers
dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("update", manual_update))  # Manual trigger for Telegram
dp.add_handler(CallbackQueryHandler(button))

# Run both bots
async def main():
    # Start Telegram bot
    updater.start_polling()
    
    # Start Discord bot
    await discord_client.start(config["discord_token"])

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
