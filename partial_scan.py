#!/usr/bin/env python3
"""Exit bertahap untuk aturan SL $3 tetap: tutup sebagian di target dekat, SL sisa ke plus, sisanya trailing jauh.
  python partial_scan.py
"""
import itertools
import multiprocessing as mp

import numpy as np
import pandas as pd

import backtest as bt
import entry_scan as es

PARTIAL_TP = [3.0, 4.5, 6.0]      # $ (1R, 1.5R, 2R)
PARTIAL_FRAC = [0.5, 0.7]
TRAIL = [9.0, 15.0, 24.0]
BIAS = ["none", "m15", "h1", "d1"]
VOL = [None, 4.5]
SESSION = ["all", "ldn", "ny"]


def run(p):
    df, I, m0, m1 = es._D[p["tf"]]
    plan = es.build_plan(I, {**p, "be": None})
    plan["partial_tp"], plan["partial_frac"], plan["be_plus"] = p["ptp"], p["pfrac"], 1.0
    out = dict(p)
    for tag, (s, e) in {"now": (m1, len(df)), "prev": (m0, m1)}.items():
        t, c = bt.run_backtest(df, plan, es.CFG, s, e)
        st = bt.summarize("", t, c, es.CFG.capital)
        r = np.array([x.r_multiple for x in t])
        out.update({f"{tag}_trades": st["trades"], f"{tag}_win": st["win_rate_%"], f"{tag}_PF": st["profit_factor"],
                    f"{tag}_ret": st["net_return_%"], f"{tag}_dd": st["max_dd_%"], f"{tag}_expR": st["expectancy_R"],
                    f"{tag}_R_no_top3": np.sort(r)[:-3].sum() if len(r) > 3 else np.nan})
    return out


def params():
    for tf, en, bi, stc, vol, se, sd, ptp, pf, trl in itertools.product(
            es.TFS, es.ENTRIES, BIAS, es.STRUCT, VOL, SESSION, es.SIDE, PARTIAL_TP, PARTIAL_FRAC, TRAIL):
        yield dict(tf=tf, entry=en, bias=bi, struct=stc, vol=vol, session=se, side=sd, ptp=ptp, pfrac=pf, trail=trl)


COLS = ["tf", "entry", "bias", "struct", "vol", "session", "side", "ptp", "pfrac", "trail",
        "now_trades", "now_win", "now_PF", "now_ret", "now_dd", "now_R_no_top3",
        "prev_trades", "prev_win", "prev_PF", "prev_ret", "prev_dd", "prev_R_no_top3"]

if __name__ == "__main__":
    ps = list(params())
    print(f"Menguji {len(ps):,} kombinasi partial-TP (SL ${es.SL_USD}) ...", flush=True)
    with mp.Pool(mp.cpu_count(), initializer=es._init) as pool:
        R = pd.DataFrame(pool.imap_unordered(run, ps, chunksize=32))
    R.to_csv("results/partial_scan.csv", index=False)
    ok = R[(R.now_trades >= 20) & (R.prev_trades >= 20)]
    both = ok[(ok.now_ret > 0) & (ok.prev_ret > 0)]
    rob = both[(both.now_R_no_top3 > 0) & (both.prev_R_no_top3 > 0)]
    print(f"Cukup trade: {len(ok):,} | profit dua bulan: {len(both):,} | ROBUST: {len(rob):,}")
    with pd.option_context("display.width", 300, "display.max_columns", 40, "display.float_format", "{:,.2f}".format):
        rob = rob.assign(min_ret=rob[["now_ret", "prev_ret"]].min(axis=1))
        print("\n=== ROBUST, urut return terendah dua bulan ===")
        print(rob.sort_values("min_ret", ascending=False)[COLS].head(25).to_string(index=False))
        print("\n=== Jika tidak ada yang robust: TOP profit dua bulan ===")
        both = both.assign(min_ret=both[["now_ret", "prev_ret"]].min(axis=1))
        print(both.sort_values("min_ret", ascending=False)[COLS].head(10).to_string(index=False))
        rb = ((ok.now_R_no_top3 > 0) & (ok.prev_R_no_top3 > 0) & (ok.now_ret > 0) & (ok.prev_ret > 0))
        for col in ["entry", "ptp", "pfrac", "trail", "struct", "bias", "session", "side", "tf"]:
            g = rb.groupby(ok[col].astype(str)).mean() * 100
            print(f"  {col}: " + ", ".join(f"{k}={v:.1f}%" for k, v in g.items()))
