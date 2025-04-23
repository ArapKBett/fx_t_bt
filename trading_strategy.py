import pandas as pd
import requests
import json
import numpy as np
from datetime import datetime, time

try:
    with open("config.json", "r") as f:
        config = json.load(f)
except FileNotFoundError:
    print("config.json not found. Ensure it exists with correct credentials.")
    exit(1)

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
            print(f"No candle data for {pair}")
            return pd.DataFrame()
        df = pd.DataFrame([{
            "time": candle["time"],
            "open": float(candle["mid"]["o"]),
            "high": float(candle["mid"]["h"]),
            "low": float(candle["mid"]["l"]),
            "close": float(candle["mid"]["c"])
        } for candle in data["candles"]])
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        return df[["open", "high", "low", "close"]]
    except Exception as e:
        print(f"Error fetching {pair}: {e}")
        return pd.DataFrame()

def detect_candlestick_patterns(df):
    if df.empty or len(df) < 2:
        return "No pattern"
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    body = abs(latest["close"] - latest["open"])
    upper_wick = latest["high"] - max(latest["open"], latest["close"])
    lower_wick = min(latest["open"], latest["close"]) - latest["low"]
    range_size = latest["high"] - latest["low"] or 0.0001
    
    if upper_wick > 2 * body and lower_wick < body and range_size > df["range"].mean():
        return "Bearish Pin Bar" if latest["close"] < latest["open"] else "Bullish Pin Bar"
    if lower_wick > 2 * body and upper_wick < body and range_size > df["range"].mean():
        return "Bullish Pin Bar" if latest["close"] > latest["open"] else "Bearish Pin Bar"
    
    prev_body = abs(prev["close"] - prev["open"])
    if body > prev_body and latest["close"] > latest["open"] and prev["close"] < prev["open"]:
        return "Bullish Engulfing"
    if body > prev_body and latest["close"] < latest["open"] and prev["close"] > prev["open"]:
        return "Bearish Engulfing"
    
    return "No pattern"

def detect_key_levels(df):
    if df.empty or len(df) < 20:
        return None, None
    resistance = df["high"].rolling(window=20).max().iloc[-1]
    support = df["low"].rolling(window=20).min().iloc[-1]
    return support, resistance

def detect_breakout(df, levels):
    if df.empty or len(df) < 3:
        return "No breakout"
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    support, resistance = levels
    if prev["close"] < resistance and latest["close"] > resistance and (latest["close"] - resistance) > latest["range"] * 0.3:
        return f"Breakout above {resistance:.5f}"
    if prev["close"] > support and latest["close"] < support and (support - latest["close"]) > latest["range"] * 0.3:
        return f"Breakout below {support:.5f}"
    return "No breakout"

def detect_market_structure(df):
    if df.empty or len(df) < 5:
        return "Unknown"
    df["swing_high"] = df["high"].rolling(window=5, center=True).max()
    df["swing_low"] = df["low"].rolling(window=5, center=True).min()
    highs = df["swing_high"].dropna()
    lows = df["swing_low"].dropna()
    if len(highs) < 2 or len(lows) < 2:
        return "Limited data"
    latest_high, prev_high = highs[-1], highs[-2]
    latest_low, prev_low = lows[-1], lows[-2]
    if latest_high > prev_high and latest_low > prev_low:
        return "Bullish (HH, HL)"
    if latest_high < prev_high and latest_low < prev_low:
        return "Bearish (LH, LL)"
    return "Consolidation"

def detect_order_blocks(df):
    if df.empty or len(df) < 3:
        return "No OB"
    df["range"] = df["high"] - df["low"]
    small_range = df["range"] < df["range"].mean() * 0.5
    reversal = df["close"].diff().shift(-1).abs() > df["range"].mean()
    ob = small_range & reversal
    if ob.iloc[-2]:
        return f"OB at {df['close'].iloc[-2]:.5f}"
    return "No recent OB"

