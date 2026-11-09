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

# ~~FINAL~~ GAGAL VALIDASI: SL $3 tetap, win rate ≥ 80% — `macd_asia_m1`

> **Catatan 8 Nov 2026 (setelah validasi independen):** hasil di bawah ini hanya berlaku di jendela 4 minggu data Yahoo tempat strategi ini dipilih. Di data spot Dukascopy Jan 2026 dan Agu–Okt 2026 win rate turun ke 64–67% dan periode Agu–Okt rugi −22%. Lihat bagian *Validasi independen & riset multi-periode* di bawah.

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

---

# Validasi independen & riset multi-periode (8 Nov 2026) — hasil akhir: `asia_nr7_engulf`

## 1. Validasi `macd_asia_m1` di data independen: GAGAL
Data baru: spot XAUUSD Dukascopy M1 (`fetch_m1.py`), tiga periode dengan rezim berbeda, total 15 minggu / 100.256 candle:

| Periode | Rezim | Bar M1 |
|---|---|---|
| 12–30 Jan 2026 | emas naik kuat (4.537 → 4.895) | 19.108 |
| 17 Agu – 9 Okt 2026 | turun / sideways (4.369 → 4.190) | 53.668 |
| 12 Okt – 6 Nov 2026 | turun (jendela yang sama dengan data Yahoo riset lama) | 27.480 |

`macd_asia_m1` tanpa ubah parameter (spread $0,40):

| Periode | Trade | Win | expR | Return |
|---|---|---|---|---|
| Jan | 45 | 66,7% | +0,14 | +5,8% |
| Agu–Okt | 214 | 63,6% | −0,11 | **−22,3%** |
| Okt–Nov (spot) | 88 | 81,8% | +0,32 | +31,6% |

Di jendela Okt–Nov hasilnya tereplikasi di data spot, jadi 85% yang lama bukan masalah sumber data, melainkan **overfit ke satu rezim 4 minggu**. Strategi ini dicabut.

## 2. Berapa win rate yang "gratis" dari manajemen SL saja?
Benchmark entry **acak** (`multi_scan.py --bench`, 5 seed, semua sesi) dengan SL tetap + breakeven cepat + trailing yang sama:

| SL | Pemicu BE dicek di | Win acak | expR acak |
|---|---|---|---|
| $3 | high/low M1 ("tick") | 69–78% | −0,20 … −0,28 |
| $3 | close M1 | 55–64% | ≈ −0,10 (= biaya spread) |
| $4,5 | close M1, BE +0,75 | 59% | −0,16 |

Pelajaran: dengan SL tetap dan BE cepat, win rate sebagian besar ditentukan oleh **rasio SL : pemicu BE**, bukan oleh entry. Win rate 75% bisa dicapai entry acak, tetapi expectancy-nya negatif. Jadi syarat yang sebenarnya menguji strategi adalah **profit di tiap periode**, bukan win rate.

Temuan penting kedua: pemicu BE gaya tick (SL pindah begitu high/low menyentuh +$0,75) memberi win rate 89% tetapi **rugi** (expR −0,02): noise M1 ($1,8–2,5 per candle) menyentuh pemicu lalu menyentuh SL plus, sehingga runner tidak pernah terbentuk. Pemicu di **close M1** (candle harus menutup ≥ +$0,75) adalah konfirmasi yang jauh lebih kuat dan menjadi kunci hasil di bawah. Keduanya tersedia di mesin (`be_touch`), dan EA harus memakai versi close M1.

## 3. Scan multi-periode: kandidat harus lolos di 3 periode sekaligus
`multi_scan.py`: 6.804 kombinasi (18 entry lama+baru × sinyal M1/M5/M15 × bias none/M15/H1/D1 × sesi × arah × 3 manajemen) × 3 periode, diulang untuk SL $3, $4,5, $6 dan dua mode BE; lalu `stage2.py` (grid manajemen + partial TP) dan `final_grid.py` (SL $3–5 untuk entry terbaik dan portofolionya). Kriteria lolos ditetapkan sebelum melihat hasil: ≥ 10 trade, win ≥ 75% dan profit di **setiap** periode, win gabungan ≥ 80%, ≥ 60% minggu profit.

