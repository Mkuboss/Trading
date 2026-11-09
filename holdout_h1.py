#!/usr/bin/env python3
"""Uji HOLDOUT premis H1 (pra-registrasi 9 Nov 2026, ditulis sebelum data 2015-2017 dilihat).
Kandidat dibekukan dari scan_h1.py (data 2018-2026): SL $45 tetap, tanpa TP, BE close H1 +10% SL, trailing 3x SL.
  A. supertrend bias D1, semua sesi, buy & sell    (8/9 tahun profit, win 89%, PF 3,07)
  B. ema_pb bias D1, sesi NY, buy saja              (9/9 tahun, win 87,5%, PF 3,07)
  C. nr7 bias H1, sesi NY, buy saja                 (9/9 tahun, win 88,5%, PF 3,10)
Data holdout: Dukascopy H1 2015-2017 (emas: 2015 turun, 2016 naik lalu turun, 2017 naik moderat).
Kriteria lolos per kandidat (spread $0,30, slippage $0,10):
  - >= 2 dari 3 tahun profit, ΣR 2015-2017 > 0, win >= 80%, dan
  - ΣR harus > rata-rata entry ACAK dengan arah & manajemen sama (12 seed) di periode yang sama + 1 deviasi standar,
    supaya laba bukan sekadar drift arah pasar + mekanisme BE.
  python holdout_h1.py
"""
import numpy as np
import pandas as pd

import backtest as bt
import entry_scan as es
import hiwin_scan as hs
import research as rs

DATA = "data/XAUUSD_H1_2015_17.csv"
CFG = bt.Config(spread=0.30, slippage=0.10)
SL, BE, TRAIL = 45.0, 0.10, 3.0
CANDS = {"A supertrend d1 all both": dict(fam="old", entry="supertrend", bias="d1", session="all", side="both"),
         "B ema_pb d1 ny long": dict(fam="new", entry="ema_pb", bias="d1", session="ny", side="long"),
         "C nr7 h1 ny long": dict(fam="new", entry="nr7", bias="h1", session="ny", side="long")}


def trades(df, plan):
    t, c = bt.run_backtest(df, plan, CFG, 300, len(df))
    return pd.Series([x.r_multiple for x in t], index=pd.DatetimeIndex([x.entry_time for x in t]), dtype=float)


def bench(df, side, session, seed, n_target):
    rng = np.random.default_rng(seed)
    hr = df.index.hour
    ses = {"all": hr >= 0, "ny": (hr >= 13) & (hr < 20), "ldn": (hr >= 7) & (hr < 13)}[session]
    dirs = np.ones(len(df), int) if side == "long" else rng.choice([-1, 1], len(df))
    sig = np.where(ses & (rng.random(len(df)) < n_target * 2.5 / max(ses.sum(), 1)), dirs, 0)
    plan = pd.DataFrame({"entry": sig, "sl": SL, "tp": np.nan, "exit_long": False, "exit_short": False,
                         "be_trigger": BE * SL, "be_plus": BE * SL, "trail": TRAIL * SL}, index=df.index)
    return trades(df, plan)


if __name__ == "__main__":
    df = bt.load_csv(DATA)
    print(f"Data holdout: {len(df):,} bar H1 {df.index[0]} .. {df.index[-1]}")
    Inew, Iold = es.precompute(df), rs.precompute(df)
    hs.SL_USD = SL
    for name, spec in CANDS.items():
        plan = hs.build({**spec, "tf": "1h", "be": BE * SL, "plus": BE * SL, "trail": TRAIL * SL, "ts": 0.0}, Inew, Iold)
        plan["be_touch"] = False
        R = trades(df, plan)
        y = R.groupby(R.index.year).agg(["size", "sum", lambda x: (x > 0).mean() * 100])
        y.columns = ["n", "sumR", "win"]
        B = np.array([bench(df, spec["side"], spec["session"], s, len(R)).sum() for s in range(12)])
        win = (R > 0).mean() * 100
        ok = (y["sumR"] > 0).sum() >= 2 and R.sum() > 0 and win >= 80 and R.sum() > B.mean() + B.std()
        print(f"\n=== {name} === n={len(R)} win={win:.1f}% expR={R.mean():+.2f} ΣR={R.sum():+.1f} | acak ΣR={B.mean():+.1f}±{B.std():.1f}")
        print(y.round(1).to_string())
        print(f"  -> {'LOLOS' if ok else 'GAGAL'}")
