#!/usr/bin/env python3
"""Fetch stock prices via yfinance and write to prices.json for the trade page."""
import json
import sys
from datetime import datetime, timezone

import yfinance as yf

SYMBOLS = ["NVDA", "MU", "VOO", "QQQ"]
OUTPUT = "trade/prices.json"

try:
    data = {}
    for sym in SYMBOLS:
        ticker = yf.Ticker(sym)
        info = ticker.fast_info

        price = info.get("lastPrice")
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose")

        if price is None:
            # fallback to history for last price
            hist = ticker.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])

        data[sym] = {
            "price": round(float(price), 2) if price else None,
            "previousClose": round(float(prev), 2) if prev else None,
        }

    result = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "stocks": data,
    }

    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)

    print(f"✅ Prices written to {OUTPUT}")
    for sym, d in data.items():
        if d["price"] and d["previousClose"]:
            change = d["price"] - d["previousClose"]
            pct = (change / d["previousClose"]) * 100
            sign = "+" if change > 0 else ""
            print(f"   {sym}: ${d['price']:.2f} ({sign}{pct:.2f}%)")
        else:
            print(f"   {sym}: ❌ data missing")

except Exception as e:
    print(f"❌ Error: {e}", file=sys.stderr)
    sys.exit(1)
