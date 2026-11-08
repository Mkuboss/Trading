#!/usr/bin/env python3
"""Unduh candle M1 XAUUSD (BID) per hari dari Dukascopy, dengan cache per hari (bisa dilanjutkan).
  python fetch_m1.py --start 2026-01-12 --end 2026-01-30 --out data/duka_m1_jan26.csv
"""
import argparse
import lzma
import struct
import time
import urllib.request
from pathlib import Path

import pandas as pd

URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m:02d}/{d:02d}/BID_candles_min_1.bi5"


def fetch_day(sym, day, retries=10):
    url = URL.format(sym=sym, y=day.year, m=day.month - 1, d=day.day)
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            break
        except Exception as e:  # noqa: BLE001
            if k == retries - 1:
                raise
            time.sleep(min(90, 5 * 2 ** k))
    if not raw:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    data = lzma.decompress(raw)
    base = pd.Timestamp(day)
    rows = [(base + pd.Timedelta(seconds=t), o / 1000, hi / 1000, lo / 1000, c / 1000, v)
            for t, o, c, lo, hi, v in (struct.unpack(">5If", data[i:i + 24]) for i in range(0, len(data) - 23, 24))]
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]).set_index("time")
    return df[df.volume > 0]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--delay", type=float, default=3.0)
    a = p.parse_args()
    cache = Path("data/cache_m1")
    cache.mkdir(parents=True, exist_ok=True)
    frames = []
    for day in pd.date_range(a.start, a.end, freq="D"):
        if day.dayofweek == 5:  # Sabtu: pasar tutup
            continue
        f = cache / f"{a.symbol}_{day:%Y-%m-%d}.csv"
        if not f.exists():
            try:
                fetch_day(a.symbol, day).to_csv(f)
                print(f"  {day:%Y-%m-%d} ok", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"  {day:%Y-%m-%d} gagal: {e}", flush=True)
                continue
            time.sleep(a.delay)
        part = pd.read_csv(f, index_col=0, parse_dates=True)
        if len(part):
            frames.append(part)
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated()]
    df.index.name = "datetime"
    df.to_csv(a.out, float_format="%.3f")
    print(f"{len(df):,} bar M1 | {df.index[0]} s/d {df.index[-1]} UTC -> {a.out}")


if __name__ == "__main__":
    main()
