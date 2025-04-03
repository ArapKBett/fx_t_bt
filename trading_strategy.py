import pandas as pd
import requests
import json
import numpy as np

with open("config.json", "r") as f:
    config = json.load(f)

BASE_URL = "https://api-fxpractice.oanda.com/v3"
HEADERS = {"Authorization": f"Bearer {config['oanda_api_token']}", "Content-Type": "application/json"}

# Define the 8 major currencies
MAJOR_CURRENCIES = ["EUR", "USD", "JPY", "GBP", "CHF", "AUD", "CAD", "NZD"]

# Curated list of OANDA-supported pairs (28 fiat + 8 BTC pairs)
PAIRS = [
    "EUR_USD", "EUR_JPY", "EUR_GBP", "EUR_CHF", "EUR_AUD", "EUR_CAD", "EUR_NZD",
    "USD_JPY", "USD_CHF", "USD_CAD", "USD_AUD", "USD_NZD",
    "GBP_USD", "GBP_JPY", "GBP_CHF", "GBP_AUD", "GBP_CAD", "GBP_NZD",
    "CHF_JPY", "CHF_AUD", "CHF_CAD", "CHF_NZD",
    "AUD_USD", "AUD_JPY", "AUD_CAD", "AUD_NZD",
    "CAD_JPY", "CAD_CHF",
    "NZD_USD", "NZD_JPY", "NZD_CAD",
    "BTC_USD", "BTC_EUR", "BTC_JPY", "BTC_GBP", "BTC_CHF", "BTC_AUD", "BTC_CAD", "BTC_NZD"
]

def fetch_data(pair, granularity="H1", count=500):
    try:
        url = f"{BASE_URL}/instruments/{pair}/candles"
        params = {"count": count, "granularity": granularity, "price": "MBA"}
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()["candles"]
        df = pd.DataFrame([{
            "time": candle["time"],
            "close": float(candle["mid"]["c"]),
            "high": float(candle["mid"]["h"]),
            "low": float(candle["mid"]["l"])
        } for candle in data])
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        return df[["close", "high", "low"]]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {pair}: {e.response.text if e.response else e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Unexpected error fetching data for {pair}: {e}")
        return pd.DataFrame()

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
    df["bb_middle"] = df["close"].rolling(window=20).mean()
    df["bb_std"] = df["close"].rolling(window=20).std()
    df["bb_upper"] = df["bb_middle"] + (df["bb_std"] * 2)
    df["bb_lower"] = df["bb_middle"] - (df["bb_std"] * 2)
    df["tr1"] = df["high"] - df["low"]
    df["tr2"] = abs(df["high"] - df["close"].shift())
    df["tr3"] = abs(df["low"] - df["close"].shift())
    df["tr"] = df[["tr1", "tr2", "tr3"]].max(axis=1)
    df["atr"] = df["tr"].rolling(window=14).mean()
    df["trend_strength"] = abs(df["sma50"] - df["sma200"]) / df["sma200"] * 100
    return df.drop(columns=["tr1", "tr2", "tr3", "tr"])

def generate_signal(df):
    if df.empty or len(df) < 200:
        return "HOLD", 0.0, 0.0, 0.0, "Insufficient data for analysis."
    
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
    
    analysis = f"Trend Strength: {latest['trend_strength']:.2f}%. "
    if latest["sma50"] > latest["sma200"]:
        analysis += "Bullish trend (SMA50 > SMA200). "
    else:
        analysis += "Bearish trend (SMA50 < SMA200). "
    if rsi_overbought:
        analysis += "RSI indicates overbought (>70). "
    elif rsi_oversold:
        analysis += "RSI indicates oversold (<30). "
    else:
        analysis += f"RSI neutral at {latest['rsi']:.2f}. "
    if latest["macd_hist"] > 0:
        analysis += "MACD shows bullish momentum. "
    elif latest["macd_hist"] < 0:
        analysis += "MACD shows bearish momentum. "
    analysis += f"Price change: {price_change:.2f}% since last candle. "
    
    if sma_cross_up and not rsi_overbought and macd_cross_up:
        analysis += "Strong BUY signal confirmed."
        return "BUY", latest["trend_strength"], sl_long, tp_long, analysis
    if sma_cross_down and not rsi_oversold and macd_cross_down:
        analysis += "Strong SELL signal confirmed."
        return "SELL", latest["trend_strength"], sl_short, tp_short, analysis
    
    if latest["macd_hist"] > 0:
        return "HOLD", latest["trend_strength"], sl_long, tp_long, analysis + "Recommendation: Prepare for potential BUY if trend strengthens."
    else:
        return "HOLD", latest["trend_strength"], sl_short, tp_short, analysis + "Recommendation: Prepare for potential SELL if trend strengthens."

def get_all_signals(pairs, granularity):
    signals = {}
    for pair in pairs:
        df = fetch_data(pair, granularity)
        if not df.empty:  # Only process if data is fetched successfully
            signal, strength, sl, tp, analysis = generate_signal(df)
            signals[pair] = {"signal": signal, "strength": strength, "sl": sl, "tp": tp, "df": df, "analysis": analysis}
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