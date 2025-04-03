import matplotlib.pyplot as plt

def generate_chart(df, pair):
    """Generate a chart with price, RSI, and MACD."""
    if df.empty:
        return
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10), sharex=True, height_ratios=[3, 1, 1])
    
    # Price with SMA and Bollinger Bands
    ax1.plot(df.index, df["close"], label="Price", color="blue")
    ax1.plot(df.index, df["sma50"], label="SMA 50", color="orange")
    ax1.plot(df.index, df["sma200"], label="SMA 200", color="red")
    ax1.plot(df.index, df["bb_upper"], label="BB Upper", color="gray", linestyle="--")
    ax1.plot(df.index, df["bb_lower"], label="BB Lower", color="gray", linestyle="--")
    ax1.fill_between(df.index, df["bb_upper"], df["bb_lower"], color="gray", alpha=0.1)
    ax1.set_title(f"{pair} Technical Analysis")
    ax1.set_ylabel("Price")
    ax1.legend()
    ax1.grid()
    
    # RSI
    ax2.plot(df.index, df["rsi"], label="RSI", color="purple")
    ax2.axhline(70, color="red", linestyle="--", alpha=0.5)
    ax2.axhline(30, color="green", linestyle="--", alpha=0.5)
    ax2.set_ylabel("RSI")
    ax2.legend()
    ax2.grid()
    
    # MACD
    ax3.plot(df.index, df["macd"], label="MACD", color="blue")
    ax3.plot(df.index, df["macd_signal"], label="Signal", color="orange")
    ax3.bar(df.index, df["macd_hist"], label="Histogram", color="gray", alpha=0.5)
    ax3.set_ylabel("MACD")
    ax3.legend()
    ax3.grid()
    
    plt.xlabel("Time")
    plt.tight_layout()
    plt.savefig(f"chart_{pair.replace('_', '')}.png")
    plt.close()

def generate_comparison_chart(signals):
    """Generate a bar chart comparing trend strength across pairs."""
    pairs = list(signals.keys())
    strengths = [signals[pair]["strength"] for pair in pairs]
    signals_list = [signals[pair]["signal"] for pair in pairs]
    
    plt.figure(figsize=(12, 6))
    bars = plt.bar(pairs, strengths, color=['green' if s == "BUY" else 'red' if s == "SELL" else 'gray' for s in signals_list])
    plt.title("Trend Strength Comparison Across Major Pairs")
    plt.xlabel("Currency Pair")
    plt.ylabel("Trend Strength (%)")
    plt.xticks(rotation=45)
    for bar, signal in zip(bars, signals_list):
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval, signal, ha='center', va='bottom')
    plt.tight_layout()
    plt.savefig("comparison_chart.png")
    plt.close()