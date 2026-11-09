//+------------------------------------------------------------------+
//|                                              AsiaNR7Engulf.mq5   |
//|  EA untuk strategi `asia_nr7_engulf` (lihat RESEARCH.md bagian   |
//|  "Validasi independen & riset multi-periode").                   |
//|                                                                  |
//|  Aturan (semua jam dalam UTC, sesi Asia 00:00-07:00 UTC):        |
//|   1. NR7 M15: bar M15 sebelumnya range tersempit dari 7 bar,     |
//|      bar M15 yang baru selesai close > high-nya (BUY) atau       |
//|      close < low-nya (SELL). Arah harus searah bias H1           |
//|      (EMA20 vs EMA50 H1 dari bar H1 yang sudah selesai           |
//|      SEBELUM jam bar sinyal).                                    |
//|   2. Engulfing bullish M5 yang menelan bar merah yang menyentuh  |
//|      EMA20 M5, EMA20 > EMA50 M5, bias M15 naik (close M15 >      |
//|      EMA50 M15 dari bar M15 selesai sebelum bar sinyal). BUY.    |
//|   3. Satu posisi. Entry market di tick pertama bar M1 berikutnya.|
//|      SL tetap InpSL dolar, tanpa TP.                             |
//|   4. Breakeven: begitu ada bar M1 yang MENUTUP >= entry +        |
//|      InpBeTrigger, SL pindah ke entry + InpBePlus.               |
//|      JANGAN diubah ke pemicu sentuhan high/low: di riset itu     |
//|      menaikkan win rate tetapi membuat strategi rugi.            |
//|   5. Trailing: SL = close M1 - InpTrail (BUY) / + InpTrail       |
//|      (SELL), hanya bergerak searah posisi. Dicek tiap bar M1.    |
//|                                                                  |
//|  Pasang di chart XAUUSD timeframe M1. Data M1, M5, M15, H1       |
//|  harus tersedia (MT5 membangunnya dari M1).                      |
//+------------------------------------------------------------------+
#property copyright "Riset XAUUSD - asia_nr7_engulf"
#property version   "1.00"
#property description "SL tetap $4,5, tanpa TP, breakeven di close M1, trailing. Sesi Asia. Entry NR7 M15 + engulfing M5."

#include <Trade/Trade.mqh>

//--- input
input double InpRiskPercent     = 1.0;      // Risiko % ekuitas per trade
input double InpSL              = 4.5;      // SL tetap ($ per oz) - riset: 4,5
input double InpBeTrigger       = 0.75;     // Breakeven: close M1 >= entry + ini ($)
input double InpBePlus          = 0.60;     // Breakeven: SL pindah ke entry + ini ($)
input double InpTrail           = 18.0;     // Trailing dari close M1 ($)
input double InpMaxSpread       = 0.60;     // Spread maksimum saat entry ($); 0 = tidak dibatasi
input int    InpAsiaEndHourUTC  = 7;        // Sesi: jam UTC pembukaan bar sinyal < ini
input int    InpServerGMTOffset = -99;      // Offset jam server vs UTC (mis. 2 atau 3). -99 = otomatis (hanya live)
input bool   InpUseNR7          = true;     // Pakai entry NR7 M15 (BUY & SELL)
input bool   InpUseEngulf       = true;     // Pakai entry engulfing M5 (BUY)
input int    InpSlippagePoints  = 30;       // Deviasi maksimum order (point)
input long   InpMagic           = 20261108; // Magic number
input string InpComment         = "asia_nr7_engulf";

