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
        [InlineKeyboardButton("View Chart", callback_data="chart")]
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

# Discord task
@tasks.loop(minutes=60)  # Check every hour
async def check_signal():
    channel = discord_client.get_channel(int(config["discord_channel_id"]))
    df = fetch_data(pair, granularity)
    signal = generate_signal(df)
    await channel.send(f"Current signal for {pair}: {signal}")
    
    generate_chart(df, pair)
    with open("chart.png", "rb") as photo:
        await channel.send(file=discord.File(photo))

@discord_client.event
async def on_ready():
    print(f"Logged in as {discord_client.user}")
    if not check_signal.is_running():
        check_signal.start()

# Register Telegram handlers
dp.add_handler(CommandHandler("start", start))
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
