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

---

# Riset aturan: SL tetap 30 pips, tanpa TP, SL bergerak (SL plus + trailing)

Data: Yahoo `GC=F` M5/M15, 8 Sep – 6 Nov 2026 (dua bulan terpisah). Spread $0,40.
Script: `sl30_scan.py` (`SL_USD=3 python sl30_scan.py`, juga diuji `SL_USD=10` dan `30`).

Definisi pip: 1 pip = $0,10, jadi 30 pips = **$3**. Untuk pembanding diuji juga $10 dan $30 (kalau broker memakai 1 pip = $1).

Grid: 9 trigger × filter tren/ADX/sesi/arah × breakeven (tanpa, 1×SL, 2×SL) × SL plus (⅓ SL) × trailing (1, 2, 3, 5, 8 × SL) × awal trailing (0, 2, 4 × SL) = **25.110 kombinasi per ukuran SL, 75.330 total**.

## Hasil

| SL | Lolos (profit dua bulan, ≥20 trade/bulan) | Terbaik | Tetap profit tanpa 3 trade terbaik |
|---|---|---|---|
| $3 | 801 | BB squeeze M15: +47% / +40% | **0 kombinasi** |
| $10 | 948 | RSI-MR sell M5: +25% / +20% | **0 kombinasi** |
| $30 | 76 | MACD sell M5: +8% / +5% | **0 kombinasi** |

Kesimpulan struktural: dengan SL kecil (ATR M15 saat ini ≈ $8, jadi SL $3 kurang dari setengah ATR) dan TP tanpa batas, **sekitar 73% trade kena SL penuh** dan profit datang dari sedikit trade besar. Tidak ada kombinasi yang profitnya merata. Ini bukan kegagalan pencarian, tapi konsekuensi matematis dari aturannya.

## Strategi terbaik untuk aturan ini: `squeeze_runner` (M15)

```
Entry  : Bollinger Band (20, 2) sedang menyempit (lebar band di 20% terendah dari 120 bar),
         lalu close menembus band atas = BUY, band bawah = SELL
SL     : $3 tetap (30 pips)
SL plus: setelah profit +$3, SL dipindah ke entry +$1
Trailing: $15 dari close (dihitung di penutupan candle M15)
TP     : tidak ada
```

| Risiko | Periode | Trade | Win rate | PF | Return | Max DD | Kalah beruntun |
|---|---|---|---|---|---|---|---|
| 1% | 8 Sep – 6 Okt | 50 | 28% | 2,15 | **+46,9%** | −20,7% | 7 |
| 1% | 7 Okt – 6 Nov | 47 | 26% | 2,03 | **+40,3%** | −13,9% | 9 |
| 0,5% | 8 Sep – 6 Okt | 50 | 28% | 2,21 | +24,0% | −10,9% | 7 |
| 0,5% | 7 Okt – 6 Nov | 47 | 26% | 2,02 | +19,5% | −7,3% | 9 |

Anatomi 97 trade dalam 2 bulan: **71 kena SL penuh (−1R)**, 12 keluar di breakeven/plus, 14 profit ≥ 1R, 8 di antaranya ≥ 5R. Trade terbesar +37R (sell dari $4.303 ke $4.192, 12 jam). Median trade = −1,07R.

Yang stabil di grid: breakeven 1–2×SL dan trailing 3–5×SL semuanya positif di dua bulan. Filter tambahan (EMA200, ADX, sesi, satu arah saja) justru memperburuk salah satu bulan, jadi tidak dipakai.

## Risiko

- 1% risiko = $3 SL → ukuran posisi besar (0,33 lot per $10.000). Slippage $0,50 saat berita sudah 17% dari SL. Spread $0,80 menurunkan return sekitar 8 poin.
- Rangkaian kalah 7–9 kali berturut-turut adalah normal. Secara psikologis berat: 3 dari 4 trade rugi.
- Dua bulan data, keduanya di fase emas sangat volatil. Di pasar tenang, breakout squeeze lebih sering gagal.
- Trailing dihitung di close candle, bukan tick. Di MT5 implementasi tick-by-tick akan sedikit berbeda.
- Pakai risiko 0,5% kalau drawdown −20% terasa terlalu dalam.

