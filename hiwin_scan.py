#!/usr/bin/env python3
"""Target: SL $3 tetap, tanpa TP, SL bergerak, WIN RATE >= 80% di dua bulan, tetap profit, >= 6/9 minggu profit.
Kunci win rate tinggi: SL cepat dipindah ke plus (breakeven cepat), sisanya trailing.
  python hiwin_scan.py
"""
import itertools
import multiprocessing as mp

import numpy as np
import pandas as pd

import backtest as bt
import entry_scan as es
import research as rs

SL_USD = 3.0
BE_TRIG = [0.75, 1.0, 1.5, 2.0]
BE_PLUS = [0.3, 0.6]
TRAIL = [4.5, 9.0, 15.0]
TRAIL_START = [0.0, 6.0]
BIAS = ["none", "m15", "h1", "d1"]
SESSION = ["all", "asia", "ldn", "ny"]
SIDE = ["both", "long", "short"]
OLD = ["donch20", "donch55", "ema_pb", "ema_cross", "macd", "supertrend", "bb_squeeze", "rsi_mr", "asia_break"]
NEW = ["sweep", "ema_pb", "retest", "engulf", "nr7", "inside", "ignite", "pin", "squeeze"]
_D = {}


def _init():
    for tf, f in es.TFS.items():
        df = bt.load_csv(f)
        end = df.index[-1]
        m1 = int(np.searchsorted(df.index, end - pd.Timedelta(days=30)))
        m0 = max(int(np.searchsorted(df.index, end - pd.Timedelta(days=60))), 200)
        _D[tf] = (df, es.precompute(df), rs.precompute(df), m0, m1)


def signals(p, Inew, Iold):
    if p["fam"] == "old":
        t = rs.trigger(p["entry"], Iold)
        if t is None:
            return None
        return t
    return es.entry(p["entry"], Inew)


def build(p, Inew, Iold):
    t = signals(p, Inew, Iold)
    if t is None:
        return None
    long, short = (x.fillna(False).astype(bool) for x in t)
    c = Inew["c"]
    if p["bias"] != "none":
        b = Inew[f"bias_{p['bias']}"]
        long, short = long & (b > 0), short & (b < 0)
    hr = Inew["hour"]
    ses = {"all": hr >= 0, "asia": hr < 7, "ldn": (hr >= 7) & (hr < 13), "ny": (hr >= 13) & (hr < 20)}[p["session"]]
    long, short = long & ses, short & ses
    if p["side"] == "long":
        short = short & False
    elif p["side"] == "short":
        long = long & False
    no = pd.Series(False, index=c.index)
    plan = bt._plan(pd.DataFrame(index=c.index), long, short, pd.Series(SL_USD, index=c.index), np.nan, no, no)
    plan["be_trigger"], plan["be_plus"], plan["trail"], plan["trail_start"] = p["be"], p["plus"], p["trail"], p["ts"]
    return plan


def run(p):
    df, Inew, Iold, m0, m1 = _D[p["tf"]]
    plan = build(p, Inew, Iold)
    if plan is None:
        return None
    out = dict(p)
    wk_all = []
    for tag, (s, e) in {"prev": (m0, m1), "now": (m1, len(df))}.items():
        t, c = bt.run_backtest(df, plan, es.CFG, s, e)
        st = bt.summarize("", t, c, es.CFG.capital)
        R = pd.Series([x.r_multiple for x in t], index=[x.entry_time for x in t])
        wk_all.append(R.groupby(R.index.to_period("W")).sum() if len(R) else pd.Series(dtype=float))
        out.update({f"{tag}_trades": st["trades"], f"{tag}_win": st["win_rate_%"], f"{tag}_PF": st["profit_factor"],
                    f"{tag}_ret": st["net_return_%"], f"{tag}_dd": st["max_dd_%"], f"{tag}_expR": st["expectancy_R"],
                    f"{tag}_no_top1": R.sort_values().iloc[:-1].sum() if len(R) > 1 else np.nan})
    wk = pd.concat(wk_all)
    out["weeks_profit"], out["weeks"] = int((wk > 0).sum()), len(wk)
    return out


def params():
    fams = [("old", e) for e in OLD] + [("new", e) for e in NEW]
    for tf, (fam, en), bi, se, sd, be, plus, trl, ts in itertools.product(
            es.TFS, fams, BIAS, SESSION, SIDE, BE_TRIG, BE_PLUS, TRAIL, TRAIL_START):
        if en == "asia_break" and (tf == "5m" or se != "all"):
            continue
        if ts > 0 and ts < be:
            continue
        yield dict(tf=tf, fam=fam, entry=en, bias=bi, session=se, side=sd, be=be, plus=plus, trail=trl, ts=ts)


COLS = ["tf", "fam", "entry", "bias", "session", "side", "be", "plus", "trail", "ts", "weeks_profit", "weeks",
        "prev_trades", "prev_win", "prev_expR", "prev_PF", "prev_ret", "prev_dd", "prev_no_top1",
        "now_trades", "now_win", "now_expR", "now_PF", "now_ret", "now_dd", "now_no_top1"]

if __name__ == "__main__":
    ps = list(params())
    print(f"Menguji {len(ps):,} kombinasi (target win>=80%) ...", flush=True)
    with mp.Pool(mp.cpu_count(), initializer=_init) as pool:
        R = pd.DataFrame([r for r in pool.imap_unordered(run, ps, chunksize=64) if r])
    R.to_csv("results/hiwin_scan.csv", index=False)
    ok = R[(R.prev_trades >= 20) & (R.now_trades >= 20)]
    hw = ok[(ok.prev_win >= 80) & (ok.now_win >= 80)]
    prof = hw[(hw.prev_ret > 0) & (hw.now_ret > 0)]
    tgt = prof[(prof.weeks_profit >= 6) & (prof.prev_no_top1 > 0) & (prof.now_no_top1 > 0)]
    print(f"Cukup trade: {len(ok):,} | win>=80% dua bulan: {len(hw):,} | +profit dua bulan: {len(prof):,} | +>=6/9 minggu & tanpa top1: {len(tgt):,}")
    with pd.option_context("display.width", 350, "display.max_columns", 40, "display.float_format", "{:,.2f}".format):
        print("\n=== TARGET TERPENUHI ===")
        print(tgt.assign(m=tgt[["prev_ret", "now_ret"]].min(axis=1)).sort_values("m", ascending=False)[COLS].head(20).to_string(index=False))
        print("\n=== Win>=80% & profit dua bulan (top by min return) ===")
        print(prof.assign(m=prof[["prev_ret", "now_ret"]].min(axis=1)).sort_values("m", ascending=False)[COLS].head(15).to_string(index=False))
        print("\n=== Win rate tertinggi yang profit dua bulan, batas win >=70% ===")
        p70 = ok[(ok.prev_win >= 70) & (ok.now_win >= 70) & (ok.prev_ret > 0) & (ok.now_ret > 0)]
        print(p70.assign(m=p70[["prev_ret", "now_ret"]].min(axis=1)).sort_values("m", ascending=False)[COLS].head(15).to_string(index=False))