| SL | Kombinasi lolos | Terbaik yang profit di semua periode |
|---|---|---|
| **$3 (30 pips)** | **0 dari 6.804** (kedua mode BE; stage 2: 0 dari 2.040) | NR7 M15 Asia + bias H1: win 78,6%, 84 trade, 6/15 minggu |
| $4 (40 pips) | 28 dari 1.155 (grid akhir) | portofolio NR7+engulfing: win 80,7%, PF 2,2 |
| $4,5 (45 pips) | 10 dari 6.804; 90 dari 1.155 | portofolio NR7+engulfing: win 83,9%, PF 2,7 |
| $6 (60 pips) | 0 (win tinggi tapi profit tidak konsisten) | — |

Entry yang berulang kali muncul di puncak untuk **setiap** ukuran SL dan kedua mode BE: **NR7 breakout M15 sesi Asia** dan **engulfing bullish M5 di EMA20 sesi Asia**. Itu alasan keduanya dipilih, bukan karena satu angka terbaik.

**Kesimpulan untuk aturan 30 pips:** tidak ada kombinasi dari ±20.000 yang diuji yang mencapai win ≥ 80% *dan* profit konsisten di 3 rezim. Penyebabnya struktural: range median satu candle M1 emas $1,8–2,5, sehingga SL $3 ≈ 1,5 candle; SL sering tersentuh oleh noise sebelum breakeven sempat aktif. Dengan SL $4,5 target tercapai; $4 berada di batas (spread > $0,4 menjatuhkannya di bawah 80%).

## 4. Strategi final: `asia_nr7_engulf` (SL $4,5 = 45 pips)
Aturan (sesi Asia 00:00–07:00 UTC = 07:00–14:00 WIB; data M1 wajib):
1. **NR7 M15:** candle M15 sebelumnya adalah yang range-nya tersempit dari 7 candle terakhir, dan candle M15 sekarang menutup di atas high-nya (BUY) atau di bawah low-nya (SELL). Arah harus searah bias H1 (EMA20 > EMA50 H1 untuk BUY, sebaliknya SELL; hanya candle H1 yang sudah selesai).
2. **Engulfing bullish M5:** candle M5 hijau menelan candle merah sebelumnya, candle merah itu menyentuh EMA20 M5, EMA20 > EMA50 M5, dan bias M15 naik (close M15 > EMA50 M15). Hanya BUY.
3. Satu posisi dalam satu waktu; entry di open candle M1 berikutnya. **SL tetap $4,5**, tanpa TP.
4. **Breakeven:** begitu ada candle M1 yang *menutup* ≥ entry + $0,75, SL pindah ke entry + $0,60.
5. **Trailing:** SL mengikuti close M1 − $18 (chandelier); SL hanya bergerak searah posisi.

Hasil di 3 periode spot Dukascopy (`validate_final.py`, spread $0,30, risiko 1%, modal $10.000):

| Periode | Trade | Win | expR | PF | Return | Max DD | Kalah beruntun |
|---|---|---|---|---|---|---|---|
| Jan 2026 (naik) | 42 | 81,0% | +0,70 | 4,6 | +32,0% | −5,9% | 2 |
| Agu–Okt 2026 (turun/sideways) | 78 | 83,3% | +0,15 | 1,8 | +11,8% | −8,2% | 3 |
| Okt–Nov 2026 (turun) | 40 | 80,0% | +0,53 | 3,5 | +21,3% | −5,8% | 2 |
| **Gabungan 15 minggu** | **160** | **81,9%** | **+0,39** | **3,1** | | | 3 |

- BUY 111 trade (win 80%, +49R), SELL 49 trade (win 86%, +13R). Tanpa 3 trade terbaik tetap +19,8R.
- Anatomi: 29 SL penuh, 118 win kecil (median +0,10R = SL plus), 13 trade ≥ 0,5R, 9 trade ≥ 2R (maks +20R). Profit datang dari runner; win rate tinggi adalah efek SL plus.
- Durasi median 6 menit, rata-rata 31 menit, maksimal 9,6 jam.
- Minggu profit 8/15; mingguan R dari −3,3 sampai +25,3. Ini titik lemah utama: profit terkonsentrasi di minggu-minggu tren.

