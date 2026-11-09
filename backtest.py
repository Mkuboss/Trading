#!/usr/bin/env python3
"""
Backtest beberapa metode trading XAUUSD dan bandingkan hasilnya.

Strategi yang diuji:
  ema_trend     - Trend following: EMA50/EMA200 + entry saat pullback (RSI)
  donchian      - Breakout channel 20 bar, trailing exit channel 10 bar
  session_break - Breakout range sesi Asia saat London/NY (butuh data intraday)
  mean_revert   - Bollinger Band + RSI, exit di garis tengah
  macd_asia_m1    - FINAL win rate tinggi (SL $3 tetap, tanpa TP, SL plus + trailing), data M1, sesi Asia
  asia_nr7_runner - Aturan SL $3 tetap + trailing: NR7 breakout M15 sesi Asia, bias H1 (riset entry)
  sweep_sell_runner - Aturan SL $3 tetap + trailing: liquidity sweep sell M15, bias H1 turun
  squeeze_runner  - Aturan SL $3 tetap + tanpa TP + SL plus/trailing: BB squeeze breakout M15
  sell_rally_scalp - Win rate tinggi (~90%): MACD sell-the-rally M5, ADX>20, sesi London-NY
  trend_breakout- STRATEGI FINAL hasil riset: Donchian 20 + filter EMA50 harian + trailing 3 ATR (long)

Sumber data:
  --source yf    Yahoo Finance (default ticker GC=F, gold futures)
  --source csv   File CSV, termasuk export dari MetaTrader 5
  --source demo  Data sintetis, HANYA untuk mengetes script (hasilnya tidak bermakna)

Contoh:
  python backtest.py --source yf --interval 1h --period 730d
  python backtest.py --source csv --csv XAUUSD_H1.csv --tz-offset 2
  python backtest.py --source demo
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

OZ_PER_LOT = 100  # 1 lot XAUUSD = 100 troy ounce


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df[["open", "high", "low", "close"]].astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.dropna()


def load_csv(path: str, tz_offset: float = 0.0) -> pd.DataFrame:
    """Baca CSV OHLC. Mendukung format MT5 (<DATE> <TIME> <OPEN> ...) dan format umum.

    tz_offset: selisih jam zona waktu data terhadap UTC (mis. server broker GMT+2 -> 2).
    Semua waktu dikonversi ke UTC, karena jam sesi di strategi memakai UTC.
    """
    df = pd.read_csv(path, sep=None, engine="python")
    df.columns = [str(c).strip().strip("<>").strip().lower() for c in df.columns]

    if "date" in df.columns and "time" in df.columns:
        stamp = df["date"].astype(str).str.replace(".", "-", regex=False) + " " + df["time"].astype(str)
    else:
        for cand in ("datetime", "date", "time", "timestamp", "gmt time", "local time"):
            if cand in df.columns:
                stamp = df[cand].astype(str).str.replace(".", "-", regex=False)
                break
        else:
            raise ValueError(f"Kolom waktu tidak ditemukan. Kolom yang ada: {list(df.columns)}")

    idx = pd.to_datetime(stamp, utc=False)
    if getattr(idx.dt, "tz", None) is not None:
        idx = idx.dt.tz_convert("UTC").dt.tz_localize(None)
    else:
        idx = idx - pd.Timedelta(hours=tz_offset)
    df.index = pd.DatetimeIndex(idx)
    return _finalize(df)


def load_yf(ticker: str, interval: str, period: str) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("yfinance belum terpasang. Jalankan: pip install yfinance")
    df = yf.download(ticker, interval=interval, period=period, progress=False, auto_adjust=False)
    if df.empty:
        sys.exit(f"Gagal mengambil data {ticker} dari Yahoo Finance (cek koneksi/ticker/period).")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    if df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    return _finalize(df)


def make_demo(n_days: int = 900, seed: int = 7) -> pd.DataFrame:
    """Data H1 sintetis: rezim tren/sideways bergantian, volatilitas lebih tinggi di sesi London/NY."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-02", periods=n_days * 24, freq="h")
    idx = idx[idx.dayofweek < 5]
    n = len(idx)
    hours = idx.hour.to_numpy()
    vol = np.where((hours >= 7) & (hours < 17), 0.0024, 0.0011)
    drift = np.zeros(n)
    i = 0
    while i < n:
        length = rng.integers(200, 900)
        drift[i:i + length] = rng.choice([-0.00012, 0.0, 0.0, 0.00012])
        i += length
    rets = drift + vol * rng.standard_t(5, n) / math.sqrt(5 / 3)
    close = 1900 * np.exp(np.cumsum(rets))
    open_ = np.r_[close[0], close[:-1]]
    wick = np.abs(rng.normal(0, vol * 0.6, n)) * close
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - np.abs(rng.normal(0, vol * 0.6, n)) * close
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=idx)


