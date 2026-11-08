#!/usr/bin/env python3
"""Evaluasi ulang kandidat (profit dua bulan) dengan ukuran robustness yang lebih wajar:
   minggu profit dari 9 minggu, profit tanpa 1 trade terbaik per bulan, PF minimum, median R.
  python robust_check.py
"""
import sys
import numpy as np
import pandas as pd

import backtest as bt
import entry_scan as es
import partial_scan as pscan
import research as rs
import sl30_scan as ss

es._init()
ss._init()
rs_I = {tf: rs.precompute(ss._D[tf][0]) for tf in ss.TFS}


def plan_for(src, row):
    tf = row["tf"]
    if src == "entry":
        p = {k: row[k] for k in ["tf", "entry", "bias", "struct", "vol", "session", "side"]}
        p["vol"] = None if pd.isna(p["vol"]) else float(p["vol"])
        p["be"] = None if pd.isna(row["be"]) else float(row["be"])
        p["trail"] = float(row["trail"])
        return es.build_plan(es._D[tf][1], p), es._D[tf][0]
    if src == "partial":
        p = {k: row[k] for k in ["tf", "entry", "bias", "struct", "vol", "session", "side"]}
        p["vol"] = None if pd.isna(p["vol"]) else float(p["vol"])
        plan = es.build_plan(es._D[tf][1], {**p, "be": None, "trail": float(row["trail"])})
        plan["partial_tp"], plan["partial_frac"], plan["be_plus"] = float(row["ptp"]), float(row["pfrac"]), 1.0
        return plan, es._D[tf][0]
    if src == "slfix":
        p = {k: row[k] for k in ["tf", "trigger", "trend", "adx", "session", "side"]}
        p["be"] = None if pd.isna(row["be"]) else float(row["be"])
        p["trail"], p["trail_start"] = float(row["trail"]), float(row["trail_start"])
        return ss.build(rs_I[tf], p), ss._D[tf][0]
    raise ValueError(src)


def evaluate(src, row):
    plan, df = plan_for(src, row)
    end = df.index[-1]
    m1 = int(np.searchsorted(df.index, end - pd.Timedelta(days=30)))
    m0 = max(int(np.searchsorted(df.index, end - pd.Timedelta(days=60))), 200)
    t, c = bt.run_backtest(df, plan, es.CFG, m0, len(df))
    R = pd.Series([x.r_multiple for x in t], index=[x.entry_time for x in t])
    wk = R.groupby(R.index.to_period("W")).sum()
    r_prev, r_now = R[R.index < df.index[m1]], R[R.index >= df.index[m1]]
    no_top1 = lambda r: r.sort_values().iloc[:-1].sum() if len(r) > 1 else np.nan
    pf = lambda r: r[r > 0].sum() / -r[r <= 0].sum() if (r <= 0).any() and r[r <= 0].sum() < 0 else np.inf
    st = bt.summarize("", t, c, es.CFG.capital)
    return {"weeks_profit": int((wk > 0).sum()), "weeks": len(wk), "trades": len(R), "win_%": st["win_rate_%"],
            "median_R": R.median(), "expR": R.mean(), "minPF": min(pf(r_prev), pf(r_now)),
            "prev_no_top1": no_top1(r_prev), "now_no_top1": no_top1(r_now),
            "ret_2bln_%": st["net_return_%"], "maxDD_%": st["max_dd_%"], "streak": st["max_loss_streak"]}


if __name__ == "__main__":
    srcs = {"entry": "results/entry_scan_3.csv", "partial": "results/partial_scan.csv", "slfix": "results/slfix_scan_3.csv"}
    rows = []
    for src, f in srcs.items():
        R = pd.read_csv(f)
        cand = R[(R.now_trades >= 20) & (R.prev_trades >= 20) & (R.now_ret > 0) & (R.prev_ret > 0)]
        # buang duplikat hasil identik (parameter berbeda, trade sama)
        cand = cand.drop_duplicates(subset=[c for c in cand.columns if c.startswith(("now_", "prev_"))])
        print(f"{src}: {len(cand)} kandidat unik", file=sys.stderr)
        for _, row in cand.iterrows():
            desc = " ".join(f"{k}={row[k]}" for k in row.index if not k.startswith(("now_", "prev_")))
            rows.append({"src": src, "desc": desc, **evaluate(src, row)})
    D = pd.DataFrame(rows)
    D.to_csv("results/robust_check.csv", index=False)
    D["ok"] = (D.prev_no_top1 > 0) & (D.now_no_top1 > 0) & (D.weeks_profit >= 6) & (D.minPF >= 1.2)
    with pd.option_context("display.width", 350, "display.max_columns", 30, "display.max_colwidth", 120, "display.float_format", "{:,.2f}".format):
        print(f"\nLolos (profit tanpa 1 trade terbaik di dua bulan, >=6 dari 9 minggu profit, PF>=1.2): {D.ok.sum()} dari {len(D)}")
        print(D[D.ok].sort_values(["weeks_profit", "minPF"], ascending=False).head(20).to_string(index=False))
        print("\n=== TOP 15 berdasarkan minggu profit lalu median R (semua kandidat) ===")
        print(D.sort_values(["weeks_profit", "median_R"], ascending=False).head(15).to_string(index=False))
