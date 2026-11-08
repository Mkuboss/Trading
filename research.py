#!/usr/bin/env python3
"""
Riset kombinasi indikator teknikal untuk XAUUSD, dengan disiplin anti-overfitting.

Alur:
  1. Bangun ribuan kombinasi: TRIGGER (sinyal masuk) x FILTER (tren, ADX, sesi, arah) x EXIT (SL, TP, trailing).
  2. Uji semua kombinasi HANYA di data in-sample (IS).
  3. Pilih kandidat terbaik berdasarkan skor yang tahan banting (bukan profit terbesar).
  4. Uji kandidat itu di data out-of-sample (OOS) yang belum pernah "dilihat" saat pemilihan.
  5. Cek kestabilan per tahun dan sensitivitas parameter.

Contoh:
  python research.py --csv data/XAUUSD_H1.csv --is-end 2022-12-31
"""
from __future__ import annotations

import argparse
import itertools
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np
import pandas as pd

import backtest as bt

# ---------------------------------------------------------------------------
# Indikator tambahan
# ---------------------------------------------------------------------------


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    up, dn = h.diff(), -l.diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    a = bt.atr(df, n)
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False).mean() / a
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def supertrend_dir(df: pd.DataFrame, n: int = 10, mult: float = 3.0) -> pd.Series:
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    a = bt.atr(df, n).to_numpy()
    mid = (h + l) / 2
    ub, lb = mid + mult * a, mid - mult * a
    fub, flb = ub.copy(), lb.copy()
    d = np.ones(len(c))
    for i in range(1, len(c)):
        fub[i] = ub[i] if (ub[i] < fub[i - 1] or c[i - 1] > fub[i - 1]) else fub[i - 1]
        flb[i] = lb[i] if (lb[i] > flb[i - 1] or c[i - 1] < flb[i - 1]) else flb[i - 1]
        if c[i] > fub[i - 1]:
            d[i] = 1
        elif c[i] < flb[i - 1]:
            d[i] = -1
        else:
            d[i] = d[i - 1]
    return pd.Series(d, index=df.index)


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if rule == "1h":
        return df
    return df.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def daily_bias(df: pd.DataFrame, n: int = 50) -> pd.Series:
    """+1 jika close harian KEMARIN di atas EMA-n harian, -1 jika di bawah (tanpa look-ahead)."""
    d = df["close"].resample("1D").last().dropna()
    bias = np.sign(d - bt.ema(d, n)).shift(1)
    return pd.Series(df.index.normalize().map(bias), index=df.index).astype(float)


def precompute(df: pd.DataFrame) -> dict:
    c, h, l = df["close"], df["high"], df["low"]
    hour = pd.Series(df.index.hour, index=df.index)
    ind = {
        "c": c, "atr": bt.atr(df), "ema20": bt.ema(c, 20), "ema50": bt.ema(c, 50), "ema200": bt.ema(c, 200),
        "rsi": bt.rsi(c), "adx": adx(df), "st": supertrend_dir(df), "dbias": daily_bias(df), "hour": hour,
    }
    for n in (20, 55):
        ind[f"hh{n}"] = h.rolling(n).max().shift(1)
        ind[f"ll{n}"] = l.rolling(n).min().shift(1)
    for n in (10, 20):
        ind[f"xh{n}"] = h.rolling(n).max().shift(1)
        ind[f"xl{n}"] = l.rolling(n).min().shift(1)
    macd = bt.ema(c, 12) - bt.ema(c, 26)
    ind["macd"], ind["macds"] = macd, bt.ema(macd, 9)
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    ind["bbm"], ind["bbu"], ind["bbl"] = mid, mid + 2 * sd, mid - 2 * sd
    width = (4 * sd / mid)
    ind["squeeze"] = (width <= width.rolling(120).quantile(0.2)).shift(1).fillna(False).astype(bool)
    if (df.index.to_series().diff().median() <= pd.Timedelta(hours=1)):
        day = pd.Series(df.index.normalize(), index=df.index)
        asia = hour < 7
        ind["asia_hi"] = h.where(asia).groupby(day).transform("max")
        ind["asia_lo"] = l.where(asia).groupby(day).transform("min")
        ind["day"] = day
    return ind


