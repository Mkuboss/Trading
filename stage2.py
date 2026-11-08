#!/usr/bin/env python3
"""Tahap 2: untuk entry yang profit di semua periode, uji grid manajemen SL yang lebih luas (be/plus/trail/partial)."""
import itertools
import multiprocessing as mp

import numpy as np
import pandas as pd

import backtest as bt
import hiwin_scan as hs
import mtf
import multi_scan as ms

CANDS = [
    dict(tf="15m", fam="new", entry="nr7", bias="h1", session="asia", side="both"),
    dict(tf="15m", fam="new", entry="nr7", bias="d1", session="asia", side="both"),
    dict(tf="15m", fam="new", entry="nr7", bias="none", session="asia", side="both"),
    dict(tf="5m", fam="new", entry="ema_pb", bias="m15", session="ldn", side="short"),
    dict(tf="5m", fam="new", entry="ema_pb", bias="m15", session="ldn", side="both"),
    dict(tf="5m", fam="new", entry="engulf", bias="m15", session="ldn", side="both"),
    dict(tf="15m", fam="new", entry="pin", bias="m15", session="ldn", side="both"),
    dict(tf="5m", fam="new", entry="ema_pb", bias="d1", session="asia", side="both"),
    dict(tf="5m", fam="new", entry="nr7", bias="h1", session="all", side="long"),
    dict(tf="15m", fam="old", entry="macd", bias="h1", session="all", side="long"),
]
BE = [0.3, 0.4, 0.5, 0.6, 0.75]
PLUS = [0.25, 0.3, 0.4, 0.5]
TRAIL = [4.5, 9.0, 15.0]
PTP = [None, 1.0, 1.5, 2.0]


def run(p):
    out = dict(p)
    Rs, wks = [], []
    for per in ms.PERIODS:
        d, Inew, Iold, rule = ms._D[per][p["tf"]]
        plan = hs.build({**p, "ts": 0.0}, Inew, Iold)
        plan["be_touch"] = True
        if p["ptp"] is not None:
            plan["partial_tp"], plan["partial_frac"] = p["ptp"], 0.5
        df1 = ms._D[per]["df1"]
        plan1 = mtf.to_m1(plan, df1, rule)
        t, c = bt.run_backtest(df1, plan1, ms.CFG, 300, len(df1))
        s, R, wk = ms.stats(t, c, per)
        out.update(s); Rs.append(R); wks.append(wk)
    R, wk = pd.concat(Rs), pd.concat(wks)
    out.update(n=len(R), win=(R > 0).mean() * 100, expR=R.mean(), min_win=min(out[f"{k}_win"] for k in ms.PERIODS),
               min_ret=min(out[f"{k}_ret"] for k in ms.PERIODS), weeks_profit=int((wk > 0).sum()), weeks=len(wk),
               no_top3=R.sort_values().iloc[:-3].sum())
    return out


if __name__ == "__main__":
    ps = [dict(**c, be=be, plus=pl, trail=tr, ptp=pt) for c in CANDS for be, pl, tr, pt in itertools.product(BE, PLUS, TRAIL, PTP) if pl <= be]
    print(f"{len(ps)} kombinasi", flush=True)
    with mp.Pool(4, initializer=ms._init) as pool:
        R = pd.DataFrame(pool.imap_unordered(run, ps, chunksize=8))
    R.to_csv("results/stage2.csv", index=False)
    cols = ["tf", "entry", "bias", "session", "side", "be", "plus", "trail", "ptp", "n", "win", "expR", "min_win", "min_ret", "weeks_profit", "weeks", "no_top3",
            "jan_n", "jan_win", "jan_ret", "augoct_n", "augoct_win", "augoct_ret", "octnov_n", "octnov_win", "octnov_ret"]
    with pd.option_context("display.width", 400, "display.max_columns", 60, "display.float_format", "{:,.2f}".format):
        tgt = R[(R.min_win >= 75) & (R.win >= 80) & (R.min_ret > 0)]
        print(f"\n=== TARGET (win>=80% gabungan, >=75% & profit tiap periode): {len(tgt)} ===")
        print(tgt.sort_values("min_ret", ascending=False)[cols].head(30).to_string(index=False))
        near = R[(R.min_win >= 70) & (R.win >= 78) & (R.min_ret > 0)]
        print(f"\n=== Mendekati (win>=78% gabungan, >=70% & profit tiap periode): {len(near)} ===")
        print(near.sort_values("expR", ascending=False)[cols].head(30).to_string(index=False))
        print("\n=== Per entry: win tertinggi yang masih profit semua periode ===")
        P = R[R.min_ret > 0]
        print(P.sort_values("win", ascending=False).groupby(["tf", "entry", "bias", "session", "side"]).head(1)[cols].to_string(index=False))
