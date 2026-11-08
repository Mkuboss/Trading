#!/usr/bin/env python3
"""Tahap akhir: entry Asia yang konsisten muncul di scan SL 3/4.5/6 (NR7 M15 dan engulfing M5) diuji pada
grid SL 3..5 dolar + manajemen, sendiri-sendiri dan sebagai portofolio satu posisi. Semua di 3 periode sekaligus."""
import itertools
import multiprocessing as mp
import sys

import numpy as np
import pandas as pd

import backtest as bt
import hiwin_scan as hs
import mtf
import multi_scan as ms

ENTRIES = {
    "nr7_d1": dict(tf="15m", fam="new", entry="nr7", bias="d1", session="asia", side="both"),
    "nr7_h1": dict(tf="15m", fam="new", entry="nr7", bias="h1", session="asia", side="both"),
    "eng_m15": dict(tf="5m", fam="new", entry="engulf", bias="m15", session="asia", side="long"),
    "eng_none": dict(tf="5m", fam="new", entry="engulf", bias="none", session="asia", side="long"),
}
PORTS = {"nr7_d1+eng_m15": ["nr7_d1", "eng_m15"], "nr7_h1+eng_m15": ["nr7_h1", "eng_m15"], "nr7_d1+eng_none": ["nr7_d1", "eng_none"]}
SL = [3.0, 3.5, 4.0, 4.5, 5.0]
BE = [0.5, 0.75, 1.0, 1.25]
PLUS = [0.3, 0.45, 0.6]
TRAIL = [9.0, 13.5, 18.0]


def plan_m1(per, name, sl, be, plus, trail):
    e = ENTRIES[name]
    d, Inew, Iold, rule = ms._D[per][e["tf"]]
    hs.SL_USD = sl
    plan = hs.build({**e, "be": be, "plus": plus, "trail": trail, "ts": 0.0}, Inew, Iold)
    plan["be_touch"] = True
    return mtf.to_m1(plan, ms._D[per]["df1"], rule)


def run(p):
    out = dict(p)
    names = PORTS.get(p["name"], [p["name"]])
    Rs, wks = [], []
    for per in ms.PERIODS:
        plans = [plan_m1(per, n, p["sl"], p["be"], p["plus"], p["trail"]) for n in names]
        plan = plans[0].copy()
        for q in plans[1:]:  # gabung sinyal: kalau keduanya ada di bar yang sama, pakai yang pertama
            plan["entry"] = np.where(plan["entry"] != 0, plan["entry"], q["entry"])
        df1 = ms._D[per]["df1"]
        t, c = bt.run_backtest(df1, plan, bt.Config(spread=p["spread"]), 300, len(df1))
        s, R, wk = ms.stats(t, c, per)
        out.update(s); Rs.append(R); wks.append(wk)
    R, wk = pd.concat(Rs), pd.concat(wks)
    out.update(n=len(R), win=(R > 0).mean() * 100 if len(R) else np.nan, expR=R.mean() if len(R) else np.nan,
               PF=R[R > 0].sum() / -R[R <= 0].sum() if (R <= 0).any() else np.inf,
               min_win=min(out[f"{k}_win"] for k in ms.PERIODS), min_ret=min(out[f"{k}_ret"] for k in ms.PERIODS),
               weeks_profit=int((wk > 0).sum()), weeks=len(wk), no_top3=R.sort_values().iloc[:-3].sum(),
               streak=bt.summarize("", [], pd.Series(dtype=float), 1)["max_loss_streak"])
    return out


COLS = ["name", "sl", "be", "plus", "trail", "spread", "n", "win", "expR", "PF", "min_win", "min_ret", "weeks_profit", "weeks", "no_top3",
        "jan_n", "jan_win", "jan_ret", "augoct_n", "augoct_win", "augoct_ret", "octnov_n", "octnov_win", "octnov_ret"]

if __name__ == "__main__":
    names = list(ENTRIES) + list(PORTS)
    ps = [dict(name=n, sl=sl, be=be, plus=pl, trail=tr, spread=0.3) for n, sl, be, pl, tr in itertools.product(names, SL, BE, PLUS, TRAIL) if pl <= be]
    print(f"{len(ps)} kombinasi", flush=True)
    with mp.Pool(4, initializer=ms._init) as pool:
        R = pd.DataFrame(pool.imap_unordered(run, ps, chunksize=8))
    R.to_csv("results/final_grid.csv", index=False)
    with pd.option_context("display.width", 400, "display.max_columns", 60, "display.float_format", "{:,.2f}".format):
        tgt = R[(R.min_win >= 75) & (R.win >= 80) & (R.min_ret > 0) & (R.weeks_profit >= 0.6 * R.weeks)]
        print(f"\n=== TARGET: {len(tgt)} dari {len(R)} ===")
        print(tgt.groupby(["name", "sl"]).size().unstack(fill_value=0).to_string())
        for sl in SL:
            T = tgt[tgt.sl == sl]
            print(f"\n--- SL ${sl}: {len(T)} lolos; terbaik per nama (urut expR) ---")
            if len(T):
                print(T.sort_values("expR", ascending=False).groupby("name").head(2)[COLS].to_string(index=False))
        print("\n=== SL $3: terbaik per nama walau tidak lolos (urut win, syarat profit semua periode) ===")
        T = R[(R.sl == 3.0) & (R.min_ret > 0)]
        print(T.sort_values("win", ascending=False).groupby("name").head(1)[COLS].to_string(index=False))
