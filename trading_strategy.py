import pandas as pd
from oandapyV20 import API
from oandapyV20.endpoints.instruments import InstrumentsCandles
import oandapyV20.endpoints.orders as orders
import json

with open("config.json", "r") as f:
    config = json.load(f)

api = API(access_token=config["oanda_api_token"])

def fetch_data(pair, granularity="H4", count=250):
    params = {
        "count": count,
        "granularity": granularity,
        "price": "M"  # Midpoint prices
    }
    r = InstrumentsCandles(instrument=pair, params=params)
    api.request(r)
    data = r.response["candles"]
    df = pd.DataFrame([{
        "time": candle["time"],
        "close": float(candle["mid"]["c"])
    } for candle in data])
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)
    return df

def calculate_indicators(df):
    df["sma50"] = df["close"].rolling(window=50).mean()
    df["sma200"] = df["close"].rolling(window=200).mean()
    return df

def generate_signal(df):
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    if prev["sma50"] < prev["sma200"] and latest["sma50"] > latest["sma200"]:
        return "BUY"
    elif prev["sma50"] > prev["sma200"] and latest["sma50"] < latest["sma200"]:
        return "SELL"
    return "HOLD"

def place_order(signal, pair, units=1000):
    if signal == "HOLD":
        return "No trade executed."
    
    order_type = "MARKET"
    direction = 1 if signal == "BUY" else -1
    data = {
        "order": {
            "instrument": pair,
            "units": str(direction * units),
            "type": order_type,
            "positionFill": "DEFAULT"
        }
    }
    r = orders.OrderCreate(accountID=config["oanda_account_id"], data=data)
    api.request(r)
    return f"{signal} order placed for {pair}: {units} units."
