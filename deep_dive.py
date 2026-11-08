#!/usr/bin/env python3
"""Pendalaman satu kandidat hiwin_m1: ketahanan parameter, spread, sesi, arah, anatomi trade.
  python deep_dive.py '{"tf":"5m","fam":"old","entry":"macd","bias":"m15","session":"all","side":"short","be":1.0,"plus":1.0,"trail":4.5}'
"""
import json
import sys

import numpy as np
import pandas as pd

import backtest as bt
import hiwin_m1 as h
import mtf


def ev(p, spread=0.4, seg=None, risk=1.0):
    df1 = h._D["df1"]
    d, Inew, Iold, rule = h._D[p["tf"]]
    plan = h.hs.build({**p, "ts": 0.0}, Inew, Iold)
    if plan is None:
        return None
    plan1 = mtf.to_m1(plan, df1, rule)
    s, e = {None: (300, len(df1)), "h1": (300, h._D["mid"]), "h2": (h._D["mid"], len(df1))}[seg]
    t, c = bt.run_backtest(df1, plan1, bt.Config(spread=spread, risk_pct=risk), s, e)
    st = bt.summarize("", t, c, 1e4)
    R = pd.Series([x.r_multiple for x in t], index=[x.entry_time for x in t])
    wk = R.groupby(R.index.to_period("W")).sum()
    return dict(n=len(t), win=st["win_rate_%"], expR=R.mean() if len(R) else np.nan, PF=st["profit_factor"],
                ret=st["net_return_%"], dd=st["max_dd_%"], wk=f"{(wk > 0).sum()}/{len(wk)}", R=R, t=t)


def f(o):
    if o is None:
        return "(tidak ada)"
    return f"n={o['n']:3d} win={o['win']:5.1f}% expR={o['expR']:+.2f} PF={o['PF']:.2f} ret={o['ret']:+5.1f}% DD={o['dd']:5.1f}% minggu+={o['wk']}"


if __name__ == "__main__":
    P = json.loads(sys.argv[1])
    h._init()
    print(P)
    print("  4 minggu:", f(ev(P)), "\n  paruh 1 :", f(ev(P, seg="h1")), "\n  paruh 2 :", f(ev(P, seg="h2")))
    print("be/plus:")
    for be, plus in [(0.5, 0.3), (0.5, 0.5), (0.75, 0.6), (0.75, 0.75), (1.0, 0.6), (1.0, 1.0), (1.5, 1.0), (1.5, 1.5)]:
        print(f"  be={be} plus={plus}:", f(ev({**P, 'be': be, 'plus': plus})))
    for trl in [3, 4.5, 6, 9, 15]:
        print(f"  trail ${trl}:", f(ev({**P, 'trail': trl})))
    for bi in ["none", "m15", "h1", "d1"]:
        print(f"  bias {bi}:", f(ev({**P, 'bias': bi})))
    for se in ["all", "asia", "ldn", "ny"]:
        print(f"  sesi {se}:", f(ev({**P, 'session': se})))
    for sd in ["short", "both", "long"]:
        print(f"  side {sd}:", f(ev({**P, 'side': sd})))
    for sp in [0.2, 0.4, 0.6, 0.8]:
        print(f"  spread ${sp}:", f(ev(P, spread=sp)))
    o = ev(P)
    R = o["R"]
    print(f"Anatomi: SL penuh={(R <= -0.9).sum()} | plus kecil (0..0.5R)={((R > 0) & (R < 0.5)).sum()} | >=0.5R={(R >= 0.5).sum()} "
          f"| maks {R.max():+.2f}R | median {R.median():+.2f}R | streak kalah {bt.summarize('', o['t'], pd.Series([1e4]), 1e4)['max_loss_streak']}")
    print("mingguan R:", {str(k): round(v, 1) for k, v in R.groupby(R.index.to_period('W')).sum().items()})