# ---------------------------------------------------------------------------
# Indikator
# ---------------------------------------------------------------------------
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


# ---------------------------------------------------------------------------
# Strategi
# Setiap strategi mengembalikan "plan" (DataFrame sejajar dengan data):
#   entry      : +1 buy / -1 sell / 0 (sinyal di close bar ini, dieksekusi di open bar berikutnya)
#   sl         : jarak stop loss (dalam $)
#   tp         : jarak take profit (dalam $), NaN = tanpa TP tetap
#   exit_long  : True -> tutup posisi buy di open bar berikutnya
#   exit_short : True -> tutup posisi sell di open bar berikutnya
#   trail      : (opsional) jarak trailing stop dalam $, NaN = tanpa trailing
#   trail_start: (opsional) trailing baru aktif setelah profit >= nilai ini ($)
#   be_trigger : (opsional) setelah profit >= nilai ini ($), SL dipindah ke entry + be_plus
#   be_plus    : (opsional) jarak SL di atas entry setelah breakeven ($)
#   partial_tp : (opsional) jarak target partial ($); saat tersentuh, partial_frac posisi ditutup, SL ke entry+be_plus
#   partial_frac: (opsional) porsi yang ditutup di partial (default 0.5)
#   lock_frac  : (opsional) setelah be_trigger tercapai, SL dikunci di entry + lock_frac x profit maksimum (close), $
# ---------------------------------------------------------------------------
def _plan(df, long, short, sl, tp, exit_long, exit_short) -> pd.DataFrame:
    entry = long.fillna(False).astype(int) - short.fillna(False).astype(int)
    return pd.DataFrame({
        "entry": entry,
        "sl": sl,
        "tp": tp if isinstance(tp, pd.Series) else pd.Series(tp, index=df.index, dtype=float),
        "exit_long": exit_long.fillna(False).astype(bool),
        "exit_short": exit_short.fillna(False).astype(bool),
    }, index=df.index)


def strat_ema_trend(df, fast=50, slow=200, rsi_n=14, rsi_buy=40, rsi_sell=60, sl_atr=1.5, tp_atr=3.0):
    """Ikuti tren: buy pullback saat EMA fast > EMA slow, RSI naik kembali melewati 40 (sebaliknya untuk sell)."""
    c = df["close"]
    ef, es, r, a = ema(c, fast), ema(c, slow), rsi(c, rsi_n), atr(df)
    up = (ef > es) & (c > es)
    dn = (ef < es) & (c < es)
    long = up & (r.shift(1) < rsi_buy) & (r >= rsi_buy)
    short = dn & (r.shift(1) > rsi_sell) & (r <= rsi_sell)
    return _plan(df, long, short, sl_atr * a, tp_atr * a, c < es, c > es)


def strat_donchian(df, entry_n=20, exit_n=10, sl_atr=2.0):
    """Breakout ala Turtle: buy tembus high 20 bar, keluar saat tembus low 10 bar (trailing)."""
    c, h, l = df["close"], df["high"], df["low"]
    a = atr(df)
    long = c > h.rolling(entry_n).max().shift(1)
    short = c < l.rolling(entry_n).min().shift(1)
    exit_long = c < l.rolling(exit_n).min().shift(1)
    exit_short = c > h.rolling(exit_n).max().shift(1)
    return _plan(df, long, short, sl_atr * a, np.nan, exit_long, exit_short)


def strat_session_breakout(df, asia_end=7, trade_end=16, close_hour=20, rr=2.0):
    """Range sesi Asia (00:00-asia_end UTC). Entry di breakout pertama sampai trade_end UTC.
    SL di sisi lain range (dibatasi 0.5-2 ATR), TP = rr x SL, semua posisi ditutup jam close_hour UTC."""
    c, h, l = df["close"], df["high"], df["low"]
    a = atr(df)
    hour = pd.Series(df.index.hour, index=df.index)
    day = pd.Series(df.index.normalize(), index=df.index)
    asia = hour < asia_end
    asia_hi = h.where(asia).groupby(day).transform("max")
    asia_lo = l.where(asia).groupby(day).transform("min")
    window = (hour >= asia_end) & (hour < trade_end)
    sig = (window & (c > asia_hi)).astype(int) - (window & (c < asia_lo)).astype(int)
    first = (sig != 0) & ((sig != 0).astype(int).groupby(day).cumsum() == 1)
    sig = sig.where(first, 0)
    sl = (asia_hi - asia_lo).clip(lower=0.5 * a, upper=2.0 * a)
    eod = hour >= close_hour
    return _plan(df, sig > 0, sig < 0, sl, rr * sl, eod, eod)