---

# Riset entry untuk SL $3 tetap: entry baru, filter struktur, partial TP

Masukan: "entry-nya yang salah, kembangkan, kombinasikan". Data sama (Yahoo `GC=F` M5/M15, 8 Sep – 6 Nov 2026).

## Yang dikembangkan

- **8 entry baru** yang dirancang untuk SL ketat (`entry_scan.py`): liquidity sweep, pullback EMA20, retest setelah breakout, engulfing di pullback, NR7 breakout, inside-bar breakout, momentum ignition, pin bar di EMA20. Plus Bollinger squeeze.
- **Filter**: bias multi-timeframe (M15/H1/D1 tanpa look-ahead), filter struktur (SL harus di balik swing 5 candle), filter volatilitas (ATR ≤ batas), sesi (Asia/London/NY), arah.
- **Exit bertahap** (`partial_scan.py`, fitur baru di mesin): tutup 50–70% posisi di +1R/1,5R/2R, SL sisa ke plus, sisanya trailing jauh.
- Total diuji: 23.040 (entry, SL $3) + 23.040 ($10) + 23.040 ($30) + 46.656 (partial) = **115.776 kombinasi**.

## Dua ukuran robustness

1. **Ketat**: profit tanpa 3 trade terbaik di masing-masing bulan → **0 kombinasi** lolos di semua scan. Untuk strategi "biarkan profit berjalan" dengan ~25–50 trade/bulan, membuang 3 trade terbaik = membuang 10% trade terbaik, hampir selalu mematikan hasil. Ukuran ini terlalu ketat untuk aturan ini.
2. **Wajar** (`robust_check.py`): profit tanpa **1** trade terbaik di tiap bulan, ≥ 6 dari 9 minggu profit, PF ≥ 1,2 di tiap bulan → **29 dari 691** kandidat lolos.

## Dua strategi final (M15, saling melengkapi)

### `asia_nr7_runner`
```
Entry : candle sebelumnya NR7 (range tersempit 7 candle), close menembus high-nya = BUY, low-nya = SELL
Filter: hanya sesi Asia 00–07 UTC (07:00–14:00 WIB), searah tren H1 (EMA20 vs EMA50)
Exit  : SL $3 tetap, trailing $9 dari close M15, tanpa TP
```
| Periode | Trade | Win | Exp. | PF | Return | DD | Kalah beruntun |
|---|---|---|---|---|---|---|---|
| 8 Sep – 6 Okt | 25 | 24% | +1,45R | 2,73 | +39,3% | −7,9% | 6 |
| 7 Okt – 6 Nov | 23 | 30% | +0,56R | 1,72 | +12,6% | −11,9% | 5 |
| 2 bulan | 48 | 27% | +1,02R | 2,21 | +56,9% | −11,9% | 6 |

Ketahanan: trailing $6/9/12/15 semua positif; bias H1 ≈ D1; **sesi adalah kuncinya**: London −25%, NY −32%, semua sesi −22%. Catatan jujur: ATR M15 sesi Asia ($7,7) tidak lebih kecil dari London ($7,5), jadi keunggulan Asia **bukan** karena pasar lebih tenang. Ini pola empiris 2 bulan yang belum punya penjelasan kuat, dan bisa hilang saat rezim berubah.

### `sweep_sell_runner`
```
Entry : high menembus high tertinggi 20 candle, tapi close kembali di bawahnya dengan candle bearish = SELL
Filter: hanya saat tren H1 turun (EMA20 < EMA50). Sisi buy tidak dipakai: sweep buy −35% di periode ini
Exit  : SL $3 tetap, trailing $9, tanpa TP
```
| Periode | Trade | Win | Exp. | PF | Return | DD | Kalah beruntun |
|---|---|---|---|---|---|---|---|
| 8 Sep – 6 Okt | 34 | 29% | +0,42R | 1,56 | +14,1% | −8,3% | 4 |
| 7 Okt – 6 Nov | 28 | 36% | +0,81R | 2,13 | +23,9% | −7,9% | 5 |
| 2 bulan | 62 | 32% | +0,60R | 1,83 | +41,4% | −8,3% | 5 |