def detect_liquidity_zones(df):
    if df.empty or len(df) < 5:
        return "No LZ"
    latest_high = df["swing_high"].iloc[-1]
    latest_low = df["swing_low"].iloc[-1]
    price = df["close"].iloc[-1]
    if pd.isna([latest_high, latest_low, price]).any():
        return "No LZ"
    if abs(price - latest_high) < df["range"].mean() * 0.5:
        return f"LZ above at {latest_high:.5f}"
    if abs(price - latest_low) < df["range"].mean() * 0.5:
        return f"LZ below at {latest_low:.5f}"
    return "No LZ"

def detect_fair_value_gaps(df):
    if df.empty or len(df) < 3:
        return "No FVG"
    gap = df["high"].shift(1) - df["low"]
    if gap.iloc[-2] > df["range"].mean() * 1.5:
        return f"FVG at {df['high'].iloc[-3]:.5f}-{df['low'].iloc[-2]:.5f}"
    return "No FVG"

def in_killzone(timestamp):
    t = timestamp.time()
    london = (time(8, 0), time(11, 0))
    ny = (time(13, 0), time(16, 0))
    if london[0] <= t <= london[1]:
        return "London Killzone"
    if ny[0] <= t <= ny[1]:
        return "NY Killzone"
    return "No Killzone"

