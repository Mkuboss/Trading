#!/usr/bin/env python3
"""
Riset ENTRY untuk aturan SL tetap $3 (30 pips), tanpa TP, SL plus + trailing.

Ide: dengan SL sekecil ini, entry harus presisi di titik balik dan SL harus "bersembunyi"
di balik struktur harga (swing low/high terdekat), bukan di tengah noise.

Entry baru (semua dihitung di timeframe entry, M5 atau M15):
  sweep      - liquidity sweep: low menembus low terendah N bar lalu close kembali di atasnya (buy), kebalikan untuk sell
  ema_pb     - pullback ke EMA20 dalam tren EMA20>EMA50 lokal, candle penutupan searah tren
  retest     - setelah breakout high/low 20 bar, harga kembali menyentuh level itu dan tertahan
  engulf     - engulfing candle setelah pullback di bawah/atas EMA20
  nr7        - breakout dari candle dengan range tersempit 7 bar (NR7)
  inside     - breakout dari inside bar
  ignite     - momentum ignition: candle besar (>1.5 ATR) tutup dekat ekstremnya, ikut arahnya
  pin        - pin bar (ekor >= 2x badan) menyentuh EMA20

Filter:
  bias       - none | m15 (EMA50 M15) | h1 (EMA20 vs EMA50 H1) | d1 (EMA50 harian), tanpa look-ahead
  struct     - SL $3 harus berada di balik swing low/high 5 bar terakhir
  vol        - ATR(14) timeframe entry <= batas (noise lebih kecil dari SL)
  session    - all | asia (00-07 UTC) | ldn (07-13) | ny (13-20)

Kriteria lolos: >=20 trade/bulan, profit di DUA bulan, dan TETAP profit tanpa 3 trade terbaik di dua bulan.
  python entry_scan.py
"""
from __future__ import annotations

import itertools
import multiprocessing as mp
import os

import numpy as np
import pandas as pd

import backtest as bt

SL_USD = float(os.environ.get("SL_USD", "3.0"))
BE_PLUS = SL_USD / 3
# (be_trigger, trail) dalam $, proporsional terhadap SL
EXITS = [(None, 3 * SL_USD), (SL_USD, 3 * SL_USD), (SL_USD, 5 * SL_USD), (SL_USD, 8 * SL_USD),
         (2 * SL_USD, 5 * SL_USD), (2 * SL_USD, 8 * SL_USD)]
TFS = {"5m": "data/GC_5m_60d.csv", "15m": "data/GC_15m_60d.csv"}
ENTRIES = ["sweep", "ema_pb", "retest", "engulf", "nr7", "inside", "ignite", "pin", "squeeze"]
BIAS = ["none", "m15", "h1", "d1"]
STRUCT = [False, True]
VOL = [None, 1.0 * SL_USD, 1.5 * SL_USD]
SESSION = ["all", "asia", "ldn", "ny"]
SIDE = ["both", "long", "short"]


def htf_bias(df: pd.DataFrame, rule: str, fast: int, slow: int | None) -> pd.Series:
    """Arah tren timeframe lebih tinggi, hanya memakai bar HTF yang SUDAH selesai."""
    c = df["close"].resample(rule, label="left", closed="left").last().dropna()
    sig = np.sign(bt.ema(c, fast) - bt.ema(c, slow)) if slow else np.sign(c - bt.ema(c, fast))
    return sig.shift(1).reindex(df.index, method="ffill")


def precompute(df: pd.DataFrame) -> dict:
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    I = {"o": o, "h": h, "l": l, "c": c, "atr": bt.atr(df), "ema20": bt.ema(c, 20), "ema50": bt.ema(c, 50),
         "hour": pd.Series(df.index.hour, index=df.index),
         "bias_m15": htf_bias(df, "15min", 50, None), "bias_h1": htf_bias(df, "1h", 20, 50),
         "bias_d1": htf_bias(df, "1D", 50, None)}
    rng = h - l
    body = (c - o).abs()
    I["rng"], I["body"] = rng, body
    I["ll20"], I["hh20"] = l.rolling(20).min().shift(1), h.rolling(20).max().shift(1)
    I["ll5"], I["hh5"] = l.rolling(5).min(), h.rolling(5).max()
    I["nr7"] = (rng <= rng.rolling(7).min()).shift(1).fillna(False).astype(bool)
    I["inside"] = ((h < h.shift(1)) & (l > l.shift(1))).shift(1).fillna(False).astype(bool)
    I["bull"], I["bear"] = c > o, c < o
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    I["bbu"], I["bbl"] = mid + 2 * sd, mid - 2 * sd
    width = 4 * sd / mid
    I["squeeze"] = (width <= width.rolling(120).quantile(0.2)).shift(1).fillna(False).astype(bool)
    return I


