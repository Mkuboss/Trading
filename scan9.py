#!/usr/bin/env python3
"""Scan 9 periode dengan ruang pencarian SEMPIT (anti bias seleksi): manajemen dibekukan ke 3 struktur, yang dicari
hanya entry x timeframe x bias x sesi, plus filter volatilitas on/off. SL $4,5 tetap, tanpa TP tetap.
Struktur exit:
  be      : BE close M1 +0,45 -> +0,45, trailing $13,5                      (struktur lama, pembanding)
  ptp2    : partial 50% di +$2,25 (0,5R) lalu SL sisa ke +$0,30, trailing $13,5   (SL plus + biarkan sisa lari)
  ptp1    : partial 50% di +$1,50 lalu SL sisa ke +$0,30, trailing $13,5
Filter volatilitas (vol=1): tidak entry pada hari yang range hari sebelumnya > 1,5 x median range 20 hari.
  PERIODS=all9 python scan9.py
"""
import itertools
import multiprocessing as mp

import numpy as np
import pandas as pd

import backtest as bt
import hiwin_scan as hs
import mtf
import multi_scan as ms

SL = 4.5
MGMT = {"be": dict(be=0.45, plus=0.45, trail=13.5, ptp=np.nan),
        "ptp2": dict(be=np.nan, plus=0.30, trail=13.5, ptp=2.25),
        "ptp1": dict(be=np.nan, plus=0.30, trail=13.5, ptp=1.50)}
CFG = bt.Config(spread=0.30, slippage=0.10)
_VOL = {}


def _init():
    ms._init()
    for per, D in ms._D.items():
        df1 = D["df1"]
        rng = (df1.high.resample("D").max() - df1.low.resample("D").min()).dropna()
        hot = (rng.shift(1) > 1.5 * rng.shift(1).rolling(20, min_periods=5).median()).reindex(df1.index.normalize()).fillna(False).to_numpy()
        _VOL[per] = hot


def run(p):
    hs.SL_USD = SL
    m = MGMT[p["mgmt"]]
    out = dict(p)
    Rs, wks = [], []
    for per in ms.PERIODS:
        d, Inew, Iold, rule = ms._D[per][p["tf"]]
        plan = hs.build({**p, "be": m["be"], "plus": m["plus"], "trail": m["trail"], "ts": 0.0}, Inew, Iold)
        if plan is None:
            return None
        df1 = ms._D[per]["df1"]
        p1 = mtf.to_m1(plan, df1, rule)
        p1["be_touch"] = False
        p1["partial_tp"], p1["partial_frac"] = m["ptp"], 0.5
        if p["vol"]:
            p1["entry"] = np.where(_VOL[per], 0, p1["entry"])
        t, c = bt.run_backtest(df1, p1, CFG, 300, len(df1))
        s, R, wk = ms.stats(t, c, per)
        out.update(s); Rs.append(R); wks.append(wk)
    R, wk = pd.concat(Rs), pd.concat(wks)
    out.update(n=len(R), win=(R > 0).mean() * 100 if len(R) else np.nan, expR=R.mean() if len(R) else np.nan,
               PF=R[R > 0].sum() / -R[R <= 0].sum() if (R <= 0).any() else np.inf,
               min_win=min(out[f"{k}_win"] for k in ms.PERIODS), min_n=min(out[f"{k}_n"] for k in ms.PERIODS),
               n_prof=sum(out[f"{k}_ret"] > 0 for k in ms.PERIODS), weeks_profit=int((wk > 0).sum()), weeks=len(wk))
    return out


def params():
    fams = [("old", e) for e in hs.OLD] + [("new", e) for e in hs.NEW]
    for tf, (fam, en), bi, se, mg, vol in itertools.product(["1m", "5m", "15m"], fams, ["none", "m15", "h1"], ["asia", "ldn", "ny", "all"], MGMT, [0, 1]):
        if en == "asia_break" and (tf != "15m" or se != "all"):
            continue
        if tf == "1m" and (fam == "old" or en == "squeeze"):
            continue
        yield dict(tf=tf, fam=fam, entry=en, bias=bi, session=se, side="both", mgmt=mg, vol=vol)


COLS = ["tf", "entry", "bias", "session", "mgmt", "vol", "n", "win", "expR", "PF", "min_win", "min_n", "n_prof", "weeks_profit", "weeks"] + \
       [f"{k}_ret" for k in ms.PERIODS]

if __name__ == "__main__":
    ps = list(params())
    print(f"{len(ps)} kombinasi x {len(ms.PERIODS)} periode | SL ${SL} | {list(ms.PERIODS)}", flush=True)
    with mp.Pool(mp.cpu_count(), initializer=_init) as pool:
        R = pd.DataFrame([r for r in pool.imap_unordered(run, ps, chunksize=8) if r])
    R.to_csv("results/scan9.csv", index=False)
    ok = R[R.min_n >= 8]
    with pd.option_context("display.width", 400, "display.max_columns", 60, "display.float_format", "{:,.2f}".format):
        print(f"\ncukup trade: {len(ok)} | profit 9/9: {(ok.n_prof == 9).sum()} | 8/9: {(ok.n_prof == 8).sum()} | 7/9: {(ok.n_prof == 7).sum()}")
        print("\n=== profit >= 7/9, urut win ===")
        print(ok[ok.n_prof >= 7].sort_values("win", ascending=False)[COLS].head(30).to_string(index=False))
        print("\n=== win >= 78%, urut n_prof lalu expR ===")
        print(ok[ok.win >= 78].sort_values(["n_prof", "expR"], ascending=False)[COLS].head(25).to_string(index=False))
        print("\n=== rata-rata per struktur exit ===")
        print(ok.groupby("mgmt")[["win", "expR", "n_prof"]].mean())
        print(ok.groupby("vol")[["win", "expR", "n_prof"]].mean())
