#!/usr/bin/env python3
"""Cek silang logika EA (indexing gaya MT5: shift 1 = bar yang baru selesai, bias dari bar HTF sebelum bar pemuat)
terhadap sinyal strat_asia_nr7_engulf di backtest.py. Keduanya dihitung dengan cara berbeda; waktunya harus sama."""
import numpy as np
import pandas as pd

import backtest as bt
import mtf

ASIA_END = 7


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def ea_signals(df1):
    m15, m5, h1 = mtf.resample(df1, "15min"), mtf.resample(df1, "5min"), mtf.resample(df1, "1h")
    e20h, e50h = ema(h1.close, 20), ema(h1.close, 50)
    e20m5, e50m5 = ema(m5.close, 20), ema(m5.close, 50)
    e50m15 = ema(m15.close, 50)
    sig = {}
    # --- NR7 M15: bar k baru selesai (shift 1), bar k-1 (shift 2) tersempit dari shift 2..8
    rng = (m15.high - m15.low).to_numpy()
    for k in range(8, len(m15)):
        t = m15.index[k]
        if t.hour >= ASIA_END:
            continue
        if rng[k - 1] > rng[k - 7:k].min():
            continue
        # bias H1: bar H1 yang memuat t -> pakai bar sebelumnya
        j = h1.index.searchsorted(t, side="right") - 1
        if j - 1 < 0:
            continue
        b = np.sign(e20h.iloc[j - 1] - e50h.iloc[j - 1])
        c1 = m15.close.iloc[k]
        d = 1 if (c1 > m15.high.iloc[k - 1] and b > 0) else (-1 if (c1 < m15.low.iloc[k - 1] and b < 0) else 0)
        if d:
            sig.setdefault(t + pd.Timedelta(minutes=15), d)   # EA bertindak di bar M1 pertama setelah bar M15 tutup
    # --- engulfing M5
    for k in range(1, len(m5)):
        t = m5.index[k]
        if t.hour >= ASIA_END:
            continue
        o1, c1 = m5.open.iloc[k], m5.close.iloc[k]
        o2, c2, l2 = m5.open.iloc[k - 1], m5.close.iloc[k - 1], m5.low.iloc[k - 1]
        if not (c1 > o1 and c2 < o2 and c1 >= o2 and o1 <= c2):
            continue
        if not (l2 <= e20m5.iloc[k] and e20m5.iloc[k] > e50m5.iloc[k]):
            continue
        j = m15.index.searchsorted(t, side="right") - 1
        if j - 1 < 0 or not (m15.close.iloc[j - 1] > e50m15.iloc[j - 1]):
            continue
        sig.setdefault(t + pd.Timedelta(minutes=5), 1)       # NR7 di waktu yang sama diprioritaskan (setdefault)
    return pd.Series(sig).sort_index()


if __name__ == "__main__":
    for path in ["data/duka_m1_jan26.csv", "data/duka_m1_augoct26.csv", "data/duka_m1_octnov26.csv"]:
        df1 = bt.load_csv(path)
        plan = bt.strat_asia_nr7_engulf(df1)
        ent = plan["entry"][plan["entry"] != 0]
        # backtest: sinyal di bar M1 terakhir bar HTF -> eksekusi di bar M1 berikutnya
        pos = df1.index.get_indexer(ent.index) + 1
        pos = pos[pos < len(df1)]
        bt_exec = pd.Series(ent.to_numpy()[: len(pos)], index=df1.index[pos])
        ea = ea_signals(df1)
        # EA: bar M1 pertama dengan waktu >= waktu tutup bar HTF
        ea_idx = df1.index.searchsorted(ea.index)
        ea_idx = ea_idx[ea_idx < len(df1)]
        ea_exec = pd.Series(ea.to_numpy()[: len(ea_idx)], index=df1.index[ea_idx])
        ea_exec = ea_exec[~ea_exec.index.duplicated()]
        same = bt_exec.index.intersection(ea_exec.index)
        agree = int((bt_exec[same] == ea_exec[same]).sum())
        print(f"{path}: backtest {len(bt_exec)} sinyal | EA {len(ea_exec)} | waktu sama {len(same)} | arah sama {agree} "
              f"| hanya backtest {len(bt_exec.index.difference(ea_exec.index))} | hanya EA {len(ea_exec.index.difference(bt_exec.index))}")
        only_bt = bt_exec.index.difference(ea_exec.index)[:3].tolist(); only_ea = ea_exec.index.difference(bt_exec.index)[:3].tolist()
        if only_bt or only_ea:
            print("   contoh beda:", only_bt, only_ea)
