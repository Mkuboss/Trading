# EA `AsiaNR7Engulf.mq5`

Implementasi MQL5 dari strategi `asia_nr7_engulf` (`backtest.py`), hasil riset di `RESEARCH.md`.

> **STATUS (9 Nov 2026): BELUM LOLOS.** Strategi ini gagal uji holdout (rugi di Mar 2026 dan Jun 2026, lihat RESEARCH.md). EA ini disimpan sebagai referensi implementasi, **jangan dipakai** di akun apa pun sampai RESEARCH.md menyatakan lolos.
Belum dikompilasi di lingkungan riset (tidak ada MetaEditor di Linux); kompilasi di MetaEditor dulu, perbaiki
peringatan kalau ada, lalu bandingkan hasil Strategy Tester dengan `validate_final.py` sebelum dipakai.

## Pemasangan
1. Salin `AsiaNR7Engulf.mq5` ke `MQL5/Experts/`, buka di MetaEditor, tekan **Compile**.
2. Pasang di chart **XAUUSD, timeframe M1**. Pastikan histori M1 cukup (minimal beberapa minggu) agar EMA50 H1 terisi.
3. Isi `InpServerGMTOffset` sesuai jam server broker terhadap UTC (banyak broker GMT+2 musim dingin / GMT+3 musim panas;
   lihat selisih jam di Market Watch dengan jam UTC). Di live boleh `-99` (otomatis); di Strategy Tester **wajib** diisi.
4. Akun raw/ECN. Spread Asia harus ≤ $0,6 (input `InpMaxSpread` menolak entry kalau lebih lebar).

## Pengaturan Strategy Tester supaya setara backtest
- Simbol XAUUSD, timeframe **M1**, mode **"1 minute OHLC"** (paling setara dengan mesin riset) atau "Every tick based on real ticks".
- Deposit 10.000, leverage ≥ 1:100, periode uji yang sama dengan riset: 12–30 Jan 2026, 17 Agu–9 Okt 2026, 12 Okt–6 Nov 2026.
- Hasil yang diharapkan (data Dukascopy, spread $0,3): sekitar 160 trade, win ≈ 82%, PF ≈ 3. Perbedaan beberapa trade wajar
  karena data broker, inisialisasi EMA, dan spread berbeda. Kalau win rate jauh di bawah 75% atau hasil minus di ketiga periode,
  ada yang tidak cocok (biasanya offset jam server) dan EA jangan dipakai dulu.

## Pemetaan ke backtest
| Backtest (`backtest.py` / `mtf.py`) | EA |
|---|---|
| Sinyal di close bar M15/M5, entry di open M1 berikutnya | Dihitung di tick pertama bar M1 baru dari bar HTF shift 1, order market |
| `sl = 4.5` dari harga fill (ask untuk BUY) | `trade.Buy(..., sl = ask - InpSL)` |
| BE: `profit = close_M1 - entry >= 0.75` → SL = `entry + 0.6` | `ManagePosition()` memakai `iClose(M1, 1)` |
| Trailing `close_M1 - 18`, hanya naik | `MathMax(sl, close1 - InpTrail)` |
| Bias H1 = EMA20/EMA50 H1 bar yang selesai sebelum jam bar sinyal | `BiasH1()`: shift `iBarShift(H1, t) + 1` |
| Bias M15 = close M15 > EMA50 M15 bar sebelum bar M15 pemuat | `BiasM15()`: shift `iBarShift(M15, t) + 1` |
| Sesi: jam UTC pembukaan bar sinyal < 7 | `HourUTC(iTime(TF, 1)) < InpAsiaEndHourUTC` |
| Satu posisi, sinyal diabaikan saat ada posisi | `FindPosition()` lalu `return` |

Yang **tidak** boleh diubah tanpa riset ulang: pemicu breakeven harus dari **close** M1. Versi yang memindahkan SL saat
high/low menyentuh +$0,75 memberi win rate 89% tetapi rugi di 2 dari 3 periode (`validate_final.py`, baris `be_mode: tick`).
