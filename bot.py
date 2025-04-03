import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
import discord
from discord.ext import tasks
import asyncio
import json
import logging

from trading_strategy import fetch_data, generate_signal, place_order, get_all_signals, PAIRS, MAJOR_CURRENCIES
from graphics import generate_chart, generate_comparison_chart

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    with open("config.json", "r") as f:
        config = json.load(f)
except json.JSONDecodeError as e:
    print(f"Error loading config.json: {e}")
    exit(1)

application = Application.builder().token(config["telegram_token"]).build()
intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents)

pairs = PAIRS  # All 28 pairs from trading_strategy.py
granularity = config["granularity"]

async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("EUR Pairs", callback_data="eur_menu"),
         InlineKeyboardButton("USD Pairs", callback_data="usd_menu")],
        [InlineKeyboardButton("JPY Pairs", callback_data="jpy_menu"),
         InlineKeyboardButton("GBP Pairs", callback_data="gbp_menu")],
        [InlineKeyboardButton("CHF Pairs", callback_data="chf_menu"),
         InlineKeyboardButton("AUD Pairs", callback_data="aud_menu")],
        [InlineKeyboardButton("CAD Pairs", callback_data="cad_menu"),
         InlineKeyboardButton("NZD Pairs", callback_data="nzd_menu")],
        [InlineKeyboardButton("Compare All", callback_data="compare_all")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome to the Forex Bot! Choose a currency or compare all pairs:", reply_markup=reply_markup)

async def show_submenu(query, base_currency):
    keyboard = [
        [InlineKeyboardButton("Predictions", callback_data=f"{base_currency.lower()}_predictions")],
        [InlineKeyboardButton("View Charts", callback_data=f"{base_currency.lower()}_charts")],
        [InlineKeyboardButton("Compare All", callback_data=f"{base_currency.lower()}_compare")],
        [InlineKeyboardButton("Back", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"{base_currency} Pairs Menu:", reply_markup=reply_markup)

async def button(update, context):
    query = update.callback_query
    await query.answer()
    
    try:
        # Handle main menu
        base_currency = None
        if query.data.endswith("_menu"):
            base_currency = query.data.split("_")[0].upper()
            await show_submenu(query, base_currency)
            return
        
        # Handle back to main menu
        if query.data == "back_to_main":
            await start(update, context)
            return
        
        # Handle back to submenu after results
        if query.data.startswith("back_to_"):
            base_currency = query.data.split("_")[2].upper()
            await show_submenu(query, base_currency)
            return
        
        # Handle submenu actions
        elif query.data.endswith("_predictions") or query.data.endswith("_charts") or query.data.endswith("_compare"):
            base_currency = query.data.split("_")[0].upper()
            filtered_pairs = [pair for pair in pairs if pair.startswith(base_currency + "_")]
            signals = get_all_signals(filtered_pairs, granularity)
            
            if query.data.endswith("_predictions"):
                message = f"{base_currency} Pairs Predictions:\n\n"
                for pair, data in signals.items():
                    message += f"{pair}:\n"
                    message += f"  Entry: {data['df']['close'].iloc[-1]:.5f}\n"
                    message += f"  SL: {data['sl']:.5f}\n"
                    message += f"  TP: {data['tp']:.5f}\n\n"
                keyboard = [[InlineKeyboardButton("Back", callback_data=f"back_to_{base_currency.lower()}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(message, reply_markup=reply_markup)
            
            elif query.data.endswith("_charts"):
                for pair, data in signals.items():
                    generate_chart(data["df"], pair)
                    rsi = data["df"]["rsi"].iloc[-1] if not data["df"].empty else 0.0
                    macd = data["df"]["macd_hist"].iloc[-1] if not data["df"].empty else 0.0
                    caption = f"{pair}: {data['analysis']}"
                    with open(f"chart_{pair.replace('_', '')}.png", "rb") as photo:
                        await query.message.reply_photo(photo=photo, caption=caption)
                keyboard = [[InlineKeyboardButton("Back", callback_data=f"back_to_{base_currency.lower()}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(f"Charts sent for {base_currency} pairs!", reply_markup=reply_markup)
            
            elif query.data.endswith("_compare"):
                generate_comparison_chart(signals)
                with open("comparison_chart.png", "rb") as photo:
                    await query.message.reply_photo(photo=photo)
                keyboard = [[InlineKeyboardButton("Back", callback_data=f"back_to_{base_currency.lower()}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(f"Comparison chart sent for {base_currency} pairs!", reply_markup=reply_markup)
        
        # Handle top-level Compare All
        elif query.data == "compare_all":
            signals = get_all_signals(pairs, granularity)
            generate_comparison_chart(signals)
            with open("comparison_chart.png", "rb") as photo:
                await query.message.reply_photo(photo=photo)
            keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Comparison chart sent for all 28 pairs!", reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in button handler: {e}")
        await query.edit_message_text("An error occurred. Please try again.")

async def manual_update(update, context):
    signals = get_all_signals(pairs, granularity)
    message = "Manual Update and Analysis:\n\n"
    for pair, data in signals.items():
        rsi = data["df"]["rsi"].iloc[-1] if not data["df"].empty else 0.0
        macd = data["df"]["macd_hist"].iloc[-1] if not data["df"].empty else 0.0
        message += f"{pair}: {data['signal']} (Strength: {data['strength']:.2f}%, RSI: {rsi:.2f}, MACD: {macd:.3f})\n"
        message += f"  SL: {data['sl']:.5f}, TP: {data['tp']:.5f}\n"
        message += f"  {data['analysis']}\n\n"
    await update.message.reply_text(message)
    generate_comparison_chart(signals)
    with open("comparison_chart.png", "rb") as photo:
        await update.message.reply_photo(photo=photo)

@tasks.loop(minutes=15)
async def post_update():
    try:
        channel = discord_client.get_channel(int(config["discord_channel_id"]))
        if not channel:
            logger.error("Invalid Discord channel ID")
            return
        signals = get_all_signals(pairs, granularity)
        
        for pair, data in signals.items():
            generate_chart(data["df"], pair)
            rsi = data["df"]["rsi"].iloc[-1] if not data["df"].empty else 0.0
            macd = data["df"]["macd_hist"].iloc[-1] if not data["df"].empty else 0.0
            message = f"{pair}: {data['signal']} (Strength: {data['strength']:.2f}%, RSI: {rsi:.2f}, MACD: {macd:.3f})\n"
            message += f"SL: {data['sl']:.5f}, TP: {data['tp']:.5f}\n"
            message += f"{data['analysis']}"
            with open(f"chart_{pair.replace('_', '')}.png", "rb") as photo:
                await channel.send(message, file=discord.File(photo))
        
        generate_comparison_chart(signals)
        with open("comparison_chart.png", "rb") as photo:
            await channel.send("Trend Strength Comparison:", file=discord.File(photo))
    except Exception as e:
        logger.error(f"Error in Discord post_update: {e}")

@discord_client.event
async def on_ready():
    print(f"Logged in as {discord_client.user}")
    if not post_update.is_running():
        post_update.start()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("update", manual_update))
application.add_handler(CallbackQueryHandler(button))

async def main():
    await application.initialize()
    await application.start()
    telegram_task = asyncio.create_task(application.updater.start_polling())
    discord_task = discord_client.start(config["discord_token"])
    try:
        await asyncio.gather(telegram_task, discord_task)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        if application.updater.running:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
        if not discord_client.is_closed():
            await discord_client.close()
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())