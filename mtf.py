#!/usr/bin/env python3
"""
Multi-timeframe: sinyal dihitung di timeframe besar (M5/M15), eksekusi & manajemen SL di M1.

Ini mendekati eksekusi tick di MT5: breakeven dan trailing bereaksi di setiap candle M1,
bukan menunggu candle M15 ditutup. Entry: sinyal di close bar TF besar -> eksekusi di open M1 berikutnya.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import backtest as bt


def resample(df1: pd.DataFrame, rule: str) -> pd.DataFrame:
    return df1.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def to_m1(plan_htf: pd.DataFrame, df1: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Petakan plan TF besar ke index M1. Sinyal bar TF besar yang mulai jam T berlaku pada bar M1 TERAKHIR
    di dalam bar itu (yang close-nya = close bar TF besar), sehingga eksekusi terjadi di open M1 berikutnya."""
    step = pd.tseries.frequencies.to_offset(rule)
    # waktu mulai bar HTF untuk setiap bar M1
    htf_start = df1.index.floor(rule)
    # bar M1 terakhir di setiap bar HTF
    last_in_bar = pd.Series(df1.index, index=df1.index).groupby(htf_start).transform("max")
    is_last = pd.Series(df1.index == last_in_bar.values, index=df1.index)
    p = plan_htf.reindex(htf_start.unique(), fill_value=np.nan)
    out = pd.DataFrame(index=df1.index)
    entry_map = p["entry"].reindex(htf_start).fillna(0).astype(int).to_numpy()
    out["entry"] = np.where(is_last.to_numpy(), entry_map, 0)
    for col in plan_htf.columns:
        if col == "entry":
            continue
        s = p[col].reindex(htf_start)
        if plan_htf[col].dtype == bool:
            v = s.fillna(False).astype(bool).to_numpy()
            out[col] = np.where(is_last.to_numpy(), v, False)
        else:
            out[col] = s.to_numpy()  # sl/tp/trail/be berlaku di setiap M1 dalam bar HTF
    return out


def run_mtf(df1: pd.DataFrame, rule: str, strat, cfg: bt.Config, start=None, end=None, **kw):
    """Jalankan strategi `strat(df_htf, **kw) -> plan` dengan sinyal di `rule` dan manajemen di M1."""
    dfh = resample(df1, rule)
    plan_h = strat(dfh, **kw)
    plan1 = to_m1(plan_h, df1, rule)
    s = 0 if start is None else int(np.searchsorted(df1.index, start))
    e = len(df1) if end is None else int(np.searchsorted(df1.index, end))
    return bt.run_backtest(df1, plan1, cfg, s, e)
