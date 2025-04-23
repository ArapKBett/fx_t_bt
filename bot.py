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
except FileNotFoundError:
    print("config.json not found.")
    exit(1)

application = Application.builder().token(config["telegram_token"]).build()
intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents)

pairs = PAIRS
granularity = config["granularity"]

async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("EUR", callback_data="eur_menu"), InlineKeyboardButton("USD", callback_data="usd_menu")],
        [InlineKeyboardButton("JPY", callback_data="jpy_menu"), InlineKeyboardButton("GBP", callback_data="gbp_menu")],
        [InlineKeyboardButton("CHF", callback_data="chf_menu"), InlineKeyboardButton("AUD", callback_data="aud_menu")],
        [InlineKeyboardButton("CAD", callback_data="cad_menu"), InlineKeyboardButton("NZD", callback_data="nzd_menu")],
        [InlineKeyboardButton("BTC", callback_data="btc_menu"), InlineKeyboardButton("Compare", callback_data="compare_all")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Elite Forex Bot: Choose a currency or compare pairs:", reply_markup=reply_markup)

async def show_submenu(query, base_currency):
    keyboard = [
        [InlineKeyboardButton("Predictions", callback_data=f"{base_currency.lower()}_predictions")],
        [InlineKeyboardButton("Charts", callback_data=f"{base_currency.lower()}_charts")],
        [InlineKeyboardButton("Compare", callback_data=f"{base_currency.lower()}_compare")],
        [InlineKeyboardButton("Back", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"{base_currency} Pairs:", reply_markup=reply_markup)

async def button(update, context):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data.endswith("_menu"):
            base_currency = query.data.split("_")[0].upper()
            await show_submenu(query, base_currency)
            return
        
        if query.data == "back_to_main":
            await start(update, context)
            return
        
        if query.data.startswith("back_to_"):
            base_currency = query.data.split("_")[2].upper()
            await show_submenu(query, base_currency)
            return
        
        base_currency = query.data.split("_")[0].upper()
        filtered_pairs = [pair for pair in pairs if pair.startswith(base_currency + "_")]
        signals = get_all_signals(filtered_pairs, granularity)
        
        if query.data.endswith("_predictions"):
            message = f"{base_currency} Pairs Predictions:\n\n"
            for pair, data in signals.items():
                message += f"{pair}:\n"
                message += f"  Entry: {data['df']['close'].iloc[-1]:.5f}\n"
                message += f"  SL: {data['sl']:.5f}\n"
                message += f"  TP: {data['tp']:.5f}\n"
                message += f"  {data['analysis']}\n"
                message += f"  Rec: {data['recommendation']} ({data['confidence']*100:.0f}%)\n\n"
            keyboard = [[InlineKeyboardButton("Back", callback_data=f"back_to_{base_currency.lower()}")]]
            await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif query.data.endswith("_charts"):
            for pair, data in signals.items():
                if not data["df"].empty:
                    generate_chart(data["df"], pair)
                    caption = f"{pair}: {data['recommendation']} ({data['confidence']*100:.0f}%)"
                    with open(f"chart_{pair.replace('_', '')}.png", "rb") as photo:
                        await query.message.reply_photo(photo=photo, caption=caption)
            keyboard = [[InlineKeyboardButton("Back", callback_data=f"back_to_{base_currency.lower()}")]]
            await query.edit_message_text(f"Charts for {base_currency} pairs sent!", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif query.data.endswith("_compare"):
            generate_comparison_chart(signals)
            with open("comparison_chart.png", "rb") as photo:
                await query.message.reply_photo(photo=photo)
            keyboard = [[InlineKeyboardButton("Back", callback_data=f"back_to_{base_currency.lower()}")]]
            await query.edit_message_text(f"Comparison for {base_currency} pairs!", reply_markup=InlineKeyboardMarkup(keyboard))
        
        elif query.data == "compare_all":
            signals = get_all_signals(pairs, granularity)
            generate_comparison_chart(signals)
            with open("comparison_chart.png", "rb") as photo:
                await query.message.reply_photo(photo=photo)
            keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_main")]]
            await query.edit_message_text("Comparison chart sent!", reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Button error: {e}")
        await query.edit_message_text("Error occurred. Try again.")

async def manual_update(update, context):
    signals = get_all_signals(pairs, granularity)
    message = "Manual Update:\n\n"
    for pair, data in signals.items():
        message += f"{pair}: {data['signal']} ({data['strength']:.2f}%)\n"
        message += f"  SL: {data['sl']:.5f}, TP: {data['tp']:.5f}\n"
        message += f"  {data['analysis']}\n"
        message += f"  Rec: {data['recommendation']} ({data['confidence']*100:.0f}%)\n\n"
    await update.message.reply_text(message)
    generate_comparison_chart(signals)
    with open("comparison_chart.png", "rb") as photo:
        await update.message.reply_photo(photo=photo)

@tasks.loop(minutes=15)
async def post_update():
    try:
        channel = discord_client.get_channel(int(config["discord_channel_id"]))
        signals = get_all_signals(pairs, granularity)
        
        for pair, data in signals.items():
            if not data["df"].empty:
                generate_chart(data["df"], pair)
                message = f"**{pair}: {data['signal']} ({data['strength']:.2f}%)**\n"
                message += f"SL: {data['sl']:.5f}, TP: {data['tp']:.5f}\n"
                message += f"{data['analysis']}\n"
                message += f"Rec: {data['recommendation']} ({data['confidence']*100:.0f}%)\n"
                with open(f"chart_{pair.replace('_', '')}.png", "rb") as photo:
                    await channel.send(message, file=discord.File(photo))
        
        generate_comparison_chart(signals)
        with open("comparison_chart.png", "rb") as photo:
            await channel.send("**Trend Comparison**", file=discord.File(photo))
    except Exception as e:
        logger.error(f"Discord update error: {e}")

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
        logger.error(f"Main error: {e}")
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
