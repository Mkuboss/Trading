#!/usr/bin/env python3
"""Scan kombinasi dengan aturan: SL tetap 30 pips ($3), TANPA TP, SL bergerak (breakeven plus + trailing).

Diuji di 1 bulan terakhir dan bulan sebelumnya (data Yahoo GC=F M5/M15).
  python sl30_scan.py
"""
import itertools
import multiprocessing as mp

import numpy as np
import pandas as pd

import backtest as bt
import month_scan as ms
import research as rs

import os
SL_USD = float(os.environ.get("SL_USD", "3.0"))   # 30 pips = $3 jika 1 pip = $0.10; $30 jika 1 pip = $1
BE_TRIGGER = [None, 1.0 * SL_USD, 2.0 * SL_USD]   # pindah SL ke plus setelah profit $ ini (None = tanpa breakeven)
BE_PLUS = SL_USD / 3                              # SL plus: 1/3 SL di atas entry
TRAIL = [1.0 * SL_USD, 2.0 * SL_USD, 3.0 * SL_USD, 5.0 * SL_USD, 8.0 * SL_USD]  # jarak trailing ($)
TRAIL_START = [0.0, 2.0 * SL_USD, 4.0 * SL_USD]   # trailing aktif setelah profit $ ini
TFS = {"5m": "data/GC_5m_60d.csv", "15m": "data/GC_15m_60d.csv"}


def build(I, p):
    plan = rs.build_plan(I, {**p, "sl": 1.5, "exit": "rr2"})
    if plan is None:
        return None
    n = len(plan)
    plan["sl"] = SL_USD
    plan["tp"] = np.nan
    plan["trail"] = p["trail"]
    plan["trail_start"] = p["trail_start"]
    plan["be_trigger"] = np.nan if p["be"] is None else p["be"]
    plan["be_plus"] = BE_PLUS
    return plan


_D = {}


def _init():
    for tf, f in TFS.items():
        df = bt.load_csv(f)
        end = df.index[-1]
        m1 = int(np.searchsorted(df.index, end - pd.Timedelta(days=30)))
        m0 = int(np.searchsorted(df.index, end - pd.Timedelta(days=60)))
        _D[tf] = (df, rs.precompute(df), m0, m1)


def run(p):
    df, I, m0, m1 = _D[p["tf"]]
    plan = build(I, p)
    if plan is None:
        return None
    out = dict(p)
    for tag, (s, e) in {"now": (m1, len(df)), "prev": (max(m0, 200), m1)}.items():
        t, c = bt.run_backtest(df, plan, ms.CFG, s, e)
        st = bt.summarize("", t, c, ms.CFG.capital)
        r = np.array([x.r_multiple for x in t])
        out.update({f"{tag}_trades": st["trades"], f"{tag}_win": st["win_rate_%"], f"{tag}_expR": st["expectancy_R"],
                    f"{tag}_PF": st["profit_factor"], f"{tag}_ret": st["net_return_%"], f"{tag}_dd": st["max_dd_%"],
                    f"{tag}_avgwinR": r[r > 0].mean() if (r > 0).any() else np.nan,
                    f"{tag}_maxR": r.max() if len(r) else np.nan,
                    f"{tag}_R_no_top3": np.sort(r)[:-3].sum() if len(r) > 3 else np.nan})
    return out


def params():
    for tf, trig, tr, ax, se, sd, be, trl, ts in itertools.product(
            TFS, rs.TRIGGERS, rs.TRENDS, ["none", "adx20"], rs.SESSIONS, rs.SIDES, BE_TRIGGER, TRAIL, TRAIL_START):
        if trig == "asia_break" and (tf == "5m" or se == "ldn_ny"):
            continue
        if trig == "rsi_mr" and ax == "adx20":
            continue
        yield dict(tf=tf, trigger=trig, trend=tr, adx=ax, session=se, side=sd, be=be, trail=trl, trail_start=ts)


if __name__ == "__main__":
    ps = list(params())
    print(f"Menguji {len(ps):,} kombinasi (SL ${SL_USD}, tanpa TP, SL plus ${BE_PLUS}) ...", flush=True)
    with mp.Pool(mp.cpu_count(), initializer=_init) as pool:
        R = pd.DataFrame([r for r in pool.imap_unordered(run, ps, chunksize=32) if r])
    R.to_csv(f"results/slfix_scan_{SL_USD:g}.csv", index=False)
    ok = R[(R.now_trades >= 20) & (R.prev_trades >= 20)]
    both = ok[(ok.now_ret > 0) & (ok.prev_ret > 0)]
    print(f"Profit bulan ini: {(ok.now_ret > 0).sum():,} dari {len(ok):,} | profit di DUA bulan: {len(both):,}")
    both = both.assign(min_ret=both[["now_ret", "prev_ret"]].min(axis=1),
                       min_PF=both[["now_PF", "prev_PF"]].min(axis=1))
    cols = ["tf", "trigger", "trend", "adx", "session", "side", "be", "trail", "trail_start",
            "now_trades", "now_win", "now_PF", "now_ret", "now_dd", "now_R_no_top3",
            "prev_trades", "prev_win", "prev_PF", "prev_ret", "prev_dd", "prev_R_no_top3"]
    with pd.option_context("display.width", 300, "display.max_columns", 40, "display.float_format", "{:,.2f}".format):
        print("\n=== TOP 15 (profit di dua bulan, urut return terendah dari dua bulan) ===")
        print(both.sort_values("min_ret", ascending=False)[cols].head(15).to_string(index=False))
        print("\n=== TOP 10 yang TETAP profit tanpa 3 trade terbaik di dua bulan (robust) ===")
        rob = both[(both.now_R_no_top3 > 0) & (both.prev_R_no_top3 > 0)]
        print(f"jumlah: {len(rob):,}")
        print(rob.sort_values("min_ret", ascending=False)[cols].head(10).to_string(index=False))
        print("\n=== Pengaruh aturan SL bergerak (median return bulan ini, semua trigger) ===")
        print(ok.groupby(["be", "trail", "trail_start"], dropna=False).now_ret.median().unstack("trail").round(1).to_string())