# ---------------------------------------------------------------------------
# Komponen
# ---------------------------------------------------------------------------
def trigger(name: str, I: dict):
    c = I["c"]
    if name == "donch20":
        return c > I["hh20"], c < I["ll20"]
    if name == "donch55":
        return c > I["hh55"], c < I["ll55"]
    if name == "ema_pb":
        up, dn = I["ema50"] > I["ema200"], I["ema50"] < I["ema200"]
        r = I["rsi"]
        return up & (r.shift(1) < 40) & (r >= 40), dn & (r.shift(1) > 60) & (r <= 60)
    if name == "ema_cross":
        f, s = I["ema20"], I["ema50"]
        return (f > s) & (f.shift(1) <= s.shift(1)), (f < s) & (f.shift(1) >= s.shift(1))
    if name == "macd":
        m, s = I["macd"], I["macds"]
        return (m > s) & (m.shift(1) <= s.shift(1)) & (m < 0), (m < s) & (m.shift(1) >= s.shift(1)) & (m > 0)
    if name == "supertrend":
        st = I["st"]
        return (st == 1) & (st.shift(1) == -1), (st == -1) & (st.shift(1) == 1)
    if name == "bb_squeeze":
        return I["squeeze"] & (c > I["bbu"]), I["squeeze"] & (c < I["bbl"])
    if name == "rsi_mr":
        return (c < I["bbl"]) & (I["rsi"] < 30), (c > I["bbu"]) & (I["rsi"] > 70)
    if name == "asia_break":
        if "asia_hi" not in I:
            return None
        win = (I["hour"] >= 7) & (I["hour"] < 16)
        sig = (win & (c > I["asia_hi"])).astype(int) - (win & (c < I["asia_lo"])).astype(int)
        first = (sig != 0) & ((sig != 0).astype(int).groupby(I["day"]).cumsum() == 1)
        sig = sig.where(first, 0)
        return sig > 0, sig < 0
    raise ValueError(name)


TRIGGERS = ["donch20", "donch55", "ema_pb", "ema_cross", "macd", "supertrend", "bb_squeeze", "rsi_mr", "asia_break"]
TRENDS = ["none", "ema200", "daily50"]
ADX_F = ["none", "adx20", "adx_lt20"]
SESSIONS = ["all", "ldn_ny"]
SIDES = ["both", "long", "short"]
SL_ATR = [1.5, 2.5]
EXITS = ["rr1.5", "rr2", "rr3", "trail3", "signal"]


def build_plan(I: dict, p: dict) -> pd.DataFrame | None:
    t = trigger(p["trigger"], I)
    if t is None:
        return None
    long, short = (x.fillna(False).astype(bool) for x in t)
    c = I["c"]
    if p["trend"] == "ema200":
        long, short = long & (c > I["ema200"]), short & (c < I["ema200"])
    elif p["trend"] == "daily50":
        long, short = long & (I["dbias"] > 0), short & (I["dbias"] < 0)
    if p["adx"] == "adx20":
        long, short = long & (I["adx"] > 20), short & (I["adx"] > 20)
    elif p["adx"] == "adx_lt20":
        long, short = long & (I["adx"] < 20), short & (I["adx"] < 20)
    if p["session"] == "ldn_ny":
        s = (I["hour"] >= 7) & (I["hour"] < 20)
        long, short = long & s, short & s
    if p["side"] == "long":
        short = short & False
    elif p["side"] == "short":
        long = long & False

    a = I["atr"]
    sl = p["sl"] * a
    tp = pd.Series(np.nan, index=c.index)
    trail = pd.Series(np.nan, index=c.index)
    no = pd.Series(False, index=c.index)
    ex_l, ex_s = no, no
    e = p["exit"]
    if e.startswith("rr"):
        tp = float(e[2:]) * sl
    elif e.startswith("trail"):
        trail = float(e[5:]) * a
    elif e == "signal":  # keluar dengan sinyal kebalikan dari trigger/indikator dasarnya
        if p["trigger"] in ("rsi_mr",):
            ex_l, ex_s = c >= I["bbm"], c <= I["bbm"]
        elif p["trigger"] == "asia_break":
            ex_l = ex_s = I["hour"] >= 20
        elif p["trigger"].startswith("donch"):
            ex_l, ex_s = c < I["xl20"], c > I["xh20"]
        elif p["trigger"] == "supertrend":
            ex_l, ex_s = I["st"] == -1, I["st"] == 1
        else:
            ex_l, ex_s = I["ema20"] < I["ema50"], I["ema20"] > I["ema50"]
    plan = bt._plan(pd.DataFrame(index=c.index), long, short, sl, tp, ex_l, ex_s)
    plan["trail"] = trail
    return plan


def all_params(tfs):
    for tf, trig, tr, ax, se, sd, sl, ex in itertools.product(
            tfs, TRIGGERS, TRENDS, ADX_F, SESSIONS, SIDES, SL_ATR, EXITS):
        if trig == "asia_break" and tf != "1h":
            continue
        if se == "ldn_ny" and (tf == "1d" or trig == "asia_break"):
            continue
        if trig == "rsi_mr" and ax == "adx20":
            continue  # mean reversion di tren kuat: tidak logis
        if trig != "rsi_mr" and ax == "adx_lt20":
            continue  # strategi tren di pasar tanpa tren: tidak logis
        yield dict(tf=tf, trigger=trig, trend=tr, adx=ax, session=se, side=sd, sl=sl, exit=ex)


# ---------------------------------------------------------------------------
# Evaluasi
# ---------------------------------------------------------------------------
_G: dict = {}