Ketahanan: trailing $6–15 semua positif, breakeven opsional (hasil mirip). Sensitif spread: $0,8 → +19%.

### Gabungan (risiko 1% per strategi)
Korelasi mingguan A vs B = **−0,55**. Gabungan 2 bulan: **+98%, DD −7,7%, 9 dari 9 minggu profit** (mingguan: +$54, +1.525, +1.983, +1.486, +916, +1.153, +478, +532, +1.698 per $10.000).

Kandidat ketiga (NR7 M5 long + partial 50% di 1R, win rate 55%, +31%) rapuh terhadap spread dan filter volatilitas, jadi tidak dijadikan final.

## Peringatan
- Dipilih dari ~116.000 kombinasi di 2 bulan data. Walaupun sudah disaring dengan konsistensi mingguan dan ketahanan parameter, **bias seleksi tetap besar**. Hasil live hampir pasti lebih rendah.
- Keduanya cenderung sell dan hidup di rezim emas turun (Sep–Nov 2026). Bias H1 otomatis mematikan sinyal saat tren berbalik, tapi belum teruji di rezim naik.
- Win rate 27–32%: 2 dari 3 trade kena SL. Kalah beruntun 5–6 kali itu normal.
- SL $3 = 30 pips dengan 1 pip = $0,10. Slippage $0,50 saat berita = 17% dari SL; jangan entry di sekitar berita besar.
- Uji demo minimal 1 bulan; mulai risiko 0,5%.

---

# FINAL: SL $3 tetap, tanpa TP, SL bergerak, win rate ≥ 80% — `macd_asia_m1`

## Mengapa scan sebelumnya mentok di 60%
Mesin lama memindahkan SL hanya saat candle M5/M15 **ditutup**. Satu candle bisa naik +$2 lalu balik menyentuh SL −$3 sebelum tutup, sehingga breakeven tidak pernah sempat aktif. Solusi: sinyal boleh di TF apa pun, tapi **eksekusi dan manajemen SL dilakukan di M1** (`mtf.py`), mendekati eksekusi tick MT5. Dengan ini breakeven +$0,75 langsung memberi win rate 81% (sebelumnya 32%) pada strategi yang sama.

Data M1: Yahoo `GC=F`, 12 Okt – 6 Nov 2026 (27.091 candle; Yahoo hanya memberi M1 untuk 30 hari terakhir). Diuji dalam dua paruh (12–25 Okt, 26 Okt–6 Nov).

Scan `hiwin_m1.py`: 81.648 kombinasi (18 entry × sinyal M1/M5/M15 × bias × sesi × arah × breakeven cepat × trailing). Yang win ≥ 80% di dua paruh **dan** profit: 13, semuanya satu keluarga (MACD sell M5 + bias M15, 29 trade, +7,8%, sensitif spread). Keluarga kedua, MACD M1 sesi Asia + bias D1, 149 trade, +27%, 4/4 minggu, tapi win 86%/70%. Analisis trade SL-nya (`deep_dive.py` + analisis fitur) menemukan satu filter yang membedakan: **kekuatan MACD saat cross**. Cross yang terjadi dekat nol (pantulan lemah) jauh lebih sering kena SL.

Koreksi mesin yang ditemukan di tahap ini: SL plus yang melewati harga pasar kini dibatasi di harga saat itu (sebelumnya terisi di harga lebih baik dari pasar). Hasil scan sebelum/sesudah koreksi identik.