//--- global
CTrade   trade;
int      hEma20M5 = INVALID_HANDLE, hEma50M5 = INVALID_HANDLE, hEma50M15 = INVALID_HANDLE;
int      hEma20H1 = INVALID_HANDLE, hEma50H1 = INVALID_HANDLE;
datetime lastM1 = 0, lastM5 = 0, lastM15 = 0;
int      gmtOffsetSec = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   if(InpServerGMTOffset == -99)
   {
      if(MQLInfoInteger(MQL_TESTER))
      {
         Print("Di Strategy Tester offset server tidak bisa dideteksi otomatis. Isi InpServerGMTOffset (umumnya 2 atau 3).");
         return INIT_PARAMETERS_INCORRECT;
      }
      gmtOffsetSec = (int)MathRound((double)(TimeCurrent() - TimeGMT()) / 3600.0) * 3600;
   }
   else
      gmtOffsetSec = InpServerGMTOffset * 3600;
   PrintFormat("Offset server terhadap UTC: %+d jam. Sesi Asia = jam UTC 00..%02d = jam server %02d..%02d",
               gmtOffsetSec / 3600, InpAsiaEndHourUTC - 1, (gmtOffsetSec / 3600 + 24) % 24,
               (InpAsiaEndHourUTC - 1 + gmtOffsetSec / 3600 + 24) % 24);

   hEma20M5  = iMA(_Symbol, PERIOD_M5,  20, 0, MODE_EMA, PRICE_CLOSE);
   hEma50M5  = iMA(_Symbol, PERIOD_M5,  50, 0, MODE_EMA, PRICE_CLOSE);
   hEma50M15 = iMA(_Symbol, PERIOD_M15, 50, 0, MODE_EMA, PRICE_CLOSE);
   hEma20H1  = iMA(_Symbol, PERIOD_H1,  20, 0, MODE_EMA, PRICE_CLOSE);
   hEma50H1  = iMA(_Symbol, PERIOD_H1,  50, 0, MODE_EMA, PRICE_CLOSE);
   if(hEma20M5 == INVALID_HANDLE || hEma50M5 == INVALID_HANDLE || hEma50M15 == INVALID_HANDLE ||
      hEma20H1 == INVALID_HANDLE || hEma50H1 == INVALID_HANDLE)
   {
      Print("Gagal membuat indikator EMA");
      return INIT_FAILED;
   }
   lastM1 = iTime(_Symbol, PERIOD_M1, 0);
   lastM5 = iTime(_Symbol, PERIOD_M5, 0);
   lastM15 = iTime(_Symbol, PERIOD_M15, 0);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(hEma20M5); IndicatorRelease(hEma50M5); IndicatorRelease(hEma50M15);
   IndicatorRelease(hEma20H1); IndicatorRelease(hEma50H1);
}

//+------------------------------------------------------------------+
//| Nilai satu buffer indikator di shift tertentu                    |
//+------------------------------------------------------------------+
bool Ind(int handle, int shift, double &value)
{
   double buf[1];
   if(CopyBuffer(handle, 0, shift, 1, buf) != 1) return false;
   value = buf[0];
   return value != EMPTY_VALUE;
}

//+------------------------------------------------------------------+
//| Jam UTC dari waktu server                                        |
//+------------------------------------------------------------------+
int HourUTC(datetime serverTime)
{
   MqlDateTime dt;
   TimeToStruct(serverTime - gmtOffsetSec, dt);
   return dt.hour;
}

//+------------------------------------------------------------------+
//| Posisi EA ini di simbol ini                                      |
//+------------------------------------------------------------------+
bool FindPosition(ulong &ticket, long &type, double &openPrice, double &sl)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      ticket = t;
      type = PositionGetInteger(POSITION_TYPE);
      openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      sl = PositionGetDouble(POSITION_SL);
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Bias H1 untuk bar M15 yang dibuka pada barTime: hanya bar H1     |
//| yang selesai SEBELUM jam yang memuat barTime (sama dengan        |
//| htf_bias(..., "1h", 20, 50) di entry_scan.py).  +1 / -1 / 0      |
//+------------------------------------------------------------------+
int BiasH1(datetime barTime)
{
   int idx = iBarShift(_Symbol, PERIOD_H1, barTime, false);
   if(idx < 0) return 0;
   double e20, e50;
   if(!Ind(hEma20H1, idx + 1, e20) || !Ind(hEma50H1, idx + 1, e50)) return 0;
   if(e20 > e50) return 1;
   if(e20 < e50) return -1;
   return 0;
}

