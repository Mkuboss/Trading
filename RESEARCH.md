# Riset Kombinasi Teknikal XAUUSD

Tanggal riset: 8 November 2026

## Data

| Dataset | Sumber | Periode | Bar |
|---|---|---|---|
| D1 | Yahoo Finance `GC=F` | Agu 2000 – Nov 2026 (26 tahun) | 6.573 |
| H1 | Yahoo Finance `GC=F` | Jun 2024 – Nov 2026 | 13.731 |
| H1 spot | Dukascopy XAUUSD (`fetch_data.py`) | 2015 – 2026 | *download lambat karena rate limit, belum lengkap* |

Biaya: spread $0,40/oz. Risiko 1% per trade (kecuali disebut lain).

## Metode (anti-overfitting)

1. **9 trigger** (Donchian 20/55, EMA pullback, EMA cross, MACD, Supertrend, Bollinger squeeze, RSI mean reversion, Asia breakout)
   × **filter** (tren EMA200 / EMA50 harian, ADX, sesi London–NY, arah long/short/both)
   × **exit** (SL 1,5/2,5 ATR; TP 1,5R/2R/3R; trailing 3 ATR; sinyal balik)
   = **1.440 kombinasi di D1** dan **5.940 di H1+H4**.
2. Seleksi **hanya di data in-sample**, dengan skor t-stat R dikali penalti drawdown, minimal 60–120 trade.
3. Kandidat diuji di **out-of-sample** yang tidak dipakai saat seleksi:
   - D1: IS 2000–2017, OOS 2018–2026
   - H1: IS Jun 2024–Sep 2025, OOS Okt 2025–Nov 2026 (termasuk crash 2026)
4. Pengecekan lanjutan: sensitivitas parameter, benchmark entry acak, long vs short, hasil per tahun.

## Temuan utama

1. **Yang bertahan di OOS: breakout tren arah long + filter tren + trailing stop.** Polanya sama di D1, H4, dan H1.
2. **Mean reversion (BB + RSI) gagal di OOS** di semua timeframe (D1 −0,21R, H1 −0,10R), padahal bagus di IS.
3. **EMA pullback dengan TP tetap gagal di OOS** (+0,44R IS menjadi −0,09R OOS).
4. **Short pada emas konsisten rugi**: Donchian short D1 −0,41R (IS) / −0,42R (OOS). Drift naik jangka panjang emas membuat short trend-following tidak berbayar.
5. **Sebagian besar edge berasal dari tren naik emas dan exit trailing, bukan dari sinyal entry.** Entry long ACAK dengan exit yang sama sudah menghasilkan +0,59R (IS) / +0,69R (OOS). Strategi final memberi +0,84R / +1,18R, lebih baik tapi tipis (sekitar persentil 90–95 dari hasil acak).
6. **Intraday lebih rapuh.** Banyak kombinasi H1 dengan IS +0,5R jatuh ke sekitar 0R di OOS.
7. **Tidak ada "tebing" parameter.** Semua 40 variasi Donchian (N 20/55 × SL 1–3 ATR × trailing 2–5 ATR) positif di IS dan OOS. Itu tanda strategi ini robust, bukan kebetulan.

## Strategi final: `trend_breakout`

```
Arah     : LONG saja
Filter   : close harian kemarin > EMA50 harian
Entry    : close menembus high tertinggi 20 bar sebelumnya
Stop     : 1,5 × ATR(14) dari harga masuk
Exit     : trailing stop 3 × ATR(14) dari close (tanpa TP tetap)
Risiko   : 1% ekuitas per trade (lot dihitung dari jarak SL)
```

Parameter diambil dari **tengah** area yang stabil, bukan dari angka terbaik. Contohnya trailing 3 ATR dipilih walaupun trailing 5 ATR terlihat lebih tinggi di OOS.

### Hasil

| Dataset | Trade | Win rate | Avg win | Expectancy | PF | Return | Max DD |
|---|---|---|---|---|---|---|---|
| D1 2000–2026, risiko 1% | 129 | 40% | 3,7R | +0,95R | 2,72 | +217% | −9% |
| D1 2000–2026, risiko 2% | 129 | 40% | 3,7R | +0,95R | 2,65 | +790% | −17% |
| H1 2024–2026, risiko 1% | 177 | 39% | 2,4R | +0,35R | 1,66 | +79% | −13% |

Perbandingan:
- Buy & hold emas 2000–2026 punya max drawdown **−44%**.
- Di tahun-tahun buruk emas, strategi ini rugi jauh lebih kecil: 2013 strategi −1,4% vs emas −28%; 2015 −4,4% vs −10%; 2026 (s/d Nov) +2,2% vs −6%.
- Di tahun bull ekstrem, strategi ini tertinggal jauh: 2025 +9% vs emas +64%, karena risikonya hanya 1% per trade dan hanya sekitar 5 trade per tahun.
- Strategi lain di D1: `ema_trend` +0,20R, `donchian` (both side) +0,03R, `mean_revert` +0,13R dengan DD −21%.