def calculate_indicators(df):
    if df.empty or len(df) < 50:
        return df
    df["range"] = df["high"] - df["low"]
    df["sma50"] = df["close"].rolling(window=50).mean()
    df["sma200"] = df["close"].rolling(window=200).mean() if len(df) >= 200 else df["close"].mean()
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    df["atr"] = df["range"].rolling(window=14).mean()
    df["trend_strength"] = abs(df["sma50"] - df["sma200"]) / df["sma200"] * 100
    tr = pd.concat([df["range"], (df["high"] - df["close"].shift()).abs(), (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    dm_plus = (df["high"] - df["high"].shift()).where(lambda x: x > 0, 0)
    dm_minus = (df["low"].shift() - df["low"]).where(lambda x: x > 0, 0)
    atr = tr.rolling(window=14).mean()
    df["di_plus"] = 100 * (dm_plus.rolling(window=14).mean() / atr)
    df["di_minus"] = 100 * (dm_minus.rolling(window=14).mean() / atr)
    dx = 100 * abs(df["di_plus"] - df["di_minus"]) / (df["di_plus"] + df["di_minus"]).replace(0, np.nan)
    df["adx"] = dx.rolling(window=14).mean()
    return df

def generate_signal(df):
    if df.empty or len(df) < 50:
        return "HOLD", 0.0, 0.0, 0.0, "No data.", "Wait for data.", 0.0
    
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    price_change = (latest["close"] - prev["close"]) / prev["close"] * 100
    support, resistance = detect_key_levels(df)
    
    entry = latest["close"]
    sl_long = entry - latest["atr"] * 1.5
    tp_long = entry + latest["atr"] * 3
    sl_short = entry + latest["atr"] * 1.5
    tp_short = entry - latest["atr"] * 3
    rr_long = (tp_long - entry) / (entry - sl_long) if entry > sl_long else 0
    rr_short = (entry - tp_short) / (sl_short - entry) if sl_short > entry else 0
    
    sma_cross_up = prev["sma50"] < prev["sma200"] and latest["sma50"] > latest["sma200"]
    sma_cross_down = prev["sma50"] > prev["sma200"] and latest["sma50"] < latest["sma200"]
    rsi_overbought = latest["rsi"] > 70
    rsi_oversold = latest["rsi"] < 30
    macd_bull = prev["macd"] < prev["macd_signal"] and latest["macd"] > latest["macd_signal"]
    macd_bear = prev["macd"] > prev["macd_signal"] and latest["macd"] < latest["macd_signal"]
    adx_strong = latest["adx"] > 25
    
    pattern = detect_candlestick_patterns(df)
    breakout = detect_breakout(df, (support, resistance))
    structure = detect_market_structure(df)
    ob = detect_order_blocks(df)
    lz = detect_liquidity_zones(df)
    fvg = detect_fair_value_gaps(df)
    kz = in_killzone(df.index[-1])
    
    analysis = (
        f"Structure: {structure}. Trend: {latest['trend_strength']:.2f}% (ADX: {latest['adx']:.2f}). "
        f"Pattern: {pattern}. Breakout: {breakout}. OB: {ob}. LZ: {lz}. FVG: {fvg}. "
        f"KZ: {kz}. RSI: {latest['rsi']:.2f}. MACD: {'Bull' if latest['macd_hist'] > 0 else 'Bear'}. "
        f"Change: {price_change:.2f}%."
    )
    
    signal = "HOLD"
    recommendation = "Monitor for stronger signals."
    confidence = 0.5
    
    if ("Bullish" in structure or "Bullish" in pattern) and sma_cross_up and not rsi_overbought and macd_bull:
        signal = "BUY"
        recommendation = f"Buy at {entry:.5f}, SL: {sl_long:.5f}, TP: {tp_long:.5f} (R:R {rr_long:.2f})."
        confidence = 0.85 if adx_strong and ("OB at" in ob or "LZ" in lz) else 0.7
        analysis += " Strong BUY: Confluence of trend, pattern, and momentum."
    elif ("Bearish" in structure or "Bearish" in pattern) and sma_cross_down and not rsi_oversold and macd_bear:
        signal = "SELL"
        recommendation = f"Sell at {entry:.5f}, SL: {sl_short:.5f}, TP: {tp_short:.5f} (R:R {rr_short:.2f})."
        confidence = 0.85 if adx_strong and ("OB at" in ob or "LZ" in lz) else 0.7
        analysis += " Strong SELL: Confluence of trend, pattern, and momentum."
    elif "Breakout above" in breakout and latest["rsi"] > 50:
        signal = "BUY"
        recommendation = f"Buy at {entry:.5f}, SL: {sl_long:.5f}, TP: {tp_long:.5f} (R:R {rr_long:.2f})."
        confidence = 0.8 if adx_strong else 0.65
        analysis += " Breakout BUY confirmed."
    elif "Breakout below" in breakout and latest["rsi"] < 50:
        signal = "SELL"
        recommendation = f"Sell at {entry:.5f}, SL: {sl_short:.5f}, TP: {tp_short:.5f} (R:R {rr_short:.2f})."
        confidence = 0.8 if adx_strong else 0.65
        analysis += " Breakout SELL confirmed."
    
    return signal, latest["trend_strength"], sl_long if signal == "BUY" else sl_short, tp_long if signal == "BUY" else tp_short, analysis, recommendation, confidence

def get_all_signals(pairs, granularity):
    signals = {}
    for pair in pairs:
        df = fetch_data(pair, granularity)
        if not df.empty:
            signals[pair] = generate_signal(df)
            signals[pair] = {"signal": signals[pair][0], "strength": signals[pair][1], "sl": signals[pair][2], 
                             "tp": signals[pair][3], "df": df, "analysis": signals[pair][4], 
                             "recommendation": signals[pair][5], "confidence": signals[pair][6]}
    return signals

def place_order(signal, pair, units=1000, sl=0.0, tp=0.0):
    if signal == "HOLD":
        return "No trade."
    url = f"{BASE_URL}/accounts/{config['oanda_account_id']}/orders"
    data = {
        "order": {
            "units": str(units) if signal == "BUY" else str(-units),
            "instrument": pair,
            "type": "MARKET",
            "stopLossOnFill": {"price": f"{sl:.5f}"},
            "takeProfitOnFill": {"price": f"{tp:.5f}"}
        }
    }
    try:
        response = requests.post(url, headers=HEADERS, json=data)
        response.raise_for_status()
        return f"{signal} order placed: {pair}, {units} units, SL: {sl:.5f}, TP: {tp:.5f}"
    except Exception as e:
        return f"Order failed for {pair}: {e}"
