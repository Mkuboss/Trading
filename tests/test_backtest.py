import numpy as np
import pandas as pd
import pytest

import backtest as bt


def make_df(rows):
    idx = pd.date_range("2025-01-06 08:00", periods=len(rows), freq="h")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx, dtype=float)


def make_plan(df, entry_at, direction, sl, tp=np.nan):
    plan = pd.DataFrame({
        "entry": 0, "sl": sl, "tp": tp,
        "exit_long": False, "exit_short": False,
    }, index=df.index)
    plan.iloc[entry_at, plan.columns.get_loc("entry")] = direction
    return plan


CFG = bt.Config(capital=10_000, risk_pct=1.0, spread=0.0)


def test_long_hits_take_profit_for_2R():
    df = make_df([
        [2000, 2001, 1999, 2000],  # sinyal di close
        [2000, 2005, 1998, 2004],  # masuk di open 2000
        [2004, 2025, 2003, 2020],  # TP 2020 tersentuh
    ])
    trades, curve = bt.run_backtest(df, make_plan(df, 0, 1, sl=10, tp=20), CFG)
    assert len(trades) == 1
    t = trades[0]
    assert t.reason == "TP" and t.entry_price == 2000 and t.exit_price == 2020
    assert t.r_multiple == pytest.approx(2.0)
    assert curve.iloc[-1] == pytest.approx(10_200)


def test_sl_wins_when_sl_and_tp_hit_same_bar():
    df = make_df([
        [2000, 2001, 1999, 2000],
        [2000, 2030, 1980, 2000],  # SL 1990 dan TP 2020 sama-sama tersentuh
    ])
    trades, _ = bt.run_backtest(df, make_plan(df, 0, 1, sl=10, tp=20), CFG)
    assert trades[0].reason == "SL"
    assert trades[0].r_multiple == pytest.approx(-1.0)


def test_short_gap_through_stop_fills_at_open():
    df = make_df([
        [2000, 2001, 1999, 2000],
        [2000, 2001, 1995, 1996],  # masuk short di 2000, SL 2010
        [2020, 2025, 2015, 2018],  # gap di atas SL -> isi di open 2020
    ])
    trades, _ = bt.run_backtest(df, make_plan(df, 0, -1, sl=10), CFG)
    assert trades[0].reason == "SL" and trades[0].exit_price == 2020
    assert trades[0].r_multiple == pytest.approx(-2.0)


def test_spread_is_charged():
    cfg = bt.Config(capital=10_000, risk_pct=1.0, spread=0.5)
    df = make_df([
        [2000, 2001, 1999, 2000],
        [2000, 2001, 1999, 2000],
        [2000, 2001, 1999, 2000],
    ])
    trades, _ = bt.run_backtest(df, make_plan(df, 0, 1, sl=10), cfg)
    assert trades[0].reason == "end"
    assert trades[0].pnl < 0  # harga tidak bergerak, rugi sebesar spread


def test_load_mt5_csv(tmp_path):
    f = tmp_path / "XAUUSD_H1.csv"
    f.write_text(
        "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
        "2025.01.06\t10:00:00\t2630.1\t2635.0\t2628.0\t2633.2\t1000\t0\t20\n"
        "2025.01.06\t11:00:00\t2633.2\t2640.0\t2631.0\t2638.5\t1200\t0\t20\n"
    )
    df = bt.load_csv(str(f), tz_offset=2)
    assert list(df.columns) == ["open", "high", "low", "close"]
    assert df.index[0] == pd.Timestamp("2025-01-06 08:00")  # GMT+2 -> UTC
    assert df["close"].iloc[-1] == 2638.5


def test_all_strategies_run_on_demo_data():
    df = bt.make_demo(n_days=120)
    for name, fn in bt.STRATEGIES.items():
        plan = fn(df)
        assert set(plan["entry"].unique()) <= {-1, 0, 1}
        trades, curve = bt.run_backtest(df, plan, CFG)
        assert len(curve) == len(df)
        assert len(trades) > 0, name


def test_trailing_stop_locks_profit():
    df = make_df([
        [2000, 2001, 1999, 2000],
        [2000, 2010, 1999, 2010],  # masuk 2000, close 2010 -> SL naik ke 2005
        [2010, 2030, 2009, 2030],  # close 2030 -> SL naik ke 2025
        [2030, 2031, 2020, 2022],  # kena trailing di 2025
    ])
    plan = make_plan(df, 0, 1, sl=10)
    plan["trail"] = 5.0
    trades, _ = bt.run_backtest(df, plan, CFG)
    assert trades[0].reason == "SL" and trades[0].exit_price == 2025
    assert trades[0].r_multiple == pytest.approx(2.5)
