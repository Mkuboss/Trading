#!/usr/bin/env python3
"""Tahap 2 di 6 periode: entry yang profit di >= 5/6 periode pada scan 6 periode (results/multi_scan_sl4.5_m1close_6per.csv)
diuji dengan grid manajemen lebih luas (pemicu BE lebih kecil, trailing, lock_frac/ratchet) sendiri dan sebagai portofolio.
  PERIODS=all6 SL_USD=4.5 python stage2_6per.py
"""
import itertools
import multiprocessing as mp

import numpy as np
import pandas as pd

import backtest as bt
import hiwin_scan as hs
import mtf
import multi_scan as ms

ENTRIES = {
    "eng1_ldn_s": dict(tf="1m", fam="new", entry="engulf", bias="m15", session="ldn", side="short"),
    "emapb1_ldn_s": dict(tf="1m", fam="new", entry="ema_pb", bias="m15", session="ldn", side="short"),
    "sweep1_ldn_s": dict(tf="1m", fam="new", entry="sweep", bias="m15", session="ldn", side="short"),
    "donch55_asia": dict(tf="15m", fam="old", entry="donch55", bias="m15", session="asia", side="both"),
    "nr7_5_ny_l": dict(tf="5m", fam="new", entry="nr7", bias="m15", session="ny", side="long"),
    "eng5_asia_d1": dict(tf="5m", fam="new", entry="engulf", bias="d1", session="asia", side="both"),
    "emax5_ny": dict(tf="old", fam="old", entry="ema_cross", bias="m15", session="ny", side="both"),
    "nr7_15_asia_d1": dict(tf="15m", fam="new", entry="nr7", bias="d1", session="asia", side="both"),
    "macd5_asia_s": dict(tf="5m", fam="old", entry="macd", bias="none", session="asia", side="short"),
}
ENTRIES["emax5_ny"]["tf"] = "5m"
PORTS = {
    "eng1_ldn_s+nr7_15_asia_d1": ["eng1_ldn_s", "nr7_15_asia_d1"],
    "eng1_ldn_s+donch55_asia": ["eng1_ldn_s", "donch55_asia"],
    "eng1_ldn_s+nr7_5_ny_l": ["eng1_ldn_s", "nr7_5_ny_l"],
    "eng1_ldn_s+emax5_ny": ["eng1_ldn_s", "emax5_ny"],
    "eng1_ldn_s+donch55_asia+nr7_5_ny_l": ["eng1_ldn_s", "donch55_asia", "nr7_5_ny_l"],
    "nr7_15_asia_d1+donch55_asia": ["nr7_15_asia_d1", "donch55_asia"],
}
BE = [0.45, 0.6, 0.75, 1.0]
PLUS = [0.3, 0.45, 0.6]
TRAIL = [9.0, 13.5, 18.0, np.nan]
LOCK = [np.nan, 0.5, 0.7]
CFG = bt.Config(spread=0.30, slippage=0.10)


def plan_m1(per, name, be, plus, trail, lock):
    e = ENTRIES[name]
    d, Inew, Iold, rule = ms._D[per][e["tf"]]
    plan = hs.build({**e, "be": be, "plus": plus, "trail": trail, "ts": 0.0}, Inew, Iold)
    p1 = mtf.to_m1(plan, ms._D[per]["df1"], rule)
    p1["be_touch"] = False
    p1["lock_frac"] = lock
    return p1


def run(p):
    out = dict(p)
    names = PORTS.get(p["name"], [p["name"]])
    Rs, wks = [], []
    for per in ms.PERIODS:
        plans = [plan_m1(per, n, p["be"], p["plus"], p["trail"], p["lock"]) for n in names]
        plan = plans[0].copy()
        for q in plans[1:]:
            plan["entry"] = np.where(plan["entry"] != 0, plan["entry"], q["entry"])
        df1 = ms._D[per]["df1"]
        t, c = bt.run_backtest(df1, plan, CFG, 300, len(df1))
        s, R, wk = ms.stats(t, c, per)
        out.update(s); Rs.append(R); wks.append(wk)
    R, wk = pd.concat(Rs), pd.concat(wks)
    out.update(n=len(R), win=(R > 0).mean() * 100 if len(R) else np.nan, expR=R.mean() if len(R) else np.nan,
               PF=R[R > 0].sum() / -R[R <= 0].sum() if (R <= 0).any() else np.inf,
               min_win=min(out[f"{k}_win"] for k in ms.PERIODS), min_ret=min(out[f"{k}_ret"] for k in ms.PERIODS),
               n_prof=sum(out[f"{k}_ret"] > 0 for k in ms.PERIODS),
               weeks_profit=int((wk > 0).sum()), weeks=len(wk), no_top5=R.sort_values().iloc[:-5].sum())
    return out


COLS = ["name", "be", "plus", "trail", "lock", "n", "win", "expR", "PF", "min_win", "min_ret", "n_prof", "weeks_profit", "weeks", "no_top5"] + \
       [f"{k}_ret" for k in ms.PERIODS]

if __name__ == "__main__":
    hs.SL_USD = ms.SL_USD
    ps = [dict(name=n, be=b, plus=pl, trail=t, lock=lk) for n, b, pl, t, lk in
          itertools.product(list(ENTRIES) + list(PORTS), BE, PLUS, TRAIL, LOCK) if pl <= b]
    print(f"{len(ps)} kombinasi x {len(ms.PERIODS)} periode, SL ${ms.SL_USD}", flush=True)
    with mp.Pool(mp.cpu_count(), initializer=ms._init) as pool:
        R = pd.DataFrame(pool.imap_unordered(run, ps, chunksize=4))
    R.to_csv(f"results/stage2_6per_sl{ms.SL_USD:g}.csv", index=False)
    with pd.option_context("display.width", 400, "display.max_columns", 60, "display.float_format", "{:,.2f}".format):
        print("\n=== profit di 6/6 periode, urut win ===")
        print(R[R.n_prof == 6].sort_values("win", ascending=False)[COLS].head(30).to_string(index=False))
        print("\n=== win >= 78% gabungan, urut n_prof lalu expR ===")
        print(R[R.win >= 78].sort_values(["n_prof", "expR"], ascending=False)[COLS].head(30).to_string(index=False))
        print("\n=== min_win >= 75% ===")
        print(R[R.min_win >= 75].sort_values("expR", ascending=False)[COLS].head(20).to_string(index=False))
