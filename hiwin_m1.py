#!/usr/bin/env python3
"""Target: SL $3 tetap, tanpa TP, SL bergerak, win rate >= 80%, profit konsisten.
Sinyal di M1/M5/M15, eksekusi & manajemen SL (breakeven cepat + trailing) di M1.
  python hiwin_m1.py
"""
import itertools
import multiprocessing as mp
import os

import numpy as np
import pandas as pd

import backtest as bt
import entry_scan as es
import hiwin_scan as hs
import mtf
import research as rs

SL_USD = 3.0
SIG_TFS = {"1m": "1min", "5m": "5min", "15m": "15min"}
BE_TRIG = [0.5, 0.75, 1.0, 1.5]
BE_PLUS = [0.3, 0.6, 1.0]
TRAIL = [4.5, 9.0, 15.0]
BIAS = ["none", "m15", "h1", "d1"]
SESSION = ["all", "asia", "ldn", "ny"]
SIDE = ["both", "long", "short"]
CFG = bt.Config(capital=10_000, risk_pct=1.0, spread=0.40)
_D = {}


def _init():
    df1 = bt.load_csv("data/GC_1m_30d.csv")
    _D["df1"] = df1
    mid = df1.index[0] + (df1.index[-1] - df1.index[0]) / 2
    _D["mid"] = int(np.searchsorted(df1.index, mid))
    for tf, rule in SIG_TFS.items():
        d = df1 if tf == "1m" else mtf.resample(df1, rule)
        _D[tf] = (d, es.precompute(d), rs.precompute(d), rule)


def run(p):
    d, Inew, Iold, rule = _D[p["tf"]]
    plan = hs.build({**p, "ts": 0.0}, Inew, Iold)
    if plan is None:
        return None
    df1 = _D["df1"]
    plan1 = mtf.to_m1(plan, df1, rule)
    out = dict(p)
    wk_all = []
    for tag, (s, e) in {"h1": (300, _D["mid"]), "h2": (_D["mid"], len(df1))}.items():
        t, c = bt.run_backtest(df1, plan1, CFG, s, e)
        st = bt.summarize("", t, c, CFG.capital)
        R = pd.Series([x.r_multiple for x in t], index=[x.entry_time for x in t])
        wk_all.append(R.groupby(R.index.to_period("W")).sum() if len(R) else pd.Series(dtype=float))
        out.update({f"{tag}_trades": st["trades"], f"{tag}_win": st["win_rate_%"], f"{tag}_PF": st["profit_factor"],
                    f"{tag}_ret": st["net_return_%"], f"{tag}_dd": st["max_dd_%"], f"{tag}_expR": st["expectancy_R"],
                    f"{tag}_no_top1": R.sort_values().iloc[:-1].sum() if len(R) > 1 else np.nan})
    wk = pd.concat(wk_all)
    out["weeks_profit"], out["weeks"] = int((wk > 0).sum()), len(wk)
    return out


def params():
    fams = [("old", e) for e in hs.OLD] + [("new", e) for e in hs.NEW]
    for tf, (fam, en), bi, se, sd, be, plus, trl in itertools.product(
            SIG_TFS, fams, BIAS, SESSION, SIDE, BE_TRIG, BE_PLUS, TRAIL):
        if en == "asia_break" and (tf != "15m" or se != "all"):
            continue
        if tf == "1m" and en in ("supertrend", "donch55", "bb_squeeze", "squeeze"):
            continue
        yield dict(tf=tf, fam=fam, entry=en, bias=bi, session=se, side=sd, be=be, plus=plus, trail=trl)


COLS = ["tf", "fam", "entry", "bias", "session", "side", "be", "plus", "trail", "weeks_profit", "weeks",
        "h1_trades", "h1_win", "h1_expR", "h1_PF", "h1_ret", "h1_dd", "h2_trades", "h2_win", "h2_expR", "h2_PF", "h2_ret", "h2_dd"]

if __name__ == "__main__":
    ps = list(params())
    print(f"Menguji {len(ps):,} kombinasi (M1-managed, target win>=80%) ...", flush=True)
    with mp.Pool(mp.cpu_count(), initializer=_init) as pool:
        R = pd.DataFrame([r for r in pool.imap_unordered(run, ps, chunksize=32) if r])
    R.to_csv("results/hiwin_m1.csv", index=False)
    ok = R[(R.h1_trades >= 10) & (R.h2_trades >= 10)]
    hw = ok[(ok.h1_win >= 80) & (ok.h2_win >= 80)]
    prof = hw[(hw.h1_ret > 0) & (hw.h2_ret > 0)]
    tgt = prof[(prof.weeks_profit >= 3) & (prof.h1_PF >= 1.2) & (prof.h2_PF >= 1.2)]
    print(f"Cukup trade: {len(ok):,} | win>=80% dua paruh: {len(hw):,} | +profit dua paruh: {len(prof):,} | +>=3/4 minggu & PF>=1.2: {len(tgt):,}")
    with pd.option_context("display.width", 350, "display.max_columns", 40, "display.float_format", "{:,.2f}".format):
        for title, D in [("TARGET TERPENUHI", tgt), ("win>=80% & profit dua paruh", prof)]:
            print(f"\n=== {title} ===")
            print(D.assign(m=D[["h1_ret", "h2_ret"]].min(axis=1)).sort_values("m", ascending=False)[COLS].head(20).to_string(index=False))
        p70 = ok[(ok.h1_win >= 70) & (ok.h2_win >= 70) & (ok.h1_ret > 0) & (ok.h2_ret > 0)]
        print(f"\n=== win>=70% & profit dua paruh: {len(p70)} ===")
        print(p70.assign(m=p70[["h1_ret", "h2_ret"]].min(axis=1)).sort_values("m", ascending=False)[COLS].head(15).to_string(index=False))
