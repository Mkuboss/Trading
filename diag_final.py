#!/usr/bin/env python3
"""Diagnosa trade asia_nr7_engulf: fitur apa yang membedakan trade kena SL, konsisten di semua periode?"""
import numpy as np
import pandas as pd

import backtest as bt
import entry_scan as es
import mtf
import research as rs

P = {"jan": "data/duka_m1_jan26.csv", "augoct": "data/duka_m1_augoct26.csv", "octnov": "data/duka_m1_octnov26.csv"}
rows = []
for per, path in P.items():
    df = bt.load_csv(path)
    plan = bt.strat_asia_nr7_engulf(df)
    t, c = bt.run_backtest(df, plan, bt.Config(spread=0.3), 300, len(df))
    # sumber sinyal
    m15 = mtf.resample(df, "15min"); I15 = es.precompute(m15)
    l15, s15 = es.entry("nr7", I15)
    nr7_bars = set(m15.index[(l15 | s15).fillna(False).to_numpy()])
    # fitur
    m15["atr"] = bt.atr(m15); m15["atr_rel"] = m15["atr"] / m15["atr"].rolling(96).mean()
    h1 = mtf.resample(df, "1h"); h1["adx"] = rs.adx(h1); h1["atr"] = bt.atr(h1)
    d1 = mtf.resample(df, "1D"); d1["rng_prev"] = (d1.high - d1.low).shift(1)
    sess_open = df["open"].resample("1D").first()
    for x in t:
        et = x.entry_time - pd.Timedelta(minutes=1)        # bar sinyal
        b15 = et.floor("15min"); b1h = et.floor("1h"); day = et.floor("1D")
        src = "nr7" if (b15 in nr7_bars and (et.minute % 15 == 14)) else "engulf"
        i15 = m15.index.get_indexer([b15])[0]; i1h = h1.index.get_indexer([b1h])[0]; i1d = d1.index.get_indexer([day])[0]
        move_from_open = abs(x.entry_price - sess_open.get(day, np.nan))
        rows.append(dict(per=per, src=src, dir=x.direction, hour=et.hour, dow=et.dayofweek, R=x.r_multiple, sl=x.reason == "SL" and x.r_multiple < -0.9,
                         atr15=m15["atr"].iloc[i15 - 1] if i15 > 0 else np.nan, atr_rel=m15["atr_rel"].iloc[i15 - 1] if i15 > 0 else np.nan,
                         adx_h1=h1["adx"].iloc[i1h - 1] if i1h > 0 else np.nan, atr_h1=h1["atr"].iloc[i1h - 1] if i1h > 0 else np.nan,
                         rng_prev_day=d1["rng_prev"].iloc[i1d] if i1d >= 0 else np.nan, move_open=move_from_open,
                         mins=(x.exit_time - x.entry_time).total_seconds() / 60))
T = pd.DataFrame(rows)
T.to_csv("results/diag_final_trades.csv", index=False)
pd.set_option("display.width", 250)
def tab(col, bins=None):
    g = T[col] if bins is None else pd.cut(T[col], bins)
    out = T.groupby([g, "per"], observed=True)["R"].agg(n="count", win=lambda r: (r > 0).mean() * 100, expR="mean").round(2)
    print(f"\n--- {col} ---"); print(out.unstack("per").to_string())
print(T.groupby(["per", "src"])["R"].agg(n="count", win=lambda r: (r > 0).mean() * 100, expR="mean", sumR="sum").round(2).to_string())
tab("src"); tab("dir"); tab("hour"); tab("dow")
tab("atr15", [0, 2.5, 3.5, 5, 100]); tab("atr_rel", [0, 0.7, 0.9, 1.1, 1.4, 10]); tab("adx_h1", [0, 15, 20, 25, 30, 100])
tab("atr_h1", [0, 8, 11, 15, 100]); tab("rng_prev_day", [0, 40, 60, 80, 1000]); tab("move_open", [0, 5, 10, 20, 1000])
