#!/usr/bin/env python3
"""Validasi strategi final di beberapa periode data M1 sekaligus (default: 3 periode spot Dukascopy 2026).
  python validate_final.py                      # asia_nr7_engulf, spread 0.3
  python validate_final.py --strategy macd_asia_m1 --spread 0.4
"""
import argparse

import numpy as np
import pandas as pd

import backtest as bt

PERIODS = {"Jan 12-30 (bull)": "data/duka_m1_jan26.csv", "Agu 17-Okt 9 (turun/sideways)": "data/duka_m1_augoct26.csv",
           "Okt 12-Nov 6 (turun)": "data/duka_m1_octnov26.csv"}


def run(strat, df, spread, **kw):
    plan = strat(df, **kw)
    t, c = bt.run_backtest(df, plan, bt.Config(spread=spread), 300, len(df))
    st = bt.summarize("", t, c, 1e4)
    R = pd.Series([x.r_multiple for x in t], index=[x.entry_time for x in t], dtype=float)
    return st, R, t


def line(st, R):
    wk = R.groupby(R.index.to_period("W")).sum() if len(R) else pd.Series(dtype=float)
    return (f"n={st['trades']:3d} win={st['win_rate_%']:5.1f}% expR={st['expectancy_R']:+.2f} PF={st['profit_factor']:4.2f} "
            f"ret={st['net_return_%']:+6.1f}% DD={st['max_dd_%']:5.1f}% streak={st['max_loss_streak']} minggu+={(wk > 0).sum()}/{len(wk)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="asia_nr7_engulf")
    ap.add_argument("--spread", type=float, default=0.3)
    a = ap.parse_args()
    strat = bt.STRATEGIES[a.strategy]
    D = {k: bt.load_csv(v) for k, v in PERIODS.items()}
    print(f"=== {a.strategy} | spread ${a.spread} | risiko 1% ===")
    Rs, Ts = [], []
    for k, df in D.items():
        st, R, t = run(strat, df, a.spread)
        Rs.append(R); Ts += t
        print(f"  {k:32s}", line(st, R))
    R = pd.concat(Rs)
    wk = R.groupby(R.index.to_period("W")).sum()
    pnl = pd.Series([x.pnl for x in Ts])
    streak = longest = 0
    for p in pnl:
        streak = streak + 1 if p <= 0 else 0
        longest = max(longest, streak)
    print(f"  {'GABUNGAN 15 minggu':32s} n={len(R)} win={(R > 0).mean() * 100:.1f}% expR={R.mean():+.2f} "
          f"PF={R[R > 0].sum() / -R[R <= 0].sum():.2f} minggu+={(wk > 0).sum()}/{len(wk)} streak={longest} "
          f"tanpa 3 trade terbaik={R.sort_values().iloc[:-3].sum():+.1f}R")
    side = pd.Series([x.direction for x in Ts], index=R.index)
    for d, nm in [(1, "BUY"), (-1, "SELL")]:
        r = R[side == d]
        print(f"  {nm}: n={len(r)} win={(r > 0).mean() * 100:.1f}% expR={r.mean():+.2f} sumR={r.sum():+.1f}")
    print(f"  anatomi: SL penuh={(R <= -0.9).sum()} | plus kecil (0..0.5R)={((R > 0) & (R < 0.5)).sum()} | >=0.5R={(R >= 0.5).sum()} "
          f"| >=2R={(R >= 2).sum()} | maks {R.max():+.1f}R | median menang {R[R > 0].median():+.2f}R")
    dur = pd.Series([(x.exit_time - x.entry_time).total_seconds() / 60 for x in Ts])
    print(f"  durasi: median {dur.median():.0f} mnt | rata {dur.mean():.0f} mnt | maks {dur.max():.0f} mnt")
    print("  mingguan R:", {str(k)[:10]: round(v, 1) for k, v in wk.items()})
    print("\n  Sensitivitas spread:")
    for sp in [0.2, 0.3, 0.4, 0.5, 0.6, 0.8]:
        Rs = []; rets = []
        for k, df in D.items():
            st, R, _ = run(strat, df, sp); Rs.append(R); rets.append(st["net_return_%"])
        R = pd.concat(Rs)
        print(f"    ${sp}: win={(R > 0).mean() * 100:.1f}% expR={R.mean():+.2f} | ret per periode " + " / ".join(f"{r:+.1f}%" for r in rets))
    if a.strategy == "asia_nr7_engulf":
        print("\n  Ketahanan parameter (win gabungan / ret min periode):")
        for kw in [dict(sl_usd=4.0), dict(sl_usd=5.0), dict(be_trigger=0.5, be_plus=0.3), dict(be_trigger=1.0, be_plus=0.6),
                   dict(trail_usd=9.0), dict(trail_usd=13.5), dict(trail_usd=25.0), dict(be_mode="tick")]:
            Rs = []; rets = []
            for k, df in D.items():
                st, R, _ = run(strat, df, a.spread, **kw); Rs.append(R); rets.append(st["net_return_%"])
            R = pd.concat(Rs)
            print(f"    {str(kw):42s} win={(R > 0).mean() * 100:.1f}% expR={R.mean():+.2f} ret min={min(rets):+.1f}% ({' / '.join(f'{r:+.1f}' for r in rets)})")
