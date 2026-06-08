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
        fast = ticker.fast_info
        # full info for post-market fields (not in fast_info)
        info = ticker.info

        reg_price = fast.get("lastPrice") or fast.get("regularMarketPrice")
        prev_close = fast.get("previousClose") or fast.get("regularMarketPreviousClose")
        post_price = info.get("postMarketPrice")
        post_change = info.get("postMarketChange")
        post_pct = info.get("postMarketChangePercent")

        if reg_price is None:
            hist = ticker.history(period="1d")
            if not hist.empty:
                reg_price = float(hist["Close"].iloc[-1])

        market_state = info.get("marketState", "UNKNOWN")

        data[sym] = {
            "price": round(float(reg_price), 2) if reg_price else None,
            "previousClose": round(float(prev_close), 2) if prev_close else None,
            "marketState": market_state,
        }

        # Include after-market price if available
        if post_price is not None:
            data[sym]["postMarketPrice"] = round(float(post_price), 2)
            if post_change is not None:
                data[sym]["postMarketChange"] = round(float(post_change), 2)
            if post_pct is not None:
                data[sym]["postMarketChangePercent"] = round(float(post_pct), 2)

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
            extra = ""
            if d.get("postMarketPrice"):
                pm = d["postMarketPrice"]
                pc = d.get("postMarketChange", pm - d["price"])
                pp = d.get("postMarketChangePercent", (pc / d["price"]) * 100)
                ps = "+" if pc > 0 else ""
                extra = f" | AH: ${pm:.2f} ({ps}{pp:.2f}%)"
            print(f"   {sym}: ${d['price']:.2f} ({sign}{pct:.2f}%) [{d.get('marketState','?')}]{extra}")
        else:
            print(f"   {sym}: ❌ data missing")

except Exception as e:
    print(f"❌ Error: {e}", file=sys.stderr)
    sys.exit(1)