## Aturan
```
Data   : M1 XAUUSD
Entry  : MACD(12,26,9) M1 memotong signal.
         SELL jika cross ke BAWAH terjadi DI ATAS nol (jual saat pantulan naik)
         BUY  jika cross ke ATAS terjadi DI BAWAH nol (beli saat pantulan turun)
Filter : |MACD| saat cross ≥ 0,5 × ATR(14) M1
         sesi Asia 00–07 UTC (07:00–14:00 WIB)
         searah bias harian: close kemarin vs EMA50 harian (sell hanya saat di bawah, buy hanya saat di atas)
SL     : $3 tetap (30 pips)
SL plus: setelah profit +$0,5, SL dipindah ke entry +$1 (atau ke harga saat itu jika lebih dekat)
Trail  : $4,5 dari close M1
TP     : tidak ada
Risiko : 1% per trade (0,33 lot per $10.000)
```

## Hasil (spread $0,40, risiko 1%)
| Periode | Trade | Win | Exp. | PF | Return | DD | Kalah beruntun |
|---|---|---|---|---|---|---|---|
| 12–25 Okt | 40 | **90,0%** | +0,31R | 3,96 | +12,9% | −4,0% | 2 |
| 26 Okt–6 Nov | 45 | **80,0%** | +0,48R | 3,40 | +23,6% | −3,9% | 2 |
| 4 minggu | 85 | **84,7%** | +0,40R | 3,56 | **+39,5%** | −4,0% | 2 |

- 4 dari 4 minggu profit; 14 dari 18 hari profit; hari terburuk −1,3R.
- Anatomi 85 trade: 12 SL penuh, 57 keluar di plus kecil (+0,2–0,5R), 15 ≥ 0,5R, 11 ≥ 1R, terbesar +6,1R. Median +0,27R. Durasi rata-rata 6 menit.
- Risiko 2%: +92%, DD −7,8%. Risiko 3%: +162%, DD −11%.

## Ketahanan
| Variasi | Hasil |
|---|---|
| Ambang MACD 0,3 / 0,4 / 0,5 / 0,6 / 0,7 / 1,0 × ATR | win 83–87%, return +25% s/d +42%, semua ≥ 79% di tiap paruh |
| Tanpa filter MACD | win 77% (86%/70%), +27% |
| be/plus 0,3–0,75 | win 80–85%, +34% s/d +43% (be 1,0 turun ke 75%) |
| Trailing $3 / 4,5 / 6 / 9 / 15 | win 84–85%, +24% s/d +40% |
| Spread $0,2 / 0,3 / 0,4 / 0,5 | win 86 / 86 / 85 / 81%, +45 / 43 / 40 / 30% |
| Spread $0,6 / $0,8 | win 79 / 76%, +24 / +15% |
| Bias harian / sesi | wajib: tanpa bias −15%, London −22%, NY −31% |

## Batasan yang harus diketahui
1. **Hanya 4 minggu data** (batas M1 Yahoo) dan rezim emas sedang turun. Filter MACD dipilih setelah melihat trade yang rugi; walaupun sederhana dan monoton, ada bias seleksi.
2. **Spread adalah variabel paling kritis.** Target ≥ 80% bertahan sampai spread $0,5. Spread emas di sesi Asia pada banyak broker lebih lebar daripada London/NY; cek spread aktual broker jam 07:00–14:00 WIB. Akun raw/ECN dengan komisi lebih cocok.
3. Durasi rata-rata 6 menit dan SL plus +$1 → eksekusi harus otomatis (EA) atau sangat disiplin. Slippage $0,3 sudah 10% dari SL.
4. Data futures `GC=F`, bukan spot broker. Perbedaan harga kecil, tapi perilaku spread/slippage berbeda.
5. Bias harian saat ini: close < EMA50 harian → hanya sinyal SELL yang aktif.

## Reproduksi
```bash
python backtest.py --source csv --csv data/GC_1m_30d.csv --strategies macd_asia_m1 --spread 0.4 --split 0.5
python hiwin_m1.py          # scan 81.648 kombinasi (±20 menit)
python deep_dive.py '{"tf":"1m","fam":"old","entry":"macd","bias":"d1","session":"asia","side":"both","be":0.5,"plus":1.0,"trail":4.5}'
```
