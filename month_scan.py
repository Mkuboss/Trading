#!/usr/bin/env python3
"""Scan semua kombinasi teknikal di 1 bulan terakhir (M5/M15/H1), cek ulang di bulan sebelumnya.

  python month_scan.py            # memakai data Yahoo GC=F 60 hari terakhir
"""
import multiprocessing as mp
import numpy as np
import pandas as pd

import backtest as bt
import research as rs

TFS = {"5m": "data/GC_5m_60d.csv", "15m": "data/GC_15m_60d.csv", "1h": "data/GC_1h_60d.csv"}
CFG = bt.Config(capital=10_000, risk_pct=1.0, spread=0.40)
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
    plan = rs.build_plan(I, p)
    if plan is None:
        return None
    out = dict(p)
    for tag, (s, e) in {"now": (m1, len(df)), "prev": (max(m0, 200), m1)}.items():
        t, c = bt.run_backtest(df, plan, CFG, s, e)
        st = bt.summarize("", t, c, CFG.capital)
        out.update({f"{tag}_trades": st["trades"], f"{tag}_win": st["win_rate_%"], f"{tag}_expR": st["expectancy_R"],
                    f"{tag}_PF": st["profit_factor"], f"{tag}_ret": st["net_return_%"], f"{tag}_dd": st["max_dd_%"]})
    return out


def params():
    for p in rs.all_params(["1h"]):
        for tf in TFS:
            if p["trigger"] == "asia_break" and tf == "5m":
                continue
            yield {**p, "tf": tf}


if __name__ == "__main__":
    ps = list(params())
    with mp.Pool(mp.cpu_count(), initializer=_init) as pool:
        R = pd.DataFrame([r for r in pool.imap_unordered(run, ps, chunksize=16) if r])
    R.to_csv("results/month_scan.csv", index=False)
    print(f"{len(R):,} kombinasi diuji. Profit di bulan terakhir: {(R.now_ret > 0).sum():,} "
          f"| profit di DUA bulan: {((R.now_ret > 0) & (R.prev_ret > 0)).sum():,}")
    cols = ["tf", "trigger", "trend", "adx", "session", "side", "sl", "exit",
            "now_trades", "now_win", "now_expR", "now_PF", "now_ret", "now_dd", "prev_trades", "prev_expR", "prev_ret"]
    fmt = {"display.width": 250, "display.max_columns": 30, "display.float_format": "{:,.2f}".format}
    ok = R[R.now_trades >= 15]
    with pd.option_context(*sum(fmt.items(), ())):
        print("\n=== TOP 10 bulan terakhir (min 15 trade) ===")
        print(ok.sort_values("now_ret", ascending=False)[cols].head(10).to_string(index=False))
        both = ok[(ok.prev_trades >= 15) & (ok.prev_ret > 0)]
        both = both.assign(min_ret=both[["now_ret", "prev_ret"]].min(axis=1))
        print("\n=== TOP 10 yang profit di bulan terakhir DAN bulan sebelumnya ===")
        print(both.sort_values("min_ret", ascending=False)[cols].head(10).to_string(index=False))
        print("\n=== Per trigger (median return bulan terakhir, % kombinasi profit) ===")
        g = ok.groupby("trigger").agg(median_ret=("now_ret", "median"), pct_profit=("now_ret", lambda x: 100 * (x > 0).mean()))
        print(g.sort_values("median_ret", ascending=False).to_string())
        g = ok.groupby("side").agg(median_ret=("now_ret", "median"), pct_profit=("now_ret", lambda x: 100 * (x > 0).mean()))
        print(g.to_string())