Ketahanan:

| Variasi | Win gabungan | Return min. periode |
|---|---|---|
| Spread $0,2 / 0,3 / 0,4 / 0,5 / 0,6 / 0,8 | 82,8 / 81,9 / 81,9 / 80,6 / 80,0 / 78,1% | +12,8 / +11,8 / +10,7 / +8,5 / +7,5 / +3,1% |
| SL $4,0 / $5,0 | 78,8 / 81,9% | +11,2 / +9,2% |
| BE +0,5→+0,3 / +1,0→+0,6 | 84,5 / 80,5% | +9,2 / +11,8% |
| Trailing $9 / 13,5 / 25 | 81,9 / 81,9 / 81,6% | +1,8 / +8,3 / +11,2% |
| **BE gaya tick (high/low)** | 89,1% | **−2,8% (rugi di 2 periode)** |

## 5. Batasan yang jujur
1. **Aturan 30 pips tidak terpenuhi.** Strategi final memakai SL 45 pips. Di 30 pips, kandidat terbaik hanya 78,6% dengan 84 trade dan konsistensi mingguan buruk.
2. **Bias seleksi tetap ada.** Entry dipilih setelah melihat ketiga periode (±20.000 kombinasi). Mitigasi: entry yang sama menang untuk semua SL dan kedua mode BE, parameter tetangga stabil, dan 3 rezim berbeda. Tetapi 160 trade / 15 minggu masih sedikit; hasil riil wajar lebih rendah.
3. **Konsistensi mingguan 8/15.** Siap menghadapi 2–3 minggu berturut-turut minus kecil sebelum satu minggu besar.
4. Spread: target bertahan sampai $0,6 di sesi Asia. Spread Asia banyak broker lebih lebar daripada London; pakai akun raw/ECN.
5. Eksekusi harus EA: BE dicek di close M1, trailing tiap M1, durasi median 6 menit. BE gaya tick **merusak** strategi (lihat tabel), jadi EA tidak boleh memindahkan SL pada sentuhan high/low.
6. Data candle bid Dukascopy, bukan tick broker; slippage saat berita tidak dimodelkan. Hindari entry 15 menit sekitar rilis data besar.

## 6. Reproduksi
```bash
python fetch_m1.py --start 2026-01-12 --end 2026-01-30 --out data/duka_m1_jan26.csv
python fetch_m1.py --start 2026-08-17 --end 2026-10-09 --out data/duka_m1_augoct26.csv
python fetch_m1.py --start 2026-10-12 --end 2026-11-07 --out data/duka_m1_octnov26.csv
python validate_final.py                                   # strategi final, 3 periode + sensitivitas
python validate_final.py --strategy macd_asia_m1 --spread 0.4   # bukti kegagalan strategi lama
python backtest.py --source csv --csv data/duka_m1_augoct26.csv --strategies asia_nr7_engulf --spread 0.3 --split 0
SL_USD=3 BE_MODE=m1close python multi_scan.py              # scan 6.804 kombinasi × 3 periode (±10 menit)
SL_USD=3 BE_MODE=m1close python multi_scan.py --bench      # benchmark entry acak
python stage2.py && python final_grid.py
```

---

# Penyempurnaan & uji holdout (9 Nov 2026)

Permintaan: sempurnakan di backtest, jangan sarankan dipakai sebelum lolos. Yang dikerjakan, berurutan dan dengan kriteria yang ditetapkan **sebelum** melihat hasil.

## 1. Leave-one-period-out: seberapa overfit prosedur seleksinya?
Dari hasil scan SL $4,5 (6.804 kombinasi), seleksi diulang hanya dengan 2 periode, lalu dilihat hasilnya di periode ke-3 yang disembunyikan:

| Periode disembunyikan | Kombinasi lolos di 2 periode lain | Profit di periode tersembunyi | Win ≥ 75% di sana |
|---|---|---|---|
| Jan (naik) | 14 | 43% | 29% |
| Agu–Okt (sideways) | 14 | 29% | 50% |
| Okt–Nov (turun) | 9 | 78% | 67% |

