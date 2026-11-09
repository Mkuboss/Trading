#!/usr/bin/env python3
"""Scan multi-periode (3 rezim pasar, data spot Dukascopy M1): kandidat harus lolos di SEMUA periode.
Target: SL $3 tetap, tanpa TP, breakeven cepat (gaya tick) + trailing, win >= 80% gabungan, >= 75% & profit tiap periode.
  python multi_scan.py            # scan penuh
  python multi_scan.py --bench    # hanya benchmark entry acak (baseline win rate dari manajemen SL saja)
"""
import itertools
import multiprocessing as mp
import os
import sys

import numpy as np
import pandas as pd

import backtest as bt
import entry_scan as es
import hiwin_scan as hs
import mtf
import research as rs

ALL_PERIODS = {"jan": "data/duka_m1_jan26.csv", "augoct": "data/duka_m1_augoct26.csv", "octnov": "data/duka_m1_octnov26.csv",
               "nov25": "data/duka_m1_nov25.csv", "mar26": "data/duka_m1_mar26.csv", "jun26": "data/duka_m1_jun26.csv",
               "feb26": "data/duka_m1_feb26.csv", "apr26": "data/duka_m1_apr26.csv", "sep25": "data/duka_m1_sep25.csv"}
# PERIODS=jan,augoct,octnov (default 3 periode riset awal) | PERIODS=all6 -> 6 periode (3 riset + 3 bekas holdout)
_sel = os.environ.get("PERIODS", "jan,augoct,octnov")
_sel = {"all6": ["jan", "augoct", "octnov", "nov25", "mar26", "jun26"],
        "all9": ["jan", "augoct", "octnov", "nov25", "mar26", "jun26", "feb26", "apr26", "sep25"]}.get(_sel, _sel.split(","))
PERIODS = {k: ALL_PERIODS[k] for k in _sel}
TAG = os.environ.get("TAG", "")
SIG_TFS = {"1m": "1min", "5m": "5min", "15m": "15min"}
SL_USD = float(os.environ.get("SL_USD", 3.0))
BE_MODE = os.environ.get("BE_MODE", "m1close")   # m1close: pemicu BE di close M1 | tick: di high/low M1
hs.SL_USD = SL_USD
_k = SL_USD / 3.0
MGMT = [(0.5 * _k, 0.3 * _k, 9.0 * _k), (0.75 * _k, 0.3 * _k, 9.0 * _k), (1.0 * _k, 0.5 * _k, 9.0 * _k)]   # (be_trigger, be_plus, trail) dalam $, diskalakan ke SL
BIAS = ["none", "m15", "h1", "d1"]
SESSION = ["all", "asia", "ldn", "ny"]
SIDE = ["both", "long", "short"]
CFG = bt.Config(capital=10_000, risk_pct=1.0, spread=0.30)
_D = {}


def _init():
    for per, path in PERIODS.items():
        df1 = bt.load_csv(path)
        _D[per] = {"df1": df1}
        for tf, rule in SIG_TFS.items():
            d = df1 if tf == "1m" else mtf.resample(df1, rule)
            _D[per][tf] = (d, es.precompute(d), rs.precompute(d), rule)


def stats(t, c, tag):
    st = bt.summarize("", t, c, CFG.capital)
    R = pd.Series([x.r_multiple for x in t], index=[x.entry_time for x in t], dtype=float)
    wk = R.groupby(R.index.to_period("W")).sum() if len(R) else pd.Series(dtype=float)
    return {f"{tag}_n": st["trades"], f"{tag}_win": st["win_rate_%"], f"{tag}_expR": st["expectancy_R"],
            f"{tag}_PF": st["profit_factor"], f"{tag}_ret": st["net_return_%"], f"{tag}_dd": st["max_dd_%"]}, R, wk


def run(p):
    out = dict(p)
    Rs, wks = [], []
    for per in PERIODS:
        d, Inew, Iold, rule = _D[per][p["tf"]]
        plan = hs.build({**p, "ts": 0.0}, Inew, Iold)
        if plan is None:
            return None
        df1 = _D[per]["df1"]
        plan1 = mtf.to_m1(plan, df1, rule)
        plan1["be_touch"] = BE_MODE == "tick"
        t, c = bt.run_backtest(df1, plan1, CFG, 300, len(df1))
        s, R, wk = stats(t, c, per)
        out.update(s)
        Rs.append(R)
        wks.append(wk)
    R = pd.concat(Rs)
    wk = pd.concat(wks)
    out.update(n=len(R), win=(R > 0).mean() * 100 if len(R) else np.nan, expR=R.mean() if len(R) else np.nan,
               min_win=min(out[f"{k}_win"] for k in PERIODS), min_ret=min(out[f"{k}_ret"] for k in PERIODS),
               min_n=min(out[f"{k}_n"] for k in PERIODS), weeks_profit=int((wk > 0).sum()), weeks=len(wk))
    return out


