#!/usr/bin/env python3
"""Cari kombinasi dengan WIN RATE >= 80% yang TETAP profit, di 1 bulan terakhir + bulan sebelumnya.

Win rate tinggi = TP kecil relatif terhadap SL. Syarat lolos:
  win rate >= 80% DAN expectancy > 0 di kedua bulan, minimal 20 trade per bulan.

  python win_scan.py
"""
import itertools
import multiprocessing as mp

import pandas as pd

import month_scan as ms
import research as rs

SL = [1.5, 2.5, 3.5]
TP_RR = ["rr0.25", "rr0.4", "rr0.6", "rr0.8"]  # TP = rr x SL


def params():
    for tf, trig, tr, ax, se, sd, sl, ex in itertools.product(
            ms.TFS, rs.TRIGGERS, rs.TRENDS, rs.ADX_F, rs.SESSIONS, rs.SIDES, SL, TP_RR):
        if trig == "asia_break" and tf == "5m":
            continue
        if se == "ldn_ny" and trig == "asia_break":
            continue
        yield dict(tf=tf, trigger=trig, trend=tr, adx=ax, session=se, side=sd, sl=sl, exit=ex)


if __name__ == "__main__":
    ps = list(params())
    with mp.Pool(mp.cpu_count(), initializer=ms._init) as pool:
        R = pd.DataFrame([r for r in pool.imap_unordered(ms.run, ps, chunksize=32) if r])
    R.to_csv("results/win_scan.csv", index=False)
    ok = R[(R.now_trades >= 20) & (R.prev_trades >= 20)]
    hi_now = ok[ok.now_win >= 80]
    hi_both = hi_now[hi_now.prev_win >= 80]
    good = hi_both[(hi_both.now_expR > 0) & (hi_both.prev_expR > 0)]
    print(f"{len(R):,} kombinasi | win>=80% bulan ini: {len(hi_now):,} | di dua bulan: {len(hi_both):,} "
          f"| di dua bulan DAN profit: {len(good):,}")
    cols = ["tf", "trigger", "trend", "adx", "session", "side", "sl", "exit",
            "now_trades", "now_win", "now_expR", "now_ret", "now_dd", "prev_trades", "prev_win", "prev_expR", "prev_ret", "prev_dd"]
    good = good.assign(min_ret=good[["now_ret", "prev_ret"]].min(axis=1)).sort_values("min_ret", ascending=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.float_format", "{:,.2f}".format):
        print(good[cols].head(20).to_string(index=False))
        print("\nRata-rata win rate vs expectancy (semua kombinasi win>=80% bulan ini):")
        print(hi_now[["now_win", "now_expR", "prev_win", "prev_expR"]].describe().loc[["mean", "50%"]].to_string())
