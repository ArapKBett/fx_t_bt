A sophisticated trading bot for forex markets, integrating price action, Inner Circle Trader (ICT) concepts, and technical indicators to provide high-probability trade signals. Built with Python, it connects to OANDA’s API for real-time data, delivers signals via Telegram and Discord, and generates visual charts for analysis.

## Features
- **Price Action Analysis**: Detects candlestick patterns (Pin Bars, Engulfing) and breakouts.
- **ICT Concepts**: Identifies Order Blocks, Liquidity Zones, and Fair Value Gaps.
- **Technical Indicators**: Uses SMA, RSI, MACD, ADX, and ATR for robust signals.
- **Confidence Scores**: Assigns 50-85% confidence to trades based on confluence.
- **Risk Management**: Calculates stop-loss and take-profit with Risk:Reward ratios.
- **Visualization**: Generates charts with support/resistance and indicators.
- **Multi-Platform**: Delivers signals via Telegram (interactive menus) and Discord (scheduled updates).
- **Supported Pairs**: 26 forex pairs plus BTC/USD on OANDA.

## Prerequisites
- Python 3.8+
- OANDA practice account (API token and account ID)
- Telegram bot token (via BotFather)
- Discord bot token and channel ID
- Termux (for mobile deployment) or a similar environment
