import matplotlib.pyplot as plt

def generate_chart(df, pair):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8), height_ratios=[3, 1, 1], sharex=True)
    
    # Price Chart (Close, SMA50, SMA200)
    ax1.plot(df.index, df["close"], label="Close", color="blue")
    ax1.plot(df.index, df["sma50"], label="SMA50", color="orange")
    ax1.plot(df.index, df["sma200"], label="SMA200", color="green")
    ax1.set_title(f"{pair} Chart")
    ax1.legend()
    ax1.grid(True)
    
    # RSI Chart
    ax2.plot(df.index, df["rsi"], label="RSI", color="purple")
    ax2.axhline(70, color="red", linestyle="--", alpha=0.5)
    ax2.axhline(30, color="green", linestyle="--", alpha=0.5)
    ax2.set_ylim(0, 100)
    ax2.set_title("RSI")
    ax2.legend()
    ax2.grid(True)
    
    # MACD Chart
    ax3.plot(df.index, df["macd"], label="MACD", color="blue")
    ax3.plot(df.index, df["macd_signal"], label="Signal", color="orange")
    ax3.bar(df.index, df["macd_hist"], label="Histogram", color="gray", alpha=0.5)
    ax3.axhline(0, color="black", linestyle="--", alpha=0.5)
    ax3.set_title("MACD")
    ax3.legend()
    ax3.grid(True)
    
    plt.tight_layout()
    plt.savefig(f"chart_{pair.replace('_', '')}.png")
    plt.close()

def generate_comparison_chart(signals):
    strengths = {pair: data["strength"] for pair, data in signals.items()}
    plt.figure(figsize=(12, 6))
    plt.bar(strengths.keys(), strengths.values(), color="purple")
    plt.xticks(rotation=90)
    plt.title("Trend Strength Comparison")
    plt.tight_layout()
    plt.savefig("comparison_chart.png")
    plt.close()