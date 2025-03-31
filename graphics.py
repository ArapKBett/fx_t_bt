import matplotlib.pyplot as plt
import pandas as pd

def generate_chart(df, pair):
    plt.figure(figsize=(10, 5))
    plt.plot(df.index, df["close"], label="Price", color="blue")
    plt.plot(df.index, df["sma50"], label="SMA 50", color="orange")
    plt.plot(df.index, df["sma200"], label="SMA 200", color="red")
    plt.title(f"{pair} Trend Analysis")
    plt.xlabel("Time")
    plt.ylabel("Price")
    plt.legend()
    plt.grid()
    plt.savefig("chart.png")
    plt.close()