//+------------------------------------------------------------------+
//| Bias M15 untuk bar M5 yang dibuka pada barTime: close M15 vs     |
//| EMA50 M15 dari bar M15 yang selesai SEBELUM bar M15 pemuat.      |
//+------------------------------------------------------------------+
int BiasM15(datetime barTime)
{
   int idx = iBarShift(_Symbol, PERIOD_M15, barTime, false);
   if(idx < 0) return 0;
   double e50;
   if(!Ind(hEma50M15, idx + 1, e50)) return 0;
   double c = iClose(_Symbol, PERIOD_M15, idx + 1);
   if(c > e50) return 1;
   if(c < e50) return -1;
   return 0;
}

//+------------------------------------------------------------------+
//| Sinyal NR7 M15 dari bar M15 yang baru selesai (shift 1).         |
//| Mengembalikan +1 BUY, -1 SELL, 0 tidak ada.                      |
//+------------------------------------------------------------------+
int SignalNR7()
{
   if(Bars(_Symbol, PERIOD_M15) < 12) return 0;
   datetime t1 = iTime(_Symbol, PERIOD_M15, 1);
   if(HourUTC(t1) >= InpAsiaEndHourUTC) return 0;
   // bar shift 2 harus range tersempit dari 7 bar (shift 2..8)
   double r2 = iHigh(_Symbol, PERIOD_M15, 2) - iLow(_Symbol, PERIOD_M15, 2);
   for(int s = 3; s <= 8; s++)
   {
      double r = iHigh(_Symbol, PERIOD_M15, s) - iLow(_Symbol, PERIOD_M15, s);
      if(r < r2) return 0;
   }
   double c1 = iClose(_Symbol, PERIOD_M15, 1);
   int bias = BiasH1(t1);
   if(c1 > iHigh(_Symbol, PERIOD_M15, 2) && bias > 0) return 1;
   if(c1 < iLow(_Symbol, PERIOD_M15, 2) && bias < 0) return -1;
   return 0;
}

//+------------------------------------------------------------------+
//| Sinyal engulfing bullish M5 dari bar M5 yang baru selesai.       |
//+------------------------------------------------------------------+
int SignalEngulf()
{
   if(Bars(_Symbol, PERIOD_M5) < 60) return 0;
   datetime t1 = iTime(_Symbol, PERIOD_M5, 1);
   if(HourUTC(t1) >= InpAsiaEndHourUTC) return 0;
   double o1 = iOpen(_Symbol, PERIOD_M5, 1), c1 = iClose(_Symbol, PERIOD_M5, 1);
   double o2 = iOpen(_Symbol, PERIOD_M5, 2), c2 = iClose(_Symbol, PERIOD_M5, 2), l2 = iLow(_Symbol, PERIOD_M5, 2);
   if(!(c1 > o1 && c2 < o2 && c1 >= o2 && o1 <= c2)) return 0;   // bullish menelan bar merah sebelumnya
   double e20, e50;
   if(!Ind(hEma20M5, 1, e20) || !Ind(hEma50M5, 1, e50)) return 0;
   if(!(l2 <= e20 && e20 > e50)) return 0;                        // bar merah menyentuh EMA20, tren M5 naik
   if(BiasM15(t1) <= 0) return 0;
   return 1;
}

//+------------------------------------------------------------------+
//| Lot dari risiko % ekuitas dan jarak SL ($)                       |
//+------------------------------------------------------------------+
double LotsForRisk(double slDistance)
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskUsd = equity * InpRiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0 || slDistance <= 0) return 0;
   double lossPerLot = slDistance / tickSize * tickValue;
   double lots = riskUsd / lossPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step > 0) lots = MathFloor(lots / step) * step;
   if(lots < minLot) return 0;        // risiko minimum lebih besar dari yang diizinkan: jangan entry
   if(lots > maxLot) lots = maxLot;
   return NormalizeDouble(lots, 2);
}

