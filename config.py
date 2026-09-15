import os
from dotenv import load_dotenv
import MetaTrader5 as mt5

load_dotenv()

TERMINAL_PATH = os.getenv("DERIV_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5 Deriv\terminal64.exe")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

SYMBOLS = [
    "Volatility 10 Index", "Volatility 25 Index", "Volatility 50 Index", 
    "Volatility 75 Index", "Volatility 100 Index", "Volatility 75 (1s) Index",
    "Boom 500 Index", "Boom 1000 Index", "Crash 500 Index", "Crash 1000 Index", 
    "Step Index", "Jump 75 Index"
]

# Timeframes: Strictly D1 -> H4
TIMEFRAME_HTF = mt5.TIMEFRAME_D1
TIMEFRAME_LTF = mt5.TIMEFRAME_H4

FRACTAL_WINDOW = 2          
DAILY_LOOKBACK = 100        
CANDLE_COUNT_HTF = 250      
CANDLE_COUNT_LTF = 500      
OC_TOLERANCE_PCT = 0.0005   
ALERT_HISTORY_FILE = "alert_history.json"
SCAN_INTERVAL_SECONDS = 60