def entry(name: str, I: dict):
    o, h, l, c, a, e20, e50 = I["o"], I["h"], I["l"], I["c"], I["atr"], I["ema20"], I["ema50"]
    up, dn = e20 > e50, e20 < e50
    if name == "sweep":
        return (l < I["ll20"]) & (c > I["ll20"]) & I["bull"], (h > I["hh20"]) & (c < I["hh20"]) & I["bear"]
    if name == "ema_pb":
        return up & (l <= e20) & (c > e20) & I["bull"], dn & (h >= e20) & (c < e20) & I["bear"]
    if name == "retest":
        broke_up = (c.shift(1) > I["hh20"].shift(1)).rolling(12).max().astype(bool)
        broke_dn = (c.shift(1) < I["ll20"].shift(1)).rolling(12).max().astype(bool)
        lvl_up, lvl_dn = I["hh20"].rolling(12).min(), I["ll20"].rolling(12).max()
        return (broke_up & (l <= lvl_up + SL_USD / 3) & (c > lvl_up) & I["bull"],
                broke_dn & (h >= lvl_dn - SL_USD / 3) & (c < lvl_dn) & I["bear"])
    if name == "engulf":
        bull_eng = I["bull"] & I["bear"].shift(1).fillna(False) & (c >= o.shift(1)) & (o <= c.shift(1))
        bear_eng = I["bear"] & I["bull"].shift(1).fillna(False) & (c <= o.shift(1)) & (o >= c.shift(1))
        return bull_eng & (l.shift(1) <= e20) & up, bear_eng & (h.shift(1) >= e20) & dn
    if name == "nr7":
        return I["nr7"] & (c > h.shift(1)), I["nr7"] & (c < l.shift(1))
    if name == "inside":
        return I["inside"] & (c > h.shift(1)), I["inside"] & (c < l.shift(1))
    if name == "ignite":
        big = I["body"] > 1.5 * a
        return big & I["bull"] & ((h - c) < 0.2 * I["rng"]), big & I["bear"] & ((c - l) < 0.2 * I["rng"])
    if name == "squeeze":
        return I["squeeze"] & (c > I["bbu"]), I["squeeze"] & (c < I["bbl"])
    if name == "pin":
        lower_wick, upper_wick = np.minimum(o, c) - l, h - np.maximum(o, c)
        return ((lower_wick >= 2 * I["body"]) & (l <= e20) & (c > e20) & up,
                (upper_wick >= 2 * I["body"]) & (h >= e20) & (c < e20) & dn)
    raise ValueError(name)


def build_plan(I: dict, p: dict) -> pd.DataFrame:
    long, short = (x.fillna(False).astype(bool) for x in entry(p["entry"], I))
    c = I["c"]
    if p["bias"] != "none":
        b = I[f"bias_{p['bias']}"]
        long, short = long & (b > 0), short & (b < 0)
    if p["struct"]:
        long, short = long & ((c - I["ll5"]) <= 0.9 * SL_USD), short & ((I["hh5"] - c) <= 0.9 * SL_USD)
    if p["vol"] is not None:
        long, short = long & (I["atr"] <= p["vol"]), short & (I["atr"] <= p["vol"])
    hr = I["hour"]
    ses = {"all": hr >= 0, "asia": hr < 7, "ldn": (hr >= 7) & (hr < 13), "ny": (hr >= 13) & (hr < 20)}[p["session"]]
    long, short = long & ses, short & ses
    if p["side"] == "long":
        short = short & False
    elif p["side"] == "short":
        long = long & False
    no = pd.Series(False, index=c.index)
    plan = bt._plan(pd.DataFrame(index=c.index), long, short, pd.Series(SL_USD, index=c.index), np.nan, no, no)
    be, trail = p["be"], p["trail"]
    plan["be_trigger"], plan["be_plus"], plan["trail"] = (np.nan if be is None else be), BE_PLUS, trail
    return plan


_D: dict = {}


