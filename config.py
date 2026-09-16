import os
from dotenv import load_dotenv
import MetaTrader5 as mt5

load_dotenv()

# Setup Paths & Credentials
TERMINAL_PATH = os.getenv("DERIV_TERMINAL_PATH", r"C:\Program Files\MetaTrader 5 Deriv\terminal64.exe")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")

# Deriv Synthetic Instruments
SYMBOLS = [
    "Volatility 5 Index", "Volatility 5 (1s) Index", "Volatility 10 Index","Volatility 10 (1s) Index", "Volatility 15 Index", "Volatility 15 (1s) Index", 
    "Volatility 25 Index", "Volatility 25 (1s) Index", "Volatility 30 Index", "Volatility 30 (1s) Index", "Volatility 50 Index", "Volatility 50 (1s) Index", 
    "Volatility 75 Index", "Volatility 75 (1s) Index", "Volatility 90 Index", "Volatility 90 (1s) Index", "Volatility 100 Index", "Volatility 100 (1s) Index",
    "Volatility 150 (1s) index", "Volatility 250 (1s) index",
    "Boom 500 Index", "Boom 1000 Index", "Crash 500 Index", "Crash 1000 Index", 
    "Step Index", "Jump 10 Index","Jump 25 Index", "Jump 50 Index", "Jump 75 Index", "Jump 100 Index",
]

TIMEFRAME_HTF = mt5.TIMEFRAME_D1
TIMEFRAME_LTF = mt5.TIMEFRAME_H4

FRACTAL_WINDOW = 2          
DAILY_LOOKBACK = 100        
CANDLE_COUNT_HTF = 250      
CANDLE_COUNT_LTF = 500      
OC_TOLERANCE_PCT = 0.0005   
SCAN_INTERVAL_SECONDS = 60  

# Local Databases
ALERT_HISTORY_FILE = "alert_history.json"
SUBSCRIPTIONS_FILE = "subscriptions.json"
USERS_DB = "users.json"   # Tracks user expiration dates
KEYS_DB = "keys.json"     # Tracks generated activation codes