def params():
    fams = [("old", e) for e in hs.OLD] + [("new", e) for e in hs.NEW]
    for tf, (fam, en), bi, se, sd, (be, plus, trl) in itertools.product(SIG_TFS, fams, BIAS, SESSION, SIDE, MGMT):
        if en == "asia_break" and (tf != "15m" or se != "all"):
            continue
        if tf == "1m" and en in ("supertrend", "donch55", "bb_squeeze", "squeeze"):
            continue
        yield dict(tf=tf, fam=fam, entry=en, bias=bi, session=se, side=sd, be=be, plus=plus, trail=trl)


def bench(args):
    """Entry acak dengan manajemen yang sama: baseline win rate yang murni berasal dari SL/BE, bukan dari entry."""
    per, session, be, plus, trl, seed = args
    df1 = _D[per]["df1"]
    rng = np.random.default_rng(seed)
    hr = df1.index.hour
    ses = {"all": hr >= 0, "asia": hr < 7, "ldn": (hr >= 7) & (hr < 13), "ny": (hr >= 13) & (hr < 20)}[session]
    sig = np.where(ses & (rng.random(len(df1)) < 1 / 90), rng.choice([-1, 1], len(df1)), 0)
    plan = pd.DataFrame({"entry": sig, "sl": 3.0, "tp": np.nan, "exit_long": False, "exit_short": False,
                         "be_trigger": be, "be_plus": plus, "trail": trl, "be_touch": BE_MODE == "tick"}, index=df1.index)
    t, c = bt.run_backtest(df1, plan, CFG, 300, len(df1))
    st = bt.summarize("", t, c, CFG.capital)
    return dict(per=per, session=session, be=be, plus=plus, trail=trl, n=st["trades"], win=st["win_rate_%"], expR=st["expectancy_R"])


COLS = ["tf", "fam", "entry", "bias", "session", "side", "be", "plus", "trail", "n", "win", "expR", "weeks_profit", "weeks"] + \
       [f"{k}_{m}" for k in PERIODS for m in ("n", "win", "expR", "PF", "ret")]

if __name__ == "__main__":
    print("Periode:", PERIODS, "| SL $", SL_USD, "| BE_MODE", BE_MODE, "| MGMT", MGMT, flush=True)
    if "--bench" in sys.argv:
        jobs = [(per, se, be, plus, trl, seed) for per in PERIODS for se in SESSION for be, plus, trl in MGMT for seed in range(5)]
        with mp.Pool(mp.cpu_count(), initializer=_init) as pool:
            B = pd.DataFrame(pool.map(bench, jobs))
        B.to_csv(f"results/multi_bench_sl{SL_USD:g}_{BE_MODE}{TAG}.csv", index=False)
        with pd.option_context("display.width", 250, "display.float_format", "{:,.2f}".format):
            print(B.groupby(["be", "plus", "session", "per"])[["n", "win", "expR"]].mean().to_string())
        sys.exit()
    ps = list(params())
    print(f"Menguji {len(ps):,} kombinasi x {len(PERIODS)} periode ...", flush=True)
    with mp.Pool(mp.cpu_count(), initializer=_init) as pool:
        R = pd.DataFrame([r for r in pool.imap_unordered(run, ps, chunksize=16) if r])
    R.to_csv(f"results/multi_scan_sl{SL_USD:g}_{BE_MODE}{TAG}.csv", index=False)
    ok = R[R.min_n >= 10]
    hw = ok[(ok.min_win >= 75) & (ok.win >= 80)]
    tgt = hw[(hw.min_ret > 0) & (hw.weeks_profit >= 0.6 * hw.weeks)]
    print(f"Cukup trade: {len(ok):,} | win>=75% tiap periode & >=80% gabungan: {len(hw):,} | + profit tiap periode & >=60% minggu: {len(tgt):,}")
    with pd.option_context("display.width", 400, "display.max_columns", 60, "display.float_format", "{:,.2f}".format):
        print("\n=== TARGET TERPENUHI ===")
        print(tgt.sort_values("min_ret", ascending=False)[COLS].head(25).to_string(index=False))
        print("\n=== win>=75% tiap periode (diurutkan min_ret) ===")
        print(hw.sort_values("min_ret", ascending=False)[COLS].head(15).to_string(index=False))
        p = ok[(ok.min_ret > 0)]
        print(f"\n=== profit di semua periode: {len(p)} (diurutkan win gabungan) ===")
        print(p.sort_values("win", ascending=False)[COLS].head(20).to_string(index=False))