def _init(data: dict, cfg: bt.Config):
    _G["data"], _G["cfg"] = data, cfg
    _G["ind"] = {tf: precompute(df) for tf, (df, _) in data.items()}


def stats_from(trades, curve, capital) -> dict:
    s = bt.summarize("", trades, curve, capital)
    r = np.array([t.r_multiple for t in trades])
    s["t_stat"] = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 2 and r.std() > 0 else 0.0
    s.pop("strategy")
    return s


def evaluate(p: dict, segment: str = "is") -> dict | None:
    df, split = _G["data"][p["tf"]]
    plan = build_plan(_G["ind"][p["tf"]], p)
    if plan is None:
        return None
    start, end = (0, split) if segment == "is" else (split, len(df))
    trades, curve = bt.run_backtest(df, plan, _G["cfg"], start, end)
    return {**p, **stats_from(trades, curve, _G["cfg"].capital)}


def _eval_is(p):
    return evaluate(p, "is")


def yearly(df, plan, cfg) -> pd.DataFrame:
    trades, _ = bt.run_backtest(df, plan, cfg)
    t = pd.DataFrame({"year": [x.entry_time.year for x in trades], "R": [x.r_multiple for x in trades]})
    return t.groupby("year")["R"].agg(trades="count", sum_R="sum", exp_R="mean")


def score(row) -> float:
    """Skor seleksi: t-stat dari R (konsisten + jumlah trade cukup), dihukum jika drawdown dalam."""
    if row["trades"] < MIN_TRADES or row["profit_factor"] < 1.1:
        return -np.inf
    return row["t_stat"] * (1 + row["max_dd_%"] / 100)


MIN_TRADES = 120


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/XAUUSD_H1.csv")
    ap.add_argument("--is-end", default="2022-12-31", help="akhir periode in-sample")
    ap.add_argument("--tfs", default="1h,4h,1d")
    ap.add_argument("--spread", type=float, default=0.40)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--min-trades", type=int, default=120, help="minimal trade di IS agar lolos seleksi")
    ap.add_argument("--out", default="results/research")
    a = ap.parse_args()
    global MIN_TRADES
    MIN_TRADES = a.min_trades

    raw = bt.load_csv(a.csv)
    cfg = bt.Config(capital=10_000, risk_pct=1.0, spread=a.spread)
    tfs = a.tfs.split(",")
    data = {}
    for tf in tfs:
        df = resample(raw, tf)
        split = int(np.searchsorted(df.index, pd.Timestamp(a.is_end) + pd.Timedelta(days=1)))
        data[tf] = (df, split)
        print(f"{tf}: {len(df):,} bar | IS {df.index[0]:%Y-%m-%d}..{df.index[split - 1]:%Y-%m-%d} "
              f"| OOS {df.index[split]:%Y-%m-%d}..{df.index[-1]:%Y-%m-%d}")

    params = list(all_params(tfs))
    print(f"\nMenguji {len(params):,} kombinasi di in-sample ...")
    t0 = time.time()
    with mp.Pool(mp.cpu_count(), initializer=_init, initargs=(data, cfg)) as pool:
        res = [r for r in pool.imap_unordered(_eval_is, params, chunksize=8) if r]
    print(f"selesai dalam {time.time() - t0:.0f} detik")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    R = pd.DataFrame(res)
    R["score"] = R.apply(score, axis=1)
    R.sort_values("score", ascending=False).to_csv(out / "is_all.csv", index=False)
    print(f"Kombinasi profit di IS (PF>1): {(R.profit_factor > 1).sum():,} dari {len(R):,} "
          f"| lolos syarat seleksi: {np.isfinite(R.score).sum():,}")

    # Kandidat: top-N berdasarkan skor IS, maksimal 2 per (tf, trigger) agar beragam
    R = R[np.isfinite(R.score)].sort_values("score", ascending=False)
    picks = R.groupby(["tf", "trigger"]).head(2).head(a.top)

    _init(data, cfg)
    rows = []
    keys = ["tf", "trigger", "trend", "adx", "session", "side", "sl", "exit"]
    for _, r in picks.iterrows():
        p = {k: r[k] for k in keys}
        o = evaluate(p, "oos")
        rows.append({**p,
                     "IS_trades": r.trades, "IS_exp_R": r.expectancy_R, "IS_PF": r.profit_factor, "IS_DD": r["max_dd_%"],
                     "OOS_trades": o["trades"], "OOS_exp_R": o["expectancy_R"], "OOS_PF": o["profit_factor"],
                     "OOS_DD": o["max_dd_%"], "OOS_ret_%": o["net_return_%"], "OOS_win_%": o["win_rate_%"]})
    C = pd.DataFrame(rows)
    C.to_csv(out / "candidates_oos.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.float_format", "{:,.2f}".format):
        print("\n=== KANDIDAT TERBAIK (dipilih di IS, lalu diuji di OOS) ===")
        print(C.to_string(index=False))


if __name__ == "__main__":
    main()
