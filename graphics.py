import matplotlib.pyplot as plt

def generate_chart(df, pair):
    if df.empty or len(df) < 50:
        return
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 8), height_ratios=[3, 1, 1], sharex=True)
    
    ax1.plot(df.index, df["close"], label="Close", color="blue")
    ax1.plot(df.index, df["sma50"], label="SMA50", color="orange")
    ax1.plot(df.index, df["sma200"], label="SMA200", color="green")
    support, resistance = df["low"].rolling(window=20).min().iloc[-1], df["high"].rolling(window=20).max().iloc[-1]
    ax1.axhline(support, color="green", linestyle="--", label=f"S: {support:.5f}")
    ax1.axhline(resistance, color="red", linestyle="--", label=f"R: {resistance:.5f}")
    ax1.set_title(f"{pair} Price Action")
    ax1.legend()
    ax1.grid(True)
    
    ax2.plot(df.index, df["rsi"], label="RSI", color="purple")
    ax2.axhline(70, color="red", linestyle="--")
    ax2.axhline(30, color="green", linestyle="--")
    ax2.set_ylim(0, 100)
    ax2.set_title("RSI")
    ax2.legend()
    ax2.grid(True)
    
    ax3.plot(df.index, df["macd"], label="MACD", color="blue")
    ax3.plot(df.index, df["macd_signal"], label="Signal", color="orange")
    ax3.bar(df.index, df["macd_hist"], label="Hist", color="gray", alpha=0.5)
    ax3.axhline(0, color="black", linestyle="--")
    ax3.set_title("MACD")
    ax3.legend()
    ax3.grid(True)
    
    plt.tight_layout()
    plt.savefig(f"chart_{pair.replace('_', '')}.png", dpi=100)
    plt.close()

def generate_comparison_chart(signals):
    strengths = {pair: data["strength"] for pair, data in signals.items() if data["strength"] is not None}
    plt.figure(figsize=(10, 6))
    plt.bar(strengths.keys(), strengths.values(), color="purple")
    plt.xticks(rotation=90)
    plt.title("Trend Strength Comparison")
    plt.tight_layout()
    plt.savefig("comparison_chart.png", dpi=100)
    plt.close()