def _init():
    for tf, f in TFS.items():
        df = bt.load_csv(f)
        end = df.index[-1]
        m1 = int(np.searchsorted(df.index, end - pd.Timedelta(days=30)))
        m0 = int(np.searchsorted(df.index, end - pd.Timedelta(days=60)))
        _D[tf] = (df, precompute(df), max(m0, 200), m1)


CFG = bt.Config(capital=10_000, risk_pct=1.0, spread=0.40)


def run(p: dict) -> dict:
    df, I, m0, m1 = _D[p["tf"]]
    plan = build_plan(I, p)
    out = dict(p)
    for tag, (s, e) in {"now": (m1, len(df)), "prev": (m0, m1)}.items():
        t, c = bt.run_backtest(df, plan, CFG, s, e)
        st = bt.summarize("", t, c, CFG.capital)
        r = np.array([x.r_multiple for x in t])
        out.update({f"{tag}_trades": st["trades"], f"{tag}_win": st["win_rate_%"], f"{tag}_PF": st["profit_factor"],
                    f"{tag}_ret": st["net_return_%"], f"{tag}_dd": st["max_dd_%"], f"{tag}_expR": st["expectancy_R"],
                    f"{tag}_R_no_top3": np.sort(r)[:-3].sum() if len(r) > 3 else np.nan})
    return out


def params():
    for tf, en, bi, stc, vol, se, sd, (be, trl) in itertools.product(
            TFS, ENTRIES, BIAS, STRUCT, VOL, SESSION, SIDE, EXITS):
        if tf == "15m" and vol == 1.0 * SL_USD:
            continue
        yield dict(tf=tf, entry=en, bias=bi, struct=stc, vol=vol, session=se, side=sd, be=be, trail=trl)


COLS = ["tf", "entry", "bias", "struct", "vol", "session", "side", "be", "trail",
        "now_trades", "now_win", "now_PF", "now_ret", "now_dd", "now_R_no_top3",
        "prev_trades", "prev_win", "prev_PF", "prev_ret", "prev_dd", "prev_R_no_top3"]

if __name__ == "__main__":
    ps = list(params())
    print(f"Menguji {len(ps):,} kombinasi entry baru (SL ${SL_USD}, tanpa TP, SL plus ${BE_PLUS}) ...", flush=True)
    with mp.Pool(mp.cpu_count(), initializer=_init) as pool:
        R = pd.DataFrame(pool.imap_unordered(run, ps, chunksize=32))
    R.to_csv(f"results/entry_scan_{SL_USD:g}.csv", index=False)
    ok = R[(R.now_trades >= 20) & (R.prev_trades >= 20)]
    both = ok[(ok.now_ret > 0) & (ok.prev_ret > 0)]
    rob = both[(both.now_R_no_top3 > 0) & (both.prev_R_no_top3 > 0)]
    print(f"Cukup trade: {len(ok):,} | profit dua bulan: {len(both):,} | ROBUST (profit tanpa 3 trade terbaik): {len(rob):,}")
    with pd.option_context("display.width", 300, "display.max_columns", 40, "display.float_format", "{:,.2f}".format):
        rob = rob.assign(min_ret=rob[["now_ret", "prev_ret"]].min(axis=1))
        print("\n=== ROBUST, urut return terendah dua bulan ===")
        print(rob.sort_values("min_ret", ascending=False)[COLS].head(20).to_string(index=False))
        print("\n=== Per entry: % kombinasi profit bulan ini / robust ===")
        g = ok.groupby("entry").apply(lambda x: pd.Series({"n": len(x), "pct_profit_now": 100 * (x.now_ret > 0).mean(),
                                                          "pct_robust": 100 * ((x.now_R_no_top3 > 0) & (x.prev_R_no_top3 > 0) & (x.now_ret > 0) & (x.prev_ret > 0)).mean(),
                                                          "median_win": x.now_win.median()}), include_groups=False)
        print(g.sort_values("pct_robust", ascending=False).to_string())
        print("\n=== Pengaruh filter struktur & volatilitas (% robust) ===")
        for col in ["struct", "vol", "bias", "session", "side", "tf"]:
            g = ok.groupby(col, dropna=False).apply(lambda x: 100 * ((x.now_R_no_top3 > 0) & (x.prev_R_no_top3 > 0) & (x.now_ret > 0) & (x.prev_ret > 0)).mean(), include_groups=False)
            print(f"  {col}: " + ", ".join(f"{k}={v:.1f}%" for k, v in g.items()))
