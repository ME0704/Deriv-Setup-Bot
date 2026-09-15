import MetaTrader5 as mt5
import pandas as pd

def init_deriv_mt5(terminal_path: str) -> bool:
    """Initializes connection to Deriv MT5 using the exact executable path."""
    if not mt5.initialize(path=terminal_path):
        print(f"[ERROR] MT5 Initialization failed: {mt5.last_error()}")
        return False
    print(f"[OK] Connected to Deriv MT5: {terminal_path}")
    return True

def shutdown_mt5():
    """Shuts down MT5 session."""
    mt5.shutdown()

def verify_market_watch_symbols(symbols: list) -> list:
    """Verifies and returns symbols that exist in Deriv MT5's Market Watch."""
    valid_symbols = []
    for s in symbols:
        info = mt5.symbol_info(s)
        if info is not None:
            if not info.visible:
                mt5.symbol_select(s, True)
            valid_symbols.append(s)
        else:
            print(f"[WARN] Symbol '{s}' not found on broker. Check exact Market Watch name.")
    return valid_symbols

def get_closed_candles(symbol: str, timeframe: int, count: int) -> pd.DataFrame:
    """
    Fetches completed candles.
    Starts at position 1 to exclude the live, currently forming candle 0.
    """
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 1, count)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df