#!/usr/bin/env python3
"""Validasi out-of-sample macd_asia_m1 pada data spot Dukascopy M1 (independen dari data riset Yahoo).
Parameter TIDAK diubah. Kriteria lolos ditetapkan sebelum melihat hasil: win >= 75% dan profit di tiap periode.
  python validate_oos.py data/duka_m1_jan26.csv data/duka_m1_augoct26.csv
"""
import sys

import numpy as np
import pandas as pd

import backtest as bt


def ev(df, spread=0.4, start=300, end=None, **kw):
    plan = bt.strat_macd_asia_m1(df, **kw)
    t, c = bt.run_backtest(df, plan, bt.Config(spread=spread, risk_pct=1.0), start, len(df) if end is None else end)
    st = bt.summarize("", t, c, 1e4)
    R = pd.Series([x.r_multiple for x in t], index=[x.entry_time for x in t], dtype=float)
    side = pd.Series([x.direction for x in t], index=R.index) if t else pd.Series(dtype=float)
    return dict(n=len(t), win=st["win_rate_%"], expR=R.mean() if len(R) else np.nan, PF=st["profit_factor"],
                ret=st["net_return_%"], dd=st["max_dd_%"], streak=st["max_loss_streak"], R=R, side=side, t=t)


def f(o):
    if o["n"] == 0:
        return "n=0"
    wk = o["R"].groupby(o["R"].index.to_period("W")).sum()
    return (f"n={o['n']:3d} win={o['win']:5.1f}% expR={o['expR']:+.2f} PF={o['PF']:.2f} ret={o['ret']:+6.1f}% "
            f"DD={o['dd']:5.1f}% streak={o['streak']} minggu+={(wk > 0).sum()}/{len(wk)}")


for path in sys.argv[1:]:
    df = bt.load_csv(path)
    print(f"\n=== {path}: {len(df)} bar M1, {df.index[0]} s/d {df.index[-1]}, harga {df.close.iloc[0]:.0f} -> {df.close.iloc[-1]:.0f}")
    o = ev(df)
    print("  default   :", f(o))
    if o["n"]:
        R = o["R"]
        print("  mingguan R:", {str(k): round(v, 1) for k, v in R.groupby(R.index.to_period("W")).sum().items()})
        for d, nm in [(1, "BUY"), (-1, "SELL")]:
            r = R[o["side"] == d]
            if len(r):
                print(f"  {nm:4s}: n={len(r)} win={(r > 0).mean() * 100:.1f}% expR={r.mean():+.2f} sumR={r.sum():+.1f}")
        print(f"  anatomi: SL penuh={(R <= -0.9).sum()} | 0..0.5R={((R > 0) & (R < 0.5)).sum()} | >=0.5R={(R >= 0.5).sum()} "
              f"| maks {R.max():+.2f}R | median {R.median():+.2f}R")
    for sp in [0.2, 0.3, 0.5, 0.6]:
        print(f"  spread ${sp}:", f(ev(df, spread=sp)))
    for be, plus in [(0.5, 0.5), (0.75, 0.75), (1.0, 1.0)]:
        print(f"  be={be} plus={plus}:", f(ev(df, be_trigger=be, be_plus=plus)))
    for m in [0.3, 1.0]:
        print(f"  macd_min_atr={m}:", f(ev(df, macd_min_atr=m)))
    # bias check: tanpa filter bias harian (asia saja) untuk melihat kontribusi bias
    plan = bt.strat_macd_asia_m1(df)
    print(f"  jumlah sinyal entry (plan): {(plan['entry'] != 0).sum()}")
