#!/usr/bin/env python3
"""Premis baru: SL jauh lebih besar ($30 / $45, yaitu "30-45 pips" kalau 1 pip = $1 di broker 2 desimal), entry di H1,
histori 2018-2026 (Dukascopy H1 spot). Di skala ini biaya transaksi (~$0,4) hanya ~1% dari risiko.
Exit: SL tetap, tanpa TP, BE close H1 + trailing chandelier (skala SL), atau partial 50%.
Validasi: walk-forward per tahun -> kombinasi harus profit di >= 7 dari 9 tahun; dilaporkan juga n_prof dan min_win.
  python scan_h1.py
"""
import itertools
import multiprocessing as mp

import numpy as np
import pandas as pd

import backtest as bt
import entry_scan as es
import hiwin_scan as hs
import research as rs

SLS = [30.0, 45.0]
MGMT = {"be10": (0.10, 0.10, 3.0, np.nan), "be20": (0.20, 0.15, 3.0, np.nan), "be33": (0.33, 0.25, 3.0, np.nan),
        "ptp50": (np.nan, 0.10, 3.0, 0.5)}  # (be_trigger, be_plus, trail, partial) dalam kelipatan SL
CFG = bt.Config(spread=0.30, slippage=0.10)
_D = {}


def _init():
    df = bt.load_csv("data/XAUUSD_H1.csv")
    _D["df"] = df
    _D["I"] = (es.precompute(df), rs.precompute(df))
    _D["years"] = sorted(set(df.index.year))


def run(p):
    df = _D["df"]; Inew, Iold = _D["I"]
    be, plus, trail, ptp = MGMT[p["mgmt"]]
    hs.SL_USD = p["sl"]
    plan = hs.build({**p, "be": be * p["sl"], "plus": plus * p["sl"], "trail": trail * p["sl"], "ts": 0.0}, Inew, Iold)
    if plan is None:
        return None
    plan["be_touch"] = False
    plan["partial_tp"], plan["partial_frac"] = ptp * p["sl"] if not np.isnan(ptp) else np.nan, 0.5
    t, c = bt.run_backtest(df, plan, CFG, 300, len(df))
    R = pd.Series([x.r_multiple for x in t], index=[x.entry_time for x in t], dtype=float)
    out = dict(p)
    yr = R.groupby(R.index.year)
    n_y, sum_y, win_y = yr.size(), yr.sum(), yr.apply(lambda x: (x > 0).mean() * 100)
    for y in _D["years"]:
        out[f"R{y}"] = sum_y.get(y, 0.0)
    out.update(n=len(R), win=(R > 0).mean() * 100 if len(R) else np.nan, expR=R.mean() if len(R) else np.nan,
               PF=R[R > 0].sum() / -R[R <= 0].sum() if (R <= 0).any() else np.inf,
               n_prof=int((sum_y > 0).sum()), years=len(sum_y), min_n=int(n_y.min()) if len(n_y) else 0,
               min_win=win_y.min() if len(win_y) else np.nan, maxdd_R=(R.cumsum() - R.cumsum().cummax()).min())
    return out


def params():
    fams = [("old", e) for e in hs.OLD if e != "asia_break"] + [("new", e) for e in hs.NEW]
    for (fam, en), bi, se, sd, sl, mg in itertools.product(fams, ["none", "h1", "d1"], ["all", "ldn", "ny"], ["both", "long"], SLS, MGMT):
        yield dict(tf="1h", fam=fam, entry=en, bias=bi, session=se, side=sd, sl=sl, mgmt=mg)


if __name__ == "__main__":
    ps = list(params())
    print(f"{len(ps)} kombinasi, data H1 2018-2026", flush=True)
    with mp.Pool(mp.cpu_count(), initializer=_init) as pool:
        R = pd.DataFrame([r for r in pool.imap_unordered(run, ps, chunksize=8) if r])
    R.to_csv("results/scan_h1.csv", index=False)
    yrs = [c for c in R.columns if c.startswith("R20")]
    COLS = ["entry", "bias", "session", "side", "sl", "mgmt", "n", "win", "expR", "PF", "min_win", "min_n", "n_prof", "years", "maxdd_R"] + yrs
    ok = R[R.min_n >= 10]
    with pd.option_context("display.width", 400, "display.max_columns", 60, "display.float_format", "{:,.2f}".format):
        print(f"\ncukup trade: {len(ok)} | profit semua tahun: {(ok.n_prof == ok.years).sum()} | >= 8/9: {(ok.n_prof >= 8).sum()} | >= 7/9: {(ok.n_prof >= 7).sum()}")
        print("\n=== n_prof >= 8, urut win ===")
        print(ok[ok.n_prof >= 8].sort_values("win", ascending=False)[COLS].head(30).to_string(index=False))
        print("\n=== win >= 78%, urut n_prof lalu expR ===")
        print(ok[ok.win >= 78].sort_values(["n_prof", "expR"], ascending=False)[COLS].head(25).to_string(index=False))
        print("\n=== rata-rata per mgmt / sl ===")
        print(ok.groupby(["sl", "mgmt"])[["win", "expR", "n_prof"]].mean())
