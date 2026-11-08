#!/usr/bin/env python3
"""
Unduh data historis XAUUSD (spot) dari Dukascopy dan simpan sebagai CSV H1.

Contoh:
  python fetch_data.py --start 2015 --end 2026 --out data/XAUUSD_H1.csv

Format file Dukascopy (BID_candles_hour_1.bi5, satu file per bulan, bulan 0-based):
  terkompresi LZMA, record 24 byte big-endian:
  uint32 detik sejak awal bulan, uint32 open, close, low, high (harga x 1000), float32 volume.
Semua waktu dalam UTC.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import lzma
import struct
import time
import urllib.request
from pathlib import Path

import pandas as pd

URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m:02d}/{side}_candles_hour_1.bi5"
POINT = {"XAUUSD": 1000.0, "XAGUSD": 1000.0}


def fetch_month(sym: str, year: int, month0: int, side: str = "BID", retries: int = 8) -> pd.DataFrame:
    url = URL.format(sym=sym, y=year, m=month0, side=side)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            break
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(min(60, 3 * 2 ** attempt))
    if not raw:
        return pd.DataFrame()
    data = lzma.decompress(raw)
    point = POINT.get(sym, 1000.0)
    base = pd.Timestamp(year=year, month=month0 + 1, day=1)
    rows = []
    for off in range(0, len(data) - 23, 24):
        t, o, c, lo, hi, v = struct.unpack(">5If", data[off:off + 24])
        rows.append((base + pd.Timedelta(seconds=t), o / point, hi / point, lo / point, c / point, v))
    df = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "volume"]).set_index("time")
    return df[df["volume"] > 0]  # buang bar kosong (akhir pekan/libur)


def fetch_range(sym: str, start_year: int, end_year: int, workers: int = 2) -> pd.DataFrame:
    now = pd.Timestamp.utcnow().tz_localize(None)
    jobs = [(y, m) for y in range(start_year, end_year + 1) for m in range(12)
            if pd.Timestamp(year=y, month=m + 1, day=1) < now.replace(day=1)]
    frames = []
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(fetch_month, sym, y, m): (y, m) for y, m in jobs}
        for f in cf.as_completed(futs):
            y, m = futs[f]
            try:
                frames.append(f.result())
            except Exception as e:  # noqa: BLE001
                print(f"  gagal {y}-{m + 1:02d}: {e}")
    df = pd.concat(frames).sort_index()
    return df[~df.index.duplicated()]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", default="XAUUSD")
    p.add_argument("--start", type=int, default=2015)
    p.add_argument("--end", type=int, default=pd.Timestamp.utcnow().year)
    p.add_argument("--out", default="data/XAUUSD_H1.csv")
    a = p.parse_args()
    df = fetch_range(a.symbol, a.start, a.end)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.index.name = "datetime"
    df.to_csv(a.out, float_format="%.3f")
    print(f"{len(df):,} bar H1 | {df.index[0]} s/d {df.index[-1]} UTC -> {a.out}")


if __name__ == "__main__":
    main()