//+------------------------------------------------------------------+
//| Buka posisi                                                      |
//+------------------------------------------------------------------+
void OpenPosition(int dir)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK), bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(InpMaxSpread > 0 && (ask - bid) > InpMaxSpread)
   {
      PrintFormat("Sinyal %s dilewati: spread %.2f > %.2f", dir > 0 ? "BUY" : "SELL", ask - bid, InpMaxSpread);
      return;
   }
   double stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(InpSL < stopsLevel)
   {
      PrintFormat("SL %.2f lebih kecil dari stops level broker %.2f", InpSL, stopsLevel);
      return;
   }
   double lots = LotsForRisk(InpSL);
   if(lots <= 0) { Print("Lot = 0 (ekuitas terlalu kecil untuk risiko ini)"); return; }
   bool ok;
   if(dir > 0)
      ok = trade.Buy(lots, _Symbol, 0.0, NormalizeDouble(ask - InpSL, _Digits), 0.0, InpComment);
   else
      ok = trade.Sell(lots, _Symbol, 0.0, NormalizeDouble(bid + InpSL, _Digits), 0.0, InpComment);
   if(!ok) PrintFormat("Order gagal: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
//| Manajemen SL di bar M1 baru, berdasarkan CLOSE bar M1 yang baru  |
//| selesai. Sama dengan langkah 2b run_backtest(): kandidat SL =    |
//| breakeven plus (kalau close >= entry + trigger) dan trailing;    |
//| SL hanya bergerak searah posisi.                                 |
//+------------------------------------------------------------------+
void ManagePosition(ulong ticket, long type, double openPrice, double sl)
{
   double close1 = iClose(_Symbol, PERIOD_M1, 1);
   double stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double newSL = sl;
   if(type == POSITION_TYPE_BUY)
   {
      double profit = close1 - openPrice;
      if(profit >= InpBeTrigger) newSL = MathMax(newSL, MathMin(openPrice + InpBePlus, close1));
      newSL = MathMax(newSL, close1 - InpTrail);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      newSL = MathMin(newSL, bid - stopsLevel - _Point);   // tidak boleh terlalu dekat harga sekarang
      if(newSL <= sl + _Point / 2) return;
   }
   else
   {
      double profit = openPrice - close1;
      if(profit >= InpBeTrigger) newSL = MathMin(newSL, MathMax(openPrice - InpBePlus, close1));
      newSL = MathMin(newSL, close1 + InpTrail);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      newSL = MathMax(newSL, ask + stopsLevel + _Point);
      if(newSL >= sl - _Point / 2) return;
   }
   if(!trade.PositionModify(ticket, NormalizeDouble(newSL, _Digits), 0.0))
      PrintFormat("Modifikasi SL gagal: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
void OnTick()
{
   datetime m1 = iTime(_Symbol, PERIOD_M1, 0);
   if(m1 == lastM1) return;            // hanya bekerja di tick pertama bar M1 baru
   lastM1 = m1;
   bool newM5 = false, newM15 = false;
   datetime m5 = iTime(_Symbol, PERIOD_M5, 0), m15 = iTime(_Symbol, PERIOD_M15, 0);
   if(m5 != lastM5)  { lastM5 = m5;   newM5 = true; }
   if(m15 != lastM15){ lastM15 = m15; newM15 = true; }

   ulong ticket; long type; double openPrice, sl;
   if(FindPosition(ticket, type, openPrice, sl))
   {
      ManagePosition(ticket, type, openPrice, sl);
      return;                          // satu posisi dalam satu waktu
   }
   int dir = 0;
   if(InpUseNR7 && newM15) dir = SignalNR7();        // NR7 diprioritaskan kalau keduanya muncul
   if(dir == 0 && InpUseEngulf && newM5) dir = SignalEngulf();
   if(dir != 0) OpenPosition(dir);
}
//+------------------------------------------------------------------+