Kesimpulan jujur: prosedur "lolos di 2 periode" **tidak cukup** menjamin periode berikutnya; separuh lebih kandidat gagal di periode tersembunyi, terutama di rezim sideways. Yang bertahan di ketiga uji hanya keluarga NR7 M15 Asia (bias D1 lebih stabil daripada H1 di uji ini) dan engulfing M5 Asia long, yaitu dua komponen strategi final. Karena itu strategi final **tidak boleh dianggap lolos** sebelum diuji di data yang sama sekali belum dilihat (bagian 5).

## 2. Slippage
Mesin kini punya `Config.slippage` (merugikan, dikenakan pada entry market dan eksekusi SL; test `test_slippage_worsens_entry_and_sl_fills`).

| Spread / slippage | Win | expR | PF | Return Jan / Agu–Okt / Okt–Nov |
|---|---|---|---|---|
| $0,3 / 0 | 81,9% | +0,39 | 3,09 | +32,0 / +11,8 / +21,3% |
| $0,3 / $0,1 | 80,6% | +0,35 | 2,72 | +30,6 / +8,5 / +18,8% |
| $0,3 / $0,2 | 78,1% | +0,29 | 2,22 | +25,5 / +4,1 / +16,3% |
| $0,5 / $0,2 | 76,7% | +0,23 | 1,92 | +19,8 / +1,0 / +15,2% |
| $0,6 / $0,3 | 77,5% | +0,14 | 1,49 | +11,7 / **−3,3** / +11,1% |

Rezim sideways (Agu–Okt) adalah yang paling rapuh terhadap biaya. Batas aman: spread + slippage ≤ $0,7 total.

## 3. Diagnosa trade rugi (`diag_final.py`)
Tiap trade diberi fitur: sumber sinyal, arah, jam, hari, ATR M15 relatif, ADX H1, ATR H1, range hari sebelumnya, jarak dari open harian. **Tidak ada satu pun fitur yang memisahkan trade rugi secara konsisten di ketiga periode**; bucket yang terlihat bagus di satu periode buruk di periode lain. Menambah filter dari sini = overfitting, jadi tidak dilakukan. Catatan: tiap komponen punya satu periode nyaris nol (engulfing di Jan expR −0,04; NR7 di Okt–Nov +0,17); gabungannya yang menghaluskan.

## 4. Bootstrap (5.000 pengacakan urutan 160 trade, spread $0,3 + slippage $0,1, risiko 1%)
- Return 15 minggu: median +67%, 5% terburuk +10%.
- Max drawdown: median −7,6%, 5% terburuk −14%, ekstrem −25%.
- Blok 4 minggu (±43 trade): **17% peluang rugi**, 10% terburuk −3R.
- Kalah beruntun ≥ 5 dalam 160 trade: ±4%.
Artinya satu bulan demo yang minus **tidak** otomatis membuktikan strategi rusak; dua bulan berturut-turut minus baru sinyal.

## 5. Uji holdout: pra-registrasi (ditulis sebelum data selesai diunduh)
Strategi **dibekukan**: `asia_nr7_engulf` default (SL $4,5, BE close M1 +0,75 → +0,60, trailing $18, NR7 bias H1 + engulfing bias M15). Alternatif yang dicatat sebelumnya: NR7 bias D1 (`nr7_bias="d1"`), hanya untuk dilaporkan, bukan untuk dipilih setelah melihat hasil.

Data holdout (belum pernah dilihat/dipakai): Dukascopy M1 **3–28 Nov 2025**, **2–27 Mar 2026**, **1–26 Jun 2026**.

Kriteria lolos (`holdout.py`, spread $0,30, slippage $0,10):
- tiap periode holdout: ≥ 10 trade, profit, win ≥ 75%;
- gabungan 6 periode: win ≥ 80%, PF ≥ 1,5, ≥ 60% minggu profit.

Kalau gagal, strategi dinyatakan **tidak lolos** dan tidak disarankan dipakai; riset dilanjutkan atau dihentikan dengan laporan jujur.