def strat_mean_revert(df, bb_n=20, bb_k=2.0, rsi_n=14, rsi_lo=30, rsi_hi=70, sl_atr=1.5):
    """Buy saat close di bawah lower band & RSI < 30, sell kebalikannya. Exit saat kembali ke middle band."""
    c = df["close"]
    mid = c.rolling(bb_n).mean()
    sd = c.rolling(bb_n).std()
    r, a = rsi(c, rsi_n), atr(df)
    long = (c < mid - bb_k * sd) & (r < rsi_lo)
    short = (c > mid + bb_k * sd) & (r > rsi_hi)
    return _plan(df, long, short, sl_atr * a, np.nan, c >= mid, c <= mid)


def strat_trend_breakout(df, entry_n=20, bias_ema=50, sl_atr=1.5, trail_atr=3.0):
    """STRATEGI FINAL hasil riset (lihat RESEARCH.md).
    Buy saat close menembus high 20 bar, HANYA jika close harian kemarin > EMA50 harian.
    SL awal 1.5 ATR, lalu trailing stop 3 ATR dari close. Tanpa TP tetap: biarkan profit berjalan.
    Tidak ada sisi short: di riset 26 tahun, short pada emas konsisten rugi."""
    c, h = df["close"], df["high"]
    a = atr(df)
    d = c.resample("1D").last().dropna()
    bias = np.sign(d - ema(d, bias_ema)).shift(1)
    up_day = pd.Series(df.index.normalize().map(bias), index=df.index) > 0
    long = (c > h.rolling(entry_n).max().shift(1)) & up_day
    no = pd.Series(False, index=df.index)
    plan = _plan(df, long, no, sl_atr * a, np.nan, no, no)
    plan["trail"] = trail_atr * a
    return plan


def strat_sell_rally_scalp(df, adx_min=20, sl_atr=3.5, tp_rr=0.25, start_hour=7, end_hour=20):
    """STRATEGI WIN RATE TINGGI (riset 1 bulan, lihat RESEARCH.md). Untuk M5, kondisi tren turun.
    SELL saat MACD(12,26,9) memotong signal ke bawah DI ATAS level 0 (harga sedang memantul naik),
    hanya jika ADX(14) > 20 dan jam 07-20 UTC (London-NY).
    SL 3.5 ATR, TP = 0.25 x SL. Win rate ~89-92%, tapi 1 kalah = hapus ~4 menang."""
    from research import adx  # impor lokal: research.py juga mengimpor modul ini
    c = df["close"]
    a = atr(df)
    m = ema(c, 12) - ema(c, 26)
    sig = ema(m, 9)
    hour = pd.Series(df.index.hour, index=df.index)
    short = (m < sig) & (m.shift(1) >= sig.shift(1)) & (m > 0) & (adx(df) > adx_min) \
        & (hour >= start_hour) & (hour < end_hour)
    no = pd.Series(False, index=df.index)
    return _plan(df, no, short, sl_atr * a, tp_rr * sl_atr * a, no, no)


def strat_squeeze_runner(df, bb_n=20, bb_k=2.0, sq_lookback=120, sq_pct=0.2,
                         sl_usd=3.0, be_trigger=3.0, be_plus=1.0, trail_usd=15.0):
    """ATURAN: SL tetap 30 pips ($3), TANPA TP, SL bergerak. Hasil riset 2 bulan di M15 (lihat RESEARCH.md).
    Entry : Bollinger Band (20, 2) sedang menyempit (lebar band di 20% terendah dari 120 bar terakhir),
            lalu close menembus band atas (BUY) atau band bawah (SELL).
    SL    : $3 tetap. Setelah profit $3, SL dipindah ke entry + $1 (SL plus). Trailing $15 dari close.
    Catatan: win rate ~25%; profit bergantung pada beberapa trade besar per bulan."""
    c = df["close"]
    mid, sd = c.rolling(bb_n).mean(), c.rolling(bb_n).std()
    upper, lower = mid + bb_k * sd, mid - bb_k * sd
    width = 2 * bb_k * sd / mid
    squeeze = (width <= width.rolling(sq_lookback).quantile(sq_pct)).shift(1).fillna(False).astype(bool)
    long, short = squeeze & (c > upper), squeeze & (c < lower)
    no = pd.Series(False, index=df.index)
    plan = _plan(df, long, short, pd.Series(sl_usd, index=df.index), np.nan, no, no)
    plan["be_trigger"], plan["be_plus"], plan["trail"] = be_trigger, be_plus, trail_usd
    return plan


