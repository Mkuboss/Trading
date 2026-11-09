#!/usr/bin/env python3
"""Uji HOLDOUT: data yang belum pernah dipakai saat memilih/menyetel strategi. Parameter dibekukan sebelum data dilihat.
Kriteria lolos (ditetapkan 9 Nov 2026 sebelum hasil terlihat):
  - tiap periode holdout: >= 10 trade, profit, win >= 75%  (spread $0,30, slippage $0,10)
  - gabungan 6 periode (3 riset + 3 holdout): win >= 80%, PF >= 1,5, >= 60% minggu profit
  python holdout.py
"""
import os

import numpy as np
import pandas as pd

import backtest as bt

RESEARCH = {"Jan 2026": "data/duka_m1_jan26.csv", "Agu-Okt 2026": "data/duka_m1_augoct26.csv", "Okt-Nov 2026": "data/duka_m1_octnov26.csv"}
HOLDOUT = {"Nov 2025": "data/duka_m1_nov25.csv", "Mar 2026": "data/duka_m1_mar26.csv", "Jun 2026": "data/duka_m1_jun26.csv"}
VARIANTS = {"PRIMER asia_nr7_engulf (bias H1)": {}, "alternatif (NR7 bias D1)": {"nr7_bias": "d1"}}
CFG = bt.Config(spread=0.30, slippage=0.10)


def ev(df, **kw):
    plan = bt.strat_asia_nr7_engulf(df, **kw)
    t, c = bt.run_backtest(df, plan, CFG, 300, len(df))
    st = bt.summarize("", t, c, 1e4)
    R = pd.Series([x.r_multiple for x in t], index=[x.entry_time for x in t], dtype=float)
    return st, R


if __name__ == "__main__":
    avail = {k: v for k, v in HOLDOUT.items() if os.path.exists(v)}
    print(f"Holdout tersedia: {list(avail)} | spread ${CFG.spread} slippage ${CFG.slippage}")
    for name, kw in VARIANTS.items():
        print(f"\n=== {name} ===")
        allR, ok = [], True
        for grp, files in [("riset", RESEARCH), ("HOLDOUT", avail)]:
            for k, path in files.items():
                st, R = ev(bt.load_csv(path), **kw)
                allR.append(R)
                wk = R.groupby(R.index.to_period("W")).sum() if len(R) else pd.Series(dtype=float)
                flag = ""
                if grp == "HOLDOUT":
                    passed = st["trades"] >= 10 and st["net_return_%"] > 0 and st["win_rate_%"] >= 75
                    ok &= passed
                    flag = "  <- LOLOS" if passed else "  <- GAGAL"
                print(f"  {grp:7s} {k:13s} n={st['trades']:3d} win={st['win_rate_%']:5.1f}% expR={st['expectancy_R']:+.2f} PF={st['profit_factor']:4.2f} "
                      f"ret={st['net_return_%']:+6.1f}% DD={st['max_dd_%']:5.1f}% minggu+={(wk > 0).sum()}/{len(wk)}{flag}")
        R = pd.concat(allR)
        wk = R.groupby(R.index.to_period("W")).sum()
        pf = R[R > 0].sum() / -R[R <= 0].sum()
        win = (R > 0).mean() * 100
        comb = win >= 80 and pf >= 1.5 and (wk > 0).sum() >= 0.6 * len(wk)
        print(f"  GABUNGAN n={len(R)} win={win:.1f}% expR={R.mean():+.2f} PF={pf:.2f} minggu+={(wk > 0).sum()}/{len(wk)} -> {'LOLOS' if comb else 'GAGAL'}")
        print(f"  VERDICT: {'LOLOS SEMUA KRITERIA' if (ok and comb and len(avail) == len(HOLDOUT)) else 'BELUM LOLOS'}")
