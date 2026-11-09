#!/usr/bin/env python3
"""Uji HOLDOUT ke-2 (pra-registrasi 9 Nov 2026, ditulis sebelum data Feb 2026 / Apr 2026 / Sep 2025 dilihat).
Kandidat: `port6` (backtest.py) dipilih dari 6 periode: Nov 2025, Jan, Mar, Jun, Agu-Okt, Okt-Nov 2026.
Parameter beku: SL $4,5, BE close M1 +0,45 -> +0,45, trailing $13,5. Varian informasi: SL $9 (win rate naik mekanis).

Kriteria lolos PRIMER (SL $4,5; spread $0,30, slippage $0,10):
  - tiap periode holdout: >= 20 trade, profit, win >= 65%
  - gabungan 9 periode: expR >= +0,10, PF >= 1,4, >= 55% minggu profit
  - stres biaya (spread $0,40, slippage $0,20): >= 2 dari 3 periode holdout tetap profit
Varian SL $9 hanya dilaporkan (kriteria sama + win >= 78% tiap periode, >= 80% gabungan); lolosnya varian ini TIDAK
mengubah fakta bahwa risikonya 2x aturan 45 pips.
  python holdout2.py
"""
import os

import numpy as np
import pandas as pd

import backtest as bt

RESEARCH = {"Nov 2025": "data/duka_m1_nov25.csv", "Jan 2026": "data/duka_m1_jan26.csv", "Mar 2026": "data/duka_m1_mar26.csv",
            "Jun 2026": "data/duka_m1_jun26.csv", "Agu-Okt 2026": "data/duka_m1_augoct26.csv", "Okt-Nov 2026": "data/duka_m1_octnov26.csv"}
HOLDOUT = {"Sep 2025": "data/duka_m1_sep25.csv", "Feb 2026": "data/duka_m1_feb26.csv", "Apr 2026": "data/duka_m1_apr26.csv"}
VARIANTS = {"PRIMER port6 SL $4,5": dict(sl_usd=4.5, min_win=65, comb_win=0),
            "informasi: port6 SL $9": dict(sl_usd=9.0, min_win=78, comb_win=80)}
CFG = bt.Config(spread=0.30, slippage=0.10)
CFG_STRESS = bt.Config(spread=0.40, slippage=0.20)


def ev(df, cfg, **kw):
    plan = bt.strat_port6(df, **kw)
    t, c = bt.run_backtest(df, plan, cfg, 300, len(df))
    st = bt.summarize("", t, c, 1e4)
    R = pd.Series([x.r_multiple for x in t], index=[x.entry_time for x in t], dtype=float)
    return st, R


if __name__ == "__main__":
    avail = {k: v for k, v in HOLDOUT.items() if os.path.exists(v)}
    print(f"Holdout tersedia: {list(avail)} / {list(HOLDOUT)} | spread ${CFG.spread} slippage ${CFG.slippage}")
    data = {k: bt.load_csv(v) for k, v in {**RESEARCH, **avail}.items()}
    for name, v in VARIANTS.items():
        print(f"\n=== {name} ===")
        allR, ok, stress_ok = [], True, 0
        for grp, files in [("riset", RESEARCH), ("HOLDOUT", avail)]:
            for k in files:
                st, R = ev(data[k], CFG, sl_usd=v["sl_usd"])
                allR.append(R)
                wk = R.groupby(R.index.to_period("W")).sum() if len(R) else pd.Series(dtype=float)
                flag = ""
                if grp == "HOLDOUT":
                    passed = st["trades"] >= 20 and st["net_return_%"] > 0 and st["win_rate_%"] >= v["min_win"]
                    ok &= passed
                    st2, _ = ev(data[k], CFG_STRESS, sl_usd=v["sl_usd"])
                    stress_ok += st2["net_return_%"] > 0
                    flag = f"  | stres ret={st2['net_return_%']:+.1f}%  <- {'LOLOS' if passed else 'GAGAL'}"
                print(f"  {grp:7s} {k:13s} n={st['trades']:3d} win={st['win_rate_%']:5.1f}% expR={st['expectancy_R']:+.2f} PF={st['profit_factor']:4.2f} "
                      f"ret={st['net_return_%']:+6.1f}% DD={st['max_dd_%']:5.1f}% minggu+={(wk > 0).sum()}/{len(wk)}{flag}")
        R = pd.concat(allR)
        wk = R.groupby(R.index.to_period("W")).sum()
        pf = R[R > 0].sum() / -R[R <= 0].sum()
        win = (R > 0).mean() * 100
        comb = R.mean() >= 0.10 and pf >= 1.4 and (wk > 0).sum() >= 0.55 * len(wk) and win >= v["comb_win"]
        full = len(avail) == len(HOLDOUT)
        stress = stress_ok >= 2 if full else False
        print(f"  GABUNGAN n={len(R)} win={win:.1f}% expR={R.mean():+.2f} PF={pf:.2f} minggu+={(wk > 0).sum()}/{len(wk)} -> {'LOLOS' if comb else 'GAGAL'}"
              f" | stres biaya: {stress_ok}/{len(avail)} periode holdout profit -> {'LOLOS' if stress else 'GAGAL'}")
        print(f"  VERDICT: {'LOLOS SEMUA KRITERIA' if (ok and comb and stress and full) else 'BELUM LOLOS'}")
