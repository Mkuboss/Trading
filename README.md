# Backtest Strategi XAUUSD

Script untuk menguji dan membandingkan beberapa metode trading emas (XAUUSD) di data historis.

## Strategi yang diuji

| Nama | Metode | Entry | Exit |
|---|---|---|---|
| `ema_trend` | Trend following | EMA50 > EMA200 dan RSI naik lagi melewati 40 (buy), kebalikannya untuk sell | SL 1,5 ATR, TP 3 ATR, atau close menembus EMA200 |
| `donchian` | Breakout channel (Turtle) | Close menembus high/low 20 bar | SL 2 ATR, trailing di low/high 10 bar |
| `session_break` | Breakout sesi Asia | Breakout pertama dari range 00–07 UTC, sampai jam 16 UTC | SL di sisi lain range, TP 2R, tutup jam 20 UTC |
| `asia_nr7_runner` | SL $3 tetap + trailing (riset entry) | NR7 breakout M15, sesi Asia, bias H1 | SL $3, trailing $9 |
| `sweep_sell_runner` | SL $3 tetap + trailing (riset entry) | Liquidity sweep sell M15, tren H1 turun | SL $3, trailing $9 |
| `squeeze_runner` | SL tetap $3, tanpa TP, SL plus + trailing | BB squeeze breakout M15 | SL $3, BE+$1 setelah +$3, trailing $15 |
| `sell_rally_scalp` | Win rate tinggi (~90%) | MACD sell-the-rally M5, ADX>20, sesi London–NY | SL 3,5 ATR, TP 0,25R |
| **`trend_breakout`** | **Strategi final hasil riset** (lihat [RESEARCH.md](RESEARCH.md)) | Close tembus high 20 bar, hanya jika close harian kemarin > EMA50 harian (long saja) | SL 1,5 ATR, trailing 3 ATR |
| `mean_revert` | Mean reversion | Close di luar Bollinger Band (20, 2) dan RSI < 30 / > 70 | SL 1,5 ATR, atau kembali ke middle band |

Parameter tiap strategi ada sebagai argumen default di fungsi `strat_*` di `backtest.py` dan bisa langsung diubah.

Untuk riset kombinasi otomatis (ribuan kombinasi indikator, seleksi in-sample, validasi out-of-sample) gunakan `research.py`. Untuk data spot H1 dari Dukascopy gunakan `fetch_data.py`. Hasil dan metodenya ada di [RESEARCH.md](RESEARCH.md).

## Instalasi

```bash
pip install -r requirements.txt
```

## Cara pakai

```bash
# Data Yahoo Finance (GC=F = gold futures, mendekati spot XAUUSD), H1 ~2 tahun
python backtest.py --source yf --interval 1h --period 730d

# Data harian jangka panjang (session_break otomatis dilewati)
python backtest.py --source yf --interval 1d --period 10y

# Data dari MetaTrader 5 (paling akurat untuk broker Anda)
#   MT5 -> View -> Symbols -> Bars -> pilih XAUUSD, H1 -> Export Bars
python backtest.py --source csv --csv XAUUSD_H1.csv --tz-offset 2

# Data sintetis, hanya untuk mengetes script
python backtest.py --source demo
```

Opsi penting:

| Opsi | Default | Keterangan |
|---|---|---|
| `--capital` | 10000 | Modal awal ($) |
| `--risk` | 1.0 | Risiko % ekuitas per trade (ukuran lot dihitung otomatis dari jarak SL) |
| `--spread` | 0.30 | Spread $ per oz. Sesuaikan dengan broker Anda |
| `--commission` | 0 | Komisi round-trip per lot (akun ECN/raw) |
| `--split` | 0.7 | 70% data awal untuk in-sample, 30% sisanya untuk out-of-sample |
| `--strategies` | semua | Contoh: `--strategies ema_trend,donchian` |
| `--tz-offset` | 0 | Zona waktu CSV terhadap UTC. Server MT5 umumnya GMT+2 (musim dingin) / GMT+3 (musim panas) |
| `--out` | results | Folder output |

## Output

- Tabel di terminal untuk seluruh periode, in-sample, dan out-of-sample
- `results/summary.csv`: ringkasan statistik
- `results/trades_<strategi>.csv`: detail setiap trade
- `results/equity.png`: kurva ekuitas semua strategi

### Cara membaca hasil

| Kolom | Arti | Patokan sehat |
|---|---|---|
| `win_rate_%` | Persentase trade profit | Tidak harus tinggi kalau RR besar |
| `expectancy_R` | Rata-rata hasil per trade dalam R (1R = risiko per trade) | > 0,1 |
| `profit_factor` | Total profit / total rugi | > 1,3 |
| `max_dd_%` | Penurunan ekuitas terdalam dari puncak | Sesuai toleransi Anda, misalnya < 20% |
| `max_loss_streak` | Kalah beruntun terpanjang | Siapkan mental untuk angka ini |

**Penting:** strategi baru layak dipertimbangkan kalau hasil **out-of-sample** juga positif dan jumlah trade cukup (≥ 30, idealnya > 100). Bagus di in-sample tapi jelek di out-of-sample berarti tanda overfitting.

## Asumsi & keterbatasan

- Sinyal dihitung di close bar dan dieksekusi di open bar berikutnya, jadi tidak ada look-ahead bias.
- Hanya satu posisi dalam satu waktu per strategi.
- Kalau SL dan TP tersentuh di bar yang sama, dianggap kena SL (konservatif).
- Kalau harga gap melewati SL/TP, eksekusi di harga open (mensimulasikan slippage).
- Slippage saat berita, swap/biaya inap, dan spread yang melebar tidak dimodelkan, jadi hasil live biasanya lebih buruk.
- GC=F adalah harga futures, sedikit berbeda dari spot XAUUSD di broker. Untuk hasil paling realistis, pakai CSV dari MT5 broker Anda.

## Test

```bash
python -m pytest -q
```

> ⚠️ Hasil backtest tidak menjamin hasil di masa depan. Ini alat edukasi, bukan saran investasi.
