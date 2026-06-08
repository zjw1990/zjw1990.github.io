#!/usr/bin/env -S .venv/bin/python
"""Fetch stock prices via yfinance and write to prices.json.

Usage:
    python trade/fetch_prices.py

Requires: yfinance (pip install yfinance)
Output:   trade/prices.json
"""
import json
import sys
from datetime import datetime, time, timezone
from pathlib import Path

import yfinance as yf

# ── Config ──────────────────────────────────────────────────────────────
SYMBOLS = ["NVDA", "MU", "VOO", "QQQ"]
OUTPUT = Path(__file__).resolve().parent / "prices.json"


# ── Helpers ─────────────────────────────────────────────────────────────
def fetch_stock(sym: str) -> dict | None:
    """Fetch price data for a single symbol using intraday history.

    Uses ``history(period="1d", interval="1m", prepost=True)`` to get
    1-minute bars covering pre-market, regular, and after-hours for the
    current trading day — giving us the most accurate price including
    after-market movement.
    """
    try:
        t = yf.Ticker(sym)
        fast = t.fast_info
        info = t.info

        # ── Current (intraday + after-hours) price ─────────────────────
        intraday = t.history(period="1d", interval="1m", prepost=True)

        if intraday.empty:
            # fallback: maybe market hasn't opened yet
            prev_close = fast.get("previousClose") or fast.get("regularMarketPreviousClose")
            if prev_close:
                return {
                    "price": round(float(prev_close), 2),
                    "previousClose": round(float(prev_close), 2),
                    "marketState": info.get("marketState") or "CLOSED",
                }
            print(f"   ⚠ {sym}: no intraday or previous close data", file=sys.stderr)
            return None

        # The very last close is the most recent price (regular or AH)
        latest_price = float(intraday["Close"].iloc[-1])

        # ── Separate regular vs post-market ────────────────────────────
        # Regular hours: 9:30 AM – 4:00 PM ET.  Filter rows within that window.
        reg_mask = intraday.index.to_series().apply(
            lambda ts: _is_regular_hours(ts)
        )
        reg_data = intraday[reg_mask]
        post_mask = intraday.index.to_series().apply(
            lambda ts: _is_after_hours(ts)
        )
        post_data = intraday[post_mask]

        reg_price = float(reg_data["Close"].iloc[-1]) if not reg_data.empty else None
        prev_close = (
            fast.get("previousClose")
            or fast.get("regularMarketPreviousClose")
        )

        # fallback prev_close from 5-day history
        if prev_close is None:
            hist5d = t.history(period="5d")
            if len(hist5d) >= 2:
                prev_close = float(hist5d["Close"].iloc[-2])

        market_state = info.get("marketState") or "UNKNOWN"

        result: dict = {
            "price": round(latest_price, 2),
            "previousClose": round(float(prev_close), 2) if prev_close else None,
            "marketState": market_state,
        }

        # ── Post-market / after-hours ──────────────────────────────────
        if not post_data.empty:
            pm_price = float(post_data["Close"].iloc[-1])
            result["postMarketPrice"] = round(pm_price, 2)
            if reg_price:
                pm_change = pm_price - reg_price
                pm_pct = (pm_change / reg_price) * 100
                result["postMarketChange"] = round(pm_change, 2)
                result["postMarketChangePercent"] = round(pm_pct, 2)

        # Also check info dict for post-market (sometimes more timely)
        if "postMarketPrice" not in result:
            pm_info = info.get("postMarketPrice")
            if pm_info is not None:
                result["postMarketPrice"] = round(float(pm_info), 2)
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


def _is_regular_hours(ts) -> bool:
    """Check if a timestamp falls within US regular market hours (9:30–16:00 ET)."""
    t = ts.time()
    return time(9, 30) <= t <= time(16, 0)


def _is_after_hours(ts) -> bool:
    """Check if a timestamp falls within after-hours (16:00–20:00 ET)."""
    t = ts.time()
    return time(16, 0) < t <= time(20, 0)


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