### Status sinyal saat ini (6 Nov 2026)

Close $4.075 < EMA50 harian $4.179, jadi **filter OFF: tidak ada sinyal buy**. Strategi diam (flat) sampai harga kembali di atas EMA50 harian dan menembus high 20 bar. Ini sejalan dengan kondisi pasar yang sedang koreksi.

## Keterbatasan (baca sebelum memakai uang sungguhan)

- **Tidak ada strategi yang "sempurna".** Strategi ini kalah sekitar 60% dari waktu, dengan rangkaian kalah hingga 6–10 kali berturut-turut.
- Kinerjanya sangat bergantung pada emas yang tetap bergerak dalam tren naik jangka panjang. Kalau emas masuk bear market panjang seperti 2013–2015, strategi ini kebanyakan diam atau rugi kecil.
- `GC=F` adalah harga futures, bukan spot broker. Validasi H1 jangka panjang dengan data spot Dukascopy belum selesai.
- Swap, slippage saat berita, dan spread yang melebar tidak dimodelkan.
- Ribuan kombinasi sudah diuji. Walaupun seleksi dilakukan di IS, tetap ada risiko kebetulan statistik. Uji di akun demo minimal 3 bulan sebelum memakai akun real.

## Reproduksi

```bash
pip install -r requirements.txt
python -c "import backtest as bt; d=bt.load_yf('GC=F','1d','max'); d.index.name='datetime'; d.to_csv('data/GC_D1.csv')"
python research.py --csv data/GC_D1.csv --tfs 1d --is-end 2017-12-31 --min-trades 60
python backtest.py --source csv --csv data/GC_D1.csv --spread 0.4
python fetch_data.py --start 2015 --out data/XAUUSD_H1.csv  # data spot H1 (lambat, bisa dilanjutkan)
python research.py --csv data/XAUUSD_H1.csv --tfs 1h,4h --is-end 2022-12-31
```

---

# Riset 1 bulan terakhir: win rate > 80%

Data: Yahoo `GC=F` M5/M15/H1, **7 Okt – 6 Nov 2026** (bulan ini), dicek ulang di **8 Sep – 6 Okt 2026** (bulan lalu). Spread $0,40, risiko 1%.

- `month_scan.py`: 9.000 kombinasi. Hanya 30% yang profit di bulan ini dan 10% yang profit di dua bulan.
- `win_scan.py`: 16.200 kombinasi dengan TP kecil. **437** punya win rate ≥ 80% di bulan ini, **177** di dua bulan, dan **114** di dua bulan sekaligus tetap profit.
- Rata-rata kombinasi dengan win rate ≥ 80% justru **rugi** di bulan lalu (expectancy −0,04R). Win rate tinggi tidak sama dengan profit.

## Strategi: `sell_rally_scalp` (M5)

```
Arah    : SELL saja
Entry   : MACD(12,26,9) memotong signal ke bawah, di atas level 0 (sell saat harga memantul naik)
Filter  : ADX(14) > 20, jam 07–20 UTC (14:00–03:00 WIB)
SL      : 3,5 × ATR(14)
TP      : 0,25 × SL (≈ 0,875 ATR)
```

| Risiko | Periode | Trade | Win rate | Return | Max DD | Kalah beruntun |
|---|---|---|---|---|---|---|
| 1% | Bulan lalu | 53 | 88,7% | +5,2% | −3,5% | 3 |
| 1% | Bulan ini | 26 | **92,3%** | +3,7% | −1,4% | 1 |
| 2% | Bulan lalu | 53 | 88,7% | +10,6% | −7,0% | 3 |
| 2% | Bulan ini | 26 | **92,3%** | +7,5% | −2,7% | 1 |

- Semua minggu di bulan ini profit.
- Tetap profit dengan spread $0,20 sampai $0,80.
- Rata-rata menang +0,24R, rata-rata kalah −1,01R, durasi rata-rata 1,1 jam.

**Titik impas: win rate ≈ 81%.** Kalau win rate turun di bawah sekitar 81%, strategi ini mulai rugi. Margin aman hanya sekitar 8–11 poin.

Kandidat lain yang lolos:
- MACD versi TP 0,4R: win 81–82%, +3–7%/bulan
- Donchian-55 sell M15 TP 0,25R: win 86% di dua bulan, +3%/bulan

**Risiko:**
- Hanya 2 bulan data, dan keduanya dalam fase emas turun dan bergejolak.
- Saat emas berbalik naik kuat, sell saat harga memantul akan kena SL besar berulang kali. Hentikan strategi jika harian close di atas EMA50 harian.
- Uji di akun demo dulu.
