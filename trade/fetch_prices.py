#!/usr/bin/env -S .venv/bin/python
"""Fetch stock prices via yfinance and write to prices.json.

Usage:
    python trade/fetch_prices.py

Requires: yfinance (pip install yfinance)
Output:   trade/prices.json
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

# ── Config ──────────────────────────────────────────────────────────────
SYMBOLS = ["NVDA", "MU", "VOO", "QQQ"]
OUTPUT = Path(__file__).resolve().parent / "prices.json"


# ── Helpers ─────────────────────────────────────────────────────────────
def fetch_stock(sym: str) -> dict | None:
    """Fetch price data for a single symbol. Returns None on failure."""
    try:
        t = yf.Ticker(sym)
        fast = t.fast_info
        info = t.info

        reg_price = (
            fast.get("lastPrice")
            or fast.get("regularMarketPrice")
        )
        prev_close = (
            fast.get("previousClose")
            or fast.get("regularMarketPreviousClose")
        )

        # Fallback to daily history if fast_info is empty
        if reg_price is None:
            hist = t.history(period="1d")
            if not hist.empty:
                reg_price = float(hist["Close"].iloc[-1])

        if reg_price is None:
            print(f"   ⚠ {sym}: no price data", file=sys.stderr)
            return None

        result: dict = {
            "price": round(float(reg_price), 2),
            "previousClose": round(float(prev_close), 2) if prev_close else None,
            "marketState": info.get("marketState", "UNKNOWN"),
        }

        # Post-market / after-hours
        pm = info.get("postMarketPrice")
        if pm is not None:
            result["postMarketPrice"] = round(float(pm), 2)
            pc = info.get("postMarketChange")
            if pc is not None:
                result["postMarketChange"] = round(float(pc), 2)
            pp = info.get("postMarketChangePercent")
            if pp is not None:
                result["postMarketChangePercent"] = round(float(pp), 2)

        return result

    except Exception as exc:
        print(f"   ❌ {sym}: {exc}", file=sys.stderr)
        return None


def format_stock(sym: str, d: dict) -> str:
    """Pretty-print a single stock line."""
    price = d["price"]
    prev = d.get("previousClose")
    state = d.get("marketState", "?")

    if prev and prev != 0:
        change = price - prev
        pct = (change / prev) * 100
        sign = "+" if change >= 0 else ""
        line = f"{sym:>4s}: ${price:,.2f}  {sign}{change:+.2f} ({sign}{pct:.2f}%)  [{state}]"
    else:
        line = f"{sym:>4s}: ${price:,.2f}  [{state}]"

    if d.get("postMarketPrice"):
        pm = d["postMarketPrice"]
        pc = d.get("postMarketChange", pm - price)
        pp = d.get("postMarketChangePercent", (pc / price) * 100)
        ps = "+" if pc >= 0 else ""
        line += f"  AH: ${pm:,.2f} {ps}{pc:+.2f} ({ps}{pp:.2f}%)"

    return line


# ── Main ────────────────────────────────────────────────────────────────
def main() -> int:
    print(f"Fetching: {', '.join(SYMBOLS)}")
    print("-" * 50)

    stocks: dict = {}
    errors = 0

    for sym in SYMBOLS:
        data = fetch_stock(sym)
        if data is None:
            errors += 1
        else:
            stocks[sym] = data
            print(f"   {format_stock(sym, data)}")

    if errors == len(SYMBOLS):
        print(f"\n❌ All {len(SYMBOLS)} symbols failed — aborting.", file=sys.stderr)
        return 1

    result = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "stocks": stocks,
    }

    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")

    print("-" * 50)
    print(f"✅ Written to {OUTPUT}")
    if errors:
        print(f"⚠  {errors}/{len(SYMBOLS)} symbols failed — check above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
