import pandas as pd
import requests
import json
import numpy as np
from datetime import datetime, time

with open("config.json", "r") as f:
    config = json.load(f)

BASE_URL = "https://api-fxpractice.oanda.com/v3"
HEADERS = {"Authorization": f"Bearer {config['oanda_api_token']}", "Content-Type": "application/json"}

MAJOR_CURRENCIES = ["EUR", "USD", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD"]

PAIRS = [
    "EUR_USD", "EUR_JPY", "EUR_GBP", "EUR_CHF", "EUR_AUD", "EUR_CAD", "EUR_NZD",
    "USD_JPY", "USD_CHF", "USD_CAD",
    "GBP_USD", "GBP_JPY", "GBP_CHF", "GBP_AUD", "GBP_CAD", "GBP_NZD",
    "CHF_JPY",
    "AUD_USD", "AUD_JPY", "AUD_CAD", "AUD_NZD",
    "CAD_JPY", "CAD_CHF",
    "NZD_USD", "NZD_JPY", "NZD_CAD",
    "BTC_USD"
]

def fetch_data(pair, granularity="H1", count=500):
    try:
        url = f"{BASE_URL}/instruments/{pair}/candles"
        params = {"count": count, "granularity": granularity, "price": "MBA"}
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        if "candles" not in data or not data["candles"]:
            print(f"No candle data returned for {pair}")
            return pd.DataFrame()
        df = pd.DataFrame([{
            "time": candle["time"],
            "close": float(candle["mid"]["c"]),
            "high": float(candle["mid"]["h"]),
            "low": float(candle["mid"]["l"])
        } for candle in data["candles"]])
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        if df["time"].isna().any():
            print(f"Invalid timestamp data for {pair}")
            return pd.DataFrame()
        df.set_index("time", inplace=True)
        return df[["close", "high", "low"]]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {pair}: {e.response.text if e.response else e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Unexpected error fetching data for {pair}: {e}")
        return pd.DataFrame()

def detect_market_structure(df):
    if df.empty or len(df) < 6:
        return "Unknown"
    df["swing_high"] = df["high"].rolling(window=5, center=True).max()
    df["swing_low"] = df["low"].rolling(window=5, center=True).min()
    latest_high = df["swing_high"].iloc[-1]
    latest_low = df["swing_low"].iloc[-1]
    prev_high = df["swing_high"].iloc[-6]
    prev_low = df["swing_low"].iloc[-6]
    if pd.isna([latest_high, latest_low, prev_high, prev_low]).any():
        return "Insufficient data"
    if latest_high > prev_high and latest_low > prev_low:
        return "Bullish (HH, HL)"
    elif latest_high < prev_high and latest_low < prev_low:
        return "Bearish (LH, LL)"
    return "Consolidation"

def detect_order_blocks(df):
    if df.empty or len(df) < 3:
        return "No data"
    df["range"] = df["high"] - df["low"]
    small_range = df["range"].rolling(window=3).mean() < df["range"].mean() * 0.5
    reversal = df["close"].diff().shift(-1) > df["range"].mean()
    order_block = small_range & reversal
    if order_block.iloc[-2]:
        return f"Order Block at {df['close'].iloc[-2]:.5f}"
    return "No recent Order Block"

def detect_liquidity_zones(df):
    if df.empty or len(df) < 5:
        return "No data"
    latest_swing_high = df["swing_high"].iloc[-1]
    latest_swing_low = df["swing_low"].iloc[-1]
    current_price = df["close"].iloc[-1]
    if pd.isna([latest_swing_high, latest_swing_low, current_price]).any():
        return "Insufficient data"
    range_size = latest_swing_high - latest_swing_low
    if current_price < latest_swing_high + range_size * 0.1:
        return f"Liquidity Zone above at {latest_swing_high:.5f}"
    elif current_price > latest_swing_low - range_size * 0.1:
        return f"Liquidity Zone below at {latest_swing_low:.5f}"
    return "No clear Liquidity Zone"

def detect_fair_value_gaps(df):
    if df.empty or len(df) < 3:
        return "No data"
    df["gap"] = df["high"].shift(1) - df["low"]
    fvg = df["gap"] > df["range"].mean() * 1.5
    if fvg.iloc[-2]:
        return f"FVG between {df['high'].iloc[-3]:.5f} and {df['low'].iloc[-2]:.5f}"
    return "No recent FVG"

def in_killzone(timestamp):
    if pd.isna(timestamp):
        return "Unknown"
    t = timestamp.time()
    london_open = (time(8, 0), time(11, 0))
    ny_open = (time(13, 0), time(16, 0))
    if london_open[0] <= t <= london_open[1]:
        return "In London Killzone"
    elif ny_open[0] <= t <= ny_open[1]:
        return "In NY Killzone"
    return "Outside Killzone"

def calculate_indicators(df):
    if df.empty or len(df) < 200:
        return df
    df["sma50"] = df["close"].rolling(window=50).mean()
    df["sma200"] = df["close"].rolling(window=200).mean()
    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    df["range"] = df["high"] - df["low"]
    df["atr"] = df["range"].rolling(window=14).mean()
    df["trend_strength"] = abs(df["sma50"] - df["sma200"]) / df["sma200"] * 100
    return df

def generate_signal(df):
    if df.empty or len(df) < 200:
        return "HOLD", 0.0, 0.0, 0.0, "Insufficient data for analysis.", "Wait for more data to confirm a trend."
    
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    price_change = (latest["close"] - prev["close"]) / prev["close"] * 100
    
    entry = latest["close"]
    sl_long = entry - (latest["atr"] * 1.5)
    tp_long = entry + (latest["atr"] * 3)
    sl_short = entry + (latest["atr"] * 1.5)
    tp_short = entry - (latest["atr"] * 3)
    
    sma_cross_up = prev["sma50"] < prev["sma200"] and latest["sma50"] > latest["sma200"]
    sma_cross_down = prev["sma50"] > prev["sma200"] and latest["sma50"] < latest["sma200"]
    rsi_overbought = latest["rsi"] > 70
    rsi_oversold = latest["rsi"] < 30
    macd_cross_up = prev["macd"] < prev["macd_signal"] and latest["macd"] > latest["macd_signal"]
    macd_cross_down = prev["macd"] > prev["macd_signal"] and latest["macd"] < latest["macd_signal"]
    
    market_structure = detect_market_structure(df)
    order_block = detect_order_blocks(df)
    liquidity_zone = detect_liquidity_zones(df)
    fvg = detect_fair_value_gaps(df)
    killzone = in_killzone(df.index[-1])
    
    analysis = f"Market Structure: {market_structure}. "
    analysis += f"Trend Strength: {latest['trend_strength']:.2f}%. "
    analysis += f"Order Block: {order_block}. "
    analysis += f"Liquidity Zone: {liquidity_zone}. "
    analysis += f"FVG: {fvg}. "
    analysis += f"Killzone: {killzone}. "
    if rsi_overbought:
        analysis += "RSI indicates overbought (>70). "
    elif rsi_oversold:
        analysis += "RSI indicates oversold (<30). "
    else:
        analysis += f"RSI neutral at {latest['rsi']:.2f}. "
    if latest["macd_hist"] > 0:
        analysis += "MACD shows bullish momentum. "
    else:
        analysis += "MACD shows bearish momentum. "
    analysis += f"Price change: {price_change:.2f}% since last candle. "
    
    signal = "HOLD"
    recommendation = "Hold position and monitor for stronger signals."
    
    if "Bullish" in market_structure and sma_cross_up and not rsi_overbought and macd_cross_up and "Order Block at" in order_block:
        analysis += "Strong BUY: Bullish structure with Order Block support."
        signal = "BUY"
        recommendation = f"Consider buying at {entry:.5f} with SL at {sl_long:.5f} and TP at {tp_long:.5f}. Strong bullish setup."
    elif "Bearish" in market_structure and sma_cross_down and not rsi_oversold and macd_cross_down and "Order Block at" in order_block:
        analysis += "Strong SELL: Bearish structure with Order Block resistance."
        signal = "SELL"
        recommendation = f"Consider selling at {entry:.5f} with SL at {sl_short:.5f} and TP at {tp_short:.5f}. Strong bearish setup."
    elif "Liquidity Zone above" in liquidity_zone and latest["close"] > latest["sma200"]:
        analysis += "Potential BUY: Price approaching upper liquidity."
        signal = "BUY"
        recommendation = f"Look to buy at {entry:.5f} targeting liquidity at {latest_swing_high:.5f}, SL at {sl_long:.5f}."
    elif "Liquidity Zone below" in liquidity_zone and latest["close"] < latest["sma200"]:
        analysis += "Potential SELL: Price approaching lower liquidity."
        signal = "SELL"
        recommendation = f"Look to sell at {entry:.5f} targeting liquidity at {latest_swing_low:.5f}, SL at {sl_short:.5f}."
    elif "FVG detected" in fvg:
        analysis += "Monitor for FVG fill."
        recommendation = "Watch for price to fill the FVG; prepare for a potential reversal or continuation."
    
    return signal, latest["trend_strength"], sl_long if signal == "BUY" else sl_short, tp_long if signal == "BUY" else tp_short, analysis, recommendation

def get_all_signals(pairs, granularity):
    signals = {}
    for pair in pairs:
        df = fetch_data(pair, granularity)
        if not df.empty:
            signal, strength, sl, tp, analysis, recommendation = generate_signal(df)
            signals[pair] = {"signal": signal, "strength": strength, "sl": sl, "tp": tp, "df": df, "analysis": analysis, "recommendation": recommendation}
        else:
            print(f"Skipping {pair} due to fetch error.")
    return signals

def place_order(signal, pair, units=1000, sl=0.0, tp=0.0):
    if signal == "HOLD":
        return "No trade executed."
    url = f"{BASE_URL}/accounts/{config['oanda_account_id']}/orders"
    data = {
        "order": {
            "units": str(units) if signal == "BUY" else str(-units),
            "instrument": pair,
            "type": "MARKET",
            "stopLossOnFill": {"price": f"{sl:.5f}"} if sl > 0 else None,
            "takeProfitOnFill": {"price": f"{tp:.5f}"} if tp > 0 else None
        }
    }
    try:
        response = requests.post(url, headers=HEADERS, json=data)
        response.raise_for_status()
        return f"{signal} order placed for {pair}: {units} units, SL: {sl:.5f}, TP: {tp:.5f}"
    except requests.exceptions.RequestException as e:
        return f"Trade failed for {pair}: {e.response.text if e.response else e}"