def _h1_bias(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.Series:
    """Arah tren H1 (EMA20 vs EMA50) dari bar H1 yang sudah selesai, tanpa look-ahead."""
    c = df["close"].resample("1h", label="left", closed="left").last().dropna()
    return np.sign(ema(c, fast) - ema(c, slow)).shift(1).reindex(df.index, method="ffill")


def strat_asia_nr7_runner(df, sl_usd=3.0, trail_usd=9.0, asia_end=7):
    """ATURAN SL $3 TETAP + TANPA TP + TRAILING. Untuk M15. Hasil riset entry (lihat RESEARCH.md).
    Entry : candle sebelumnya adalah NR7 (range tersempit dari 7 candle), lalu close menembus high-nya
            (BUY) atau low-nya (SELL), hanya di sesi Asia (00-07 UTC) dan searah tren H1 (EMA20 vs EMA50).
    Exit  : SL $3 tetap, trailing $9 dari close. Tidak ada TP.
    Kunci : sesi Asia tenang (ATR M15 lebih kecil), jadi SL $3 tidak tersapu noise."""
    c, h, l = df["close"], df["high"], df["low"]
    rng = h - l
    nr7 = (rng <= rng.rolling(7).min()).shift(1).fillna(False).astype(bool)
    bias = _h1_bias(df)
    asia = pd.Series(df.index.hour < asia_end, index=df.index)
    long = nr7 & (c > h.shift(1)) & (bias > 0) & asia
    short = nr7 & (c < l.shift(1)) & (bias < 0) & asia
    no = pd.Series(False, index=df.index)
    plan = _plan(df, long, short, pd.Series(sl_usd, index=df.index), np.nan, no, no)
    plan["trail"] = trail_usd
    return plan


def strat_sweep_sell_runner(df, n=20, sl_usd=3.0, trail_usd=9.0):
    """ATURAN SL $3 TETAP + TANPA TP + TRAILING. Untuk M15. Pasangan strat_asia_nr7_runner (korelasi negatif).
    Entry : liquidity sweep: high menembus high tertinggi 20 candle sebelumnya, tapi close kembali di bawahnya
            dengan candle bearish -> SELL. Hanya saat tren H1 turun (EMA20 < EMA50). Sisi buy tidak dipakai:
            di riset, sweep buy rugi konsisten.
    Exit  : SL $3 tetap, trailing $9 dari close. Tidak ada TP."""
    o, c, h = df["open"], df["close"], df["high"]
    hh = h.rolling(n).max().shift(1)
    short = (h > hh) & (c < hh) & (c < o) & (_h1_bias(df) < 0)
    no = pd.Series(False, index=df.index)
    plan = _plan(df, no, short, pd.Series(sl_usd, index=df.index), np.nan, no, no)
    plan["trail"] = trail_usd
    return plan


def _daily_bias(df: pd.DataFrame, n: int = 50) -> pd.Series:
    """+1/-1: close harian KEMARIN di atas/bawah EMA-n harian (tanpa look-ahead)."""
    d = df["close"].resample("1D").last().dropna()
    return np.sign(d - ema(d, n)).shift(1).reindex(df.index, method="ffill")


def strat_macd_asia_m1(df, macd_min_atr=0.5, asia_end=7, sl_usd=3.0, be_trigger=0.5, be_plus=1.0, trail_usd=4.5):
    """STRATEGI FINAL WIN RATE TINGGI untuk aturan SL $3 tetap, tanpa TP, SL bergerak. Jalankan di data M1.
    Entry : MACD(12,26,9) di M1 memotong signal. SELL jika cross ke bawah terjadi DI ATAS nol,
            BUY jika cross ke atas terjadi DI BAWAH nol (sell saat pantulan naik, buy saat pantulan turun).
    Filter: |MACD| saat cross >= 0.5 x ATR(14) M1 (pantulan yang kuat), sesi Asia 00-07 UTC,
            searah bias harian (close kemarin vs EMA50 harian).
    Exit  : SL $3 tetap. Setelah profit +$0.5, SL ke entry +$1 (dibatasi harga saat itu). Trailing $4.5. Tanpa TP.
    Riset: 12 Okt - 6 Nov 2026, win ~86%, lihat RESEARCH.md."""
    c = df["close"]
    a = atr(df)
    m = ema(c, 12) - ema(c, 26)
    sig = ema(m, 9)
    strong = m.abs() >= macd_min_atr * a
    bias = _daily_bias(df)
    asia = pd.Series(df.index.hour < asia_end, index=df.index)
    cross_dn = (m < sig) & (m.shift(1) >= sig.shift(1)) & (m > 0)
    cross_up = (m > sig) & (m.shift(1) <= sig.shift(1)) & (m < 0)
    long = cross_up & strong & asia & (bias > 0)
    short = cross_dn & strong & asia & (bias < 0)
    no = pd.Series(False, index=df.index)
    plan = _plan(df, long, short, pd.Series(sl_usd, index=df.index), np.nan, no, no)
    plan["be_trigger"], plan["be_plus"], plan["trail"] = be_trigger, be_plus, trail_usd
    return plan



def strat_asia_nr7_engulf(df, sl_usd=4.5, be_trigger=0.75, be_plus=0.6, trail_usd=18.0, asia_end=7, be_mode="m1close", nr7_bias="h1"):
    """Portofolio sesi Asia (00-07 UTC), WAJIB data M1. Dua entry digabung, satu posisi dalam satu waktu:
      1) NR7 breakout M15: bar sebelumnya range tersempit dari 7 bar, close menembus high/low-nya; arah ikut bias H1
         (EMA20 vs EMA50 H1 yang sudah selesai). BUY dan SELL.
      2) Engulfing bullish M5 yang menyentuh EMA20 saat EMA20 > EMA50, dengan bias M15 (close > EMA50 M15) naik. Hanya BUY.
    Eksekusi & manajemen di M1: SL tetap (default $4,5 = 45 pips), breakeven di CLOSE M1 (be_mode="m1close": kalau
    close M1 >= entry + be_trigger, SL pindah ke entry + be_plus), lalu trailing chandelier trail_usd dari close. Tanpa TP.
    be_mode="tick" (pemicu di high/low) menghasilkan win rate lebih tinggi tetapi rugi: runner terpotong oleh noise.
    Hasil 3 periode spot Dukascopy (Jan, Agu-Okt, Okt-Nov 2026): lihat RESEARCH.md."""
    import entry_scan as es
    import mtf

    def part(rule, name, bias, side):
        d = mtf.resample(df, rule)
        I = es.precompute(d)
        long, short = (x.fillna(False).astype(bool) for x in es.entry(name, I))
        b = I[f"bias_{bias}"]
        asia = I["hour"] < asia_end
        long, short = long & (b > 0) & asia, short & (b < 0) & asia
        if side == "long":
            short = short & False
        no = pd.Series(False, index=d.index)
        plan = _plan(d, long, short, pd.Series(sl_usd, index=d.index), np.nan, no, no)
        return mtf.to_m1(plan, df, rule)

    p1, p2 = part("15min", "nr7", nr7_bias, "both"), part("5min", "engulf", "m15", "long")
    plan = p1.copy()
    plan["entry"] = np.where(p1["entry"] != 0, p1["entry"], p2["entry"])
    plan["be_trigger"], plan["be_plus"], plan["trail"], plan["be_touch"] = be_trigger, be_plus, trail_usd, be_mode == "tick"
    return plan

STRATEGIES = {
    "asia_nr7_engulf": strat_asia_nr7_engulf,
    "macd_asia_m1": strat_macd_asia_m1,
    "asia_nr7_runner": strat_asia_nr7_runner,
    "sweep_sell_runner": strat_sweep_sell_runner,
    "squeeze_runner": strat_squeeze_runner,
    "sell_rally_scalp": strat_sell_rally_scalp,
    "trend_breakout": strat_trend_breakout,
    "ema_trend": strat_ema_trend,
    "donchian": strat_donchian,
    "session_break": strat_session_breakout,
    "mean_revert": strat_mean_revert,
}
INTRADAY_ONLY = {"session_break"}


# ---------------------------------------------------------------------------
# Mesin backtest
# ---------------------------------------------------------------------------
@dataclass
class Config:
    capital: float = 10_000.0
    risk_pct: float = 1.0        # % ekuitas yang dirisikokan per trade
    spread: float = 0.30         # spread dalam $ per oz (dibayar setengah saat masuk, setengah saat keluar)
    commission: float = 0.0      # komisi round-trip per lot ($)
    max_leverage: float = 100.0  # batas nilai posisi / ekuitas
    slippage: float = 0.0        # slippage $ per oz yang merugikan, dikenakan pada entry market dan eksekusi SL


@dataclass
class Trade:
    direction: int
    entry_time: pd.Timestamp
    entry_price: float
    sl_price: float
    tp_price: float
    lots: float
    risk_usd: float
    exit_time: pd.Timestamp = None
    exit_price: float = float("nan")
    reason: str = ""
    pnl: float = 0.0
    r_multiple: float = 0.0
    partial_pnl: float = 0.0   # profit dari penutupan sebagian (partial TP)
    partial_done: bool = False
    mfe: float = 0.0           # profit maksimum (dari close) selama posisi, $


def run_backtest(df: pd.DataFrame, plan: pd.DataFrame, cfg: Config, start: int = 0, end: int | None = None):
    """Satu posisi dalam satu waktu. Kalau SL dan TP tersentuh di bar yang sama, dianggap kena SL (konservatif)."""
    end = len(df) if end is None else end
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    entry_sig = plan["entry"].to_numpy()
    sl_d, tp_d = plan["sl"].to_numpy(), plan["tp"].to_numpy()
    ex_long, ex_short = plan["exit_long"].to_numpy(), plan["exit_short"].to_numpy()
    trail = plan["trail"].to_numpy() if "trail" in plan.columns else None
    # Opsional: breakeven-plus dan trailing yang baru aktif setelah profit tertentu (semua dalam $)
    be_trig = plan["be_trigger"].to_numpy() if "be_trigger" in plan.columns else None
    be_plus = plan["be_plus"].to_numpy() if "be_plus" in plan.columns else None
    trail_start = plan["trail_start"].to_numpy() if "trail_start" in plan.columns else None
    # Opsional: partial TP. Tutup `partial_frac` dari posisi di jarak `partial_tp` ($), lalu SL ke entry + be_plus
    ptp = plan["partial_tp"].to_numpy() if "partial_tp" in plan.columns else None
    pfrac = plan["partial_frac"].to_numpy() if "partial_frac" in plan.columns else None
    # Opsional: be_touch=True -> pemicu breakeven dicek di high/low bar (seperti EA tick), bukan hanya di close.
    # Konservatif: kalau di bar yang sama harga juga sudah kembali ke SL baru, posisi dianggap tertutup di SL baru.
    be_touch = plan["be_touch"].to_numpy() if "be_touch" in plan.columns else None
    # Opsional: lock_frac -> SL mengunci lock_frac x profit maksimum (diukur dari close), aktif setelah be_trigger tercapai.
    lock_frac = plan["lock_frac"].to_numpy() if "lock_frac" in plan.columns else None
    times = df.index
    half = cfg.spread / 2

    equity = cfg.capital
    pos: Trade | None = None
    pending_entry, pending_sl, pending_tp = 0, np.nan, np.nan
    pending_exit = False
    trades: list[Trade] = []
    curve = np.empty(end - start)

    def close(i, price, reason):
        nonlocal equity, pos
        fill = price - pos.direction * (half + (cfg.slippage if reason in ("SL", "BE") else 0.0))
        pnl = pos.direction * (fill - pos.entry_price) * pos.lots * OZ_PER_LOT - cfg.commission * pos.lots
        pnl += pos.partial_pnl
        pos.exit_time, pos.exit_price, pos.reason = times[i], fill, reason
        pos.pnl, pos.r_multiple = pnl, pnl / pos.risk_usd
        equity += pnl
        trades.append(pos)
        pos = None

    for i in range(start, end):
        # 1) Eksekusi perintah dari close bar sebelumnya, di harga open bar ini
        if pos is not None and pending_exit:
            close(i, o[i], "signal")
        pending_exit = False
        if pos is None and pending_entry != 0 and pending_sl > 0 and equity > 0:
            d = pending_entry
            fill = o[i] + d * (half + cfg.slippage)
            risk_usd = equity * cfg.risk_pct / 100
            oz = risk_usd / pending_sl
            oz = min(oz, equity * cfg.max_leverage / fill)
            lots = oz / OZ_PER_LOT
            pos = Trade(d, times[i], fill, fill - d * pending_sl,
                        fill + d * pending_tp if not np.isnan(pending_tp) else np.nan,
                        lots, pending_sl * oz)
        pending_entry = 0

        # 2) Cek SL / TP di dalam bar
        if pos is not None:
            d = pos.direction
            hit_sl = l[i] <= pos.sl_price if d == 1 else h[i] >= pos.sl_price
            hit_tp = (not np.isnan(pos.tp_price)) and (h[i] >= pos.tp_price if d == 1 else l[i] <= pos.tp_price)
            if hit_sl:
                gap = (o[i] < pos.sl_price) if d == 1 else (o[i] > pos.sl_price)
                close(i, o[i] if gap else pos.sl_price, "SL")
            elif hit_tp:
                gap = (o[i] > pos.tp_price) if d == 1 else (o[i] < pos.tp_price)
                close(i, o[i] if gap else pos.tp_price, "TP")

        # 2a) Partial TP: sebagian posisi ditutup saat harga menyentuh target, SL sisa ke breakeven-plus
        if pos is not None and ptp is not None and not pos.partial_done and not np.isnan(ptp[i]):
            d = pos.direction
            target = pos.entry_price + d * ptp[i]
            if (h[i] >= target) if d == 1 else (l[i] <= target):
                frac = 0.5 if pfrac is None or np.isnan(pfrac[i]) else pfrac[i]
                fill = target - d * half
                pos.partial_pnl += d * (fill - pos.entry_price) * pos.lots * frac * OZ_PER_LOT
                pos.lots *= (1 - frac)
                pos.partial_done = True
                plus = 0.0 if be_plus is None or np.isnan(be_plus[i]) else be_plus[i]
                new_sl = pos.entry_price + d * plus
                pos.sl_price = max(pos.sl_price, new_sl) if d == 1 else min(pos.sl_price, new_sl)

        # 2a') Breakeven versi tick (be_touch): pemicu dicek di ekstrem bar, SL baru = entry + plus (plus <= pemicu)
        if pos is not None and be_touch is not None and be_touch[i] and be_trig is not None and not np.isnan(be_trig[i]):
            d = pos.direction
            ext = h[i] if d == 1 else l[i]
            if d * (ext - pos.entry_price) >= be_trig[i]:
                plus = 0.0 if be_plus is None or np.isnan(be_plus[i]) else min(be_plus[i], be_trig[i])
                new_sl = pos.entry_price + d * plus
                if (d == 1 and new_sl > pos.sl_price) or (d == -1 and new_sl < pos.sl_price):
                    pos.sl_price = new_sl
                    back = l[i] <= new_sl if d == 1 else h[i] >= new_sl
                    if back:
                        close(i, new_sl, "BE")

        # 2b) Trailing stop (chandelier): geser SL mengikuti close, berlaku mulai bar berikutnya
        if pos is not None:
            d = pos.direction
            profit = d * (c[i] - pos.entry_price)
            cands = []
            pos.mfe = max(pos.mfe, profit)
            if be_trig is not None and not np.isnan(be_trig[i]) and profit >= be_trig[i]:
                plus = 0.0 if be_plus is None or np.isnan(be_plus[i]) else be_plus[i]
                # SL plus tidak boleh melewati harga sekarang (stop di atas pasar = eksekusi di pasar)
                cands.append(min(pos.entry_price + d * plus, c[i]) if d == 1 else max(pos.entry_price + d * plus, c[i]))
            if lock_frac is not None and not np.isnan(lock_frac[i]) and be_trig is not None and not np.isnan(be_trig[i]) \
                    and pos.mfe >= be_trig[i]:
                lock = pos.entry_price + d * lock_frac[i] * pos.mfe
                cands.append(min(lock, c[i]) if d == 1 else max(lock, c[i]))
            if trail is not None and not np.isnan(trail[i]) and \
                    (trail_start is None or np.isnan(trail_start[i]) or profit >= trail_start[i]):
                cands.append(c[i] - d * trail[i])
            for new_sl in cands:
                pos.sl_price = max(pos.sl_price, new_sl) if d == 1 else min(pos.sl_price, new_sl)

        # 3) Sinyal di close bar ini -> dieksekusi di open bar berikutnya
        if pos is not None:
            pending_exit = bool(ex_long[i]) if pos.direction == 1 else bool(ex_short[i])
        elif entry_sig[i] != 0 and i + 1 < end:
            pending_entry, pending_sl, pending_tp = int(entry_sig[i]), sl_d[i], tp_d[i]

        open_pnl = 0.0 if pos is None else pos.partial_pnl + pos.direction * (c[i] - pos.entry_price) * pos.lots * OZ_PER_LOT
        curve[i - start] = equity + open_pnl

    if pos is not None:  # tutup posisi yang masih terbuka di akhir data
        close(end - 1, c[end - 1], "end")
        curve[-1] = equity

    return trades, pd.Series(curve, index=times[start:end])


# ---------------------------------------------------------------------------
# Statistik
# ---------------------------------------------------------------------------
def summarize(name: str, trades: list[Trade], curve: pd.Series, capital: float) -> dict:
    r = np.array([t.r_multiple for t in trades])
    pnl = np.array([t.pnl for t in trades])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    dd = (curve / curve.cummax() - 1).min() * 100 if len(curve) else 0.0
    streak = longest = 0
    for p in pnl:
        streak = streak + 1 if p <= 0 else 0
        longest = max(longest, streak)
    net = (curve.iloc[-1] / capital - 1) * 100 if len(curve) else 0.0
    return {
        "strategy": name,
        "trades": len(trades),
        "win_rate_%": 100 * len(wins) / len(pnl) if len(pnl) else np.nan,
        "avg_win_R": r[r > 0].mean() if (r > 0).any() else np.nan,
        "avg_loss_R": r[r <= 0].mean() if (r <= 0).any() else np.nan,
        "expectancy_R": r.mean() if len(r) else np.nan,
        "profit_factor": wins.sum() / -losses.sum() if losses.sum() < 0 else np.inf,
        "net_return_%": net,
        "max_dd_%": dd,
        "max_loss_streak": longest,
    }


def print_table(rows: list[dict], title: str) -> None:
    print(f"\n=== {title} ===")
    if not rows:
        print("(tidak ada hasil)")
        return
    t = pd.DataFrame(rows).set_index("strategy")
    with pd.option_context("display.width", 200, "display.max_columns", 20, "display.float_format", "{:,.2f}".format):
        print(t.to_string())
    few = t.index[t["trades"] < 30].tolist()
    if few:
        print(f"  ! Trade < 30 untuk: {', '.join(few)} -> sampel terlalu kecil, hasil belum bisa dipercaya.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None) -> None:
    p = argparse.ArgumentParser(description="Backtest beberapa strategi XAUUSD.",
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--source", choices=["yf", "csv", "demo"], default="yf")
    p.add_argument("--csv", help="path file CSV (untuk --source csv)")
    p.add_argument("--tz-offset", type=float, default=0.0, help="jam zona waktu CSV terhadap UTC (MT5 biasanya 2 atau 3)")
    p.add_argument("--ticker", default="GC=F", help="ticker Yahoo Finance")
    p.add_argument("--interval", default="1h", help="interval Yahoo (1h maksimal ~730d, 1d bisa bertahun-tahun)")
    p.add_argument("--period", default="730d")
    p.add_argument("--strategies", default=",".join(STRATEGIES), help="daftar strategi dipisah koma")
    p.add_argument("--capital", type=float, default=10_000)
    p.add_argument("--risk", type=float, default=1.0, help="risiko %% per trade")
    p.add_argument("--spread", type=float, default=0.30, help="spread $ per oz")
    p.add_argument("--commission", type=float, default=0.0, help="komisi round-trip per lot")
    p.add_argument("--split", type=float, default=0.7,
                   help="porsi data in-sample; sisanya out-of-sample (0 = nonaktif)")
    p.add_argument("--out", default="results", help="folder output (trades CSV, ringkasan, grafik ekuitas)")
    args = p.parse_args(argv)

    if args.source == "csv":
        if not args.csv:
            p.error("--csv wajib diisi untuk --source csv")
        df = load_csv(args.csv, args.tz_offset)
    elif args.source == "yf":
        df = load_yf(args.ticker, args.interval, args.period)
    else:
        df = make_demo()
        print("!! MODE DEMO: data sintetis, hasil di bawah TIDAK mencerminkan pasar emas sungguhan.")

    if len(df) < 300:
        sys.exit(f"Data terlalu sedikit ({len(df)} bar). Minimal ~300 bar.")
    step = df.index.to_series().diff().median()
    intraday = step <= pd.Timedelta(hours=1)
    print(f"Data: {len(df):,} bar | {df.index[0]} s/d {df.index[-1]} (UTC) | timeframe ~{step}")

    cfg = Config(capital=args.capital, risk_pct=args.risk, spread=args.spread, commission=args.commission)
    names = [s.strip() for s in args.strategies.split(",") if s.strip()]
    unknown = set(names) - set(STRATEGIES)
    if unknown:
        p.error(f"Strategi tidak dikenal: {unknown}. Pilihan: {list(STRATEGIES)}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    split_i = int(len(df) * args.split) if 0 < args.split < 1 else None
    full_rows, is_rows, oos_rows, curves = [], [], [], {}

    for name in names:
        if name in INTRADAY_ONLY and not intraday:
            print(f"- {name}: dilewati (butuh data intraday H1 atau lebih kecil)")
            continue
        plan = STRATEGIES[name](df)
        trades, curve = run_backtest(df, plan, cfg)
        full_rows.append(summarize(name, trades, curve, cfg.capital))
        curves[name] = curve
        pd.DataFrame([asdict(t) for t in trades]).to_csv(out / f"trades_{name}.csv", index=False)
        if split_i:
            t_is, c_is = run_backtest(df, plan, cfg, 0, split_i)
            t_oos, c_oos = run_backtest(df, plan, cfg, split_i, len(df))
            is_rows.append(summarize(name, t_is, c_is, cfg.capital))
            oos_rows.append(summarize(name, t_oos, c_oos, cfg.capital))

    print(f"\nModal ${cfg.capital:,.0f} | risiko {cfg.risk_pct}%/trade | spread ${cfg.spread} | komisi ${cfg.commission}/lot")
    print_table(full_rows, "SELURUH PERIODE")
    if split_i:
        print_table(is_rows, f"IN-SAMPLE (s/d {df.index[split_i - 1]:%Y-%m-%d})")
        print_table(oos_rows, f"OUT-OF-SAMPLE (mulai {df.index[split_i]:%Y-%m-%d})")
        print("  Strategi yang bagus di in-sample tapi buruk di out-of-sample kemungkinan overfit.")

    pd.DataFrame(full_rows).to_csv(out / "summary.csv", index=False)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 5))
        for name, curve in curves.items():
            ax.plot(curve.index, curve.values, label=name, linewidth=1.2)
        if split_i:
            ax.axvline(df.index[split_i], color="grey", linestyle="--", linewidth=1, label="awal out-of-sample")
        ax.set_title("Kurva ekuitas per strategi")
        ax.set_ylabel("Ekuitas ($)")
        ax.grid(alpha=0.3)
        ax.legend()
        fig.tight_layout()
        fig.savefig(out / "equity.png", dpi=120)
        print(f"\nGrafik ekuitas: {out / 'equity.png'}")
    except ImportError:
        print("\n(matplotlib tidak terpasang, grafik ekuitas dilewati)")
    print(f"Detail trade & ringkasan tersimpan di folder: {out}/")


if __name__ == "__main__":
    main()
