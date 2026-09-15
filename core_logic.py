import pandas as pd
import numpy as np

def calculate_fractals(df: pd.DataFrame, n: int = 2) -> pd.DataFrame:
    df = df.copy()
    df['swing_high'] = False
    df['swing_low'] = False

    for i in range(n, len(df) - n):
        is_high = all(df['high'].iloc[i] > df['high'].iloc[i - j] for j in range(1, n + 1)) and \
                  all(df['high'].iloc[i] > df['high'].iloc[i + j] for j in range(1, n + 1))
        is_low = all(df['low'].iloc[i] < df['low'].iloc[i - j] for j in range(1, n + 1)) and \
                 all(df['low'].iloc[i] < df['low'].iloc[i + j] for j in range(1, n + 1))

        if is_high: df.at[df.index[i], 'swing_high'] = True
        if is_low: df.at[df.index[i], 'swing_low'] = True
    return df

def detect_bos_transitions(df: pd.DataFrame, n: int = 2) -> list:
    df = calculate_fractals(df, n=n)
    active_swing_high = None
    active_swing_low = None
    bos_events = []

    for i in range(len(df)):
        current_time = df['time'].iloc[i]
        current_close = df['close'].iloc[i]

        if i >= n:
            p = i - n
            if df['swing_high'].iloc[p]: active_swing_high = df['high'].iloc[p]
            if df['swing_low'].iloc[p]: active_swing_low = df['low'].iloc[p]

        if active_swing_high is not None and current_close > active_swing_high:
            bos_events.append({"index": i, "time": current_time, "direction": "Bullish", "broken_level": active_swing_high})
            active_swing_high = None 
        if active_swing_low is not None and current_close < active_swing_low:
            bos_events.append({"index": i, "time": current_time, "direction": "Bearish", "broken_level": active_swing_low})
            active_swing_low = None 
    return bos_events

def determine_trend(df: pd.DataFrame, n: int = 2) -> dict:
    bos_events = detect_bos_transitions(df, n=n)
    if not bos_events:
        return {"direction": "None", "time": None, "price": None}
    latest = bos_events[-1]
    return {"direction": latest["direction"], "time": latest["time"], "price": latest["broken_level"]}

def find_rule_a_shape(df: pd.DataFrame, direction: str, lookback: int = 100, n: int = 2) -> dict:
    df = calculate_fractals(df, n=n)
    start_idx = max(n, len(df) - lookback)

    for i in range(len(df) - 1 - n, start_idx - 1, -1):
        if direction == "Bearish" and df['swing_high'].iloc[i]:
            pivot = df['high'].iloc[i]
            prior_highs = df.iloc[:i][df.iloc[:i]['swing_high']]
            prior_lows = df.iloc[:i][df.iloc[:i]['swing_low']]
            if not prior_highs.empty and not prior_lows.empty:
                b_high, b_low = prior_highs['high'].iloc[-1], prior_lows['low'].iloc[-1]
                if b_low <= pivot <= b_high:
                    return {"matched": True, "rule_name": "Key level in range", "time": df['time'].iloc[i], "price": pivot, "shape": "A", "bound_low": b_low, "bound_high": b_high}
        elif direction == "Bullish" and df['swing_low'].iloc[i]:
            pivot = df['low'].iloc[i]
            prior_highs = df.iloc[:i][df.iloc[:i]['swing_high']]
            prior_lows = df.iloc[:i][df.iloc[:i]['swing_low']]
            if not prior_highs.empty and not prior_lows.empty:
                b_high, b_low = prior_highs['high'].iloc[-1], prior_lows['low'].iloc[-1]
                if b_low <= pivot <= b_high:
                    return {"matched": True, "rule_name": "Key level in range", "time": df['time'].iloc[i], "price": pivot, "shape": "V", "bound_low": b_low, "bound_high": b_high}
    return {"matched": False}

def find_rule_b_sweep(df: pd.DataFrame, direction: str, lookback: int = 100) -> dict:
    start_idx = max(1, len(df) - lookback)
    for i in range(len(df) - 1, start_idx - 1, -1):
        curr, prev = df.iloc[i], df.iloc[i - 1]
        if direction == "Bearish" and curr['high'] > prev['high'] and curr['close'] < prev['high']:
            return {"matched": True, "rule_name": "Previous candle sweep", "time": curr['time'], "price": curr['high'], "swept_level": prev['high']}
        elif direction == "Bullish" and curr['low'] < prev['low'] and curr['close'] > prev['low']:
            return {"matched": True, "rule_name": "Previous candle sweep", "time": curr['time'], "price": curr['low'], "swept_level": prev['low']}
    return {"matched": False}

def find_rule_c_oc_level(df: pd.DataFrame, direction: str, lookback: int = 100, tolerance_pct: float = 0.0005) -> dict:
    start_idx = max(1, len(df) - lookback)
    for j in range(len(df) - 1, start_idx - 1, -1):
        test_candle = df.iloc[j]
        for k in range(j - 2, -1, -1):
            c1, c2 = df.iloc[k], df.iloc[k + 1]
            ref_level = (c1['close'] + c2['open']) / 2.0
            if ref_level > 0 and (abs(c1['close'] - c2['open']) / ref_level) <= tolerance_pct:
                if direction == "Bearish" and test_candle['high'] >= ref_level and test_candle['close'] < ref_level:
                    return {"matched": True, "rule_name": "OC key level", "time": test_candle['time'], "price": ref_level, "level_set_time": c1['time']}
                elif direction == "Bullish" and test_candle['low'] <= ref_level and test_candle['close'] > ref_level:
                    return {"matched": True, "rule_name": "OC key level", "time": test_candle['time'], "price": ref_level, "level_set_time": c1['time']}
    return {"matched": False}

def find_qualifying_rejection(df: pd.DataFrame, direction: str, lookback: int, n: int, tolerance_pct: float) -> dict:
    for func in [find_rule_a_shape, find_rule_b_sweep]:
        res = func(df, direction, lookback=lookback, n=n) if 'n' in func.__code__.co_varnames else func(df, direction, lookback=lookback)
        if res["matched"]: return res
    res = find_rule_c_oc_level(df, direction, lookback=lookback, tolerance_pct=tolerance_pct)
    if res["matched"]: return res
    return {"matched": False}

def check_ltf_confirmation(ltf_df: pd.DataFrame, direction: str, reject_time: pd.Timestamp, today_boundary: pd.Timestamp, n: int = 2) -> dict:
    for event in detect_bos_transitions(ltf_df, n=n):
        # 1. BOS must be in the correct direction
        # 2. Freshness check: BOS must happen on or after the current boundary
        # 3. Sequence check: BOS must happen on or after the rejection occurred
        if event["direction"] == direction and event["time"] >= today_boundary and event["time"] >= reject_time:
            return {
                "confirmed": True, 
                "bos_time": event["time"], 
                "bos_price": event["broken_level"]
            }
            
    return {"confirmed": False}

def check_modifiers(df: pd.DataFrame, direction: str) -> dict:
    if len(df) < 2: return {"upgrade": False, "warning": False}
    today, yesterday = df.iloc[-1], df.iloc[-2]
    
    if direction == "Bullish":
        return {
            "upgrade": today['low'] < yesterday['low'] and today['close'] > yesterday['low'],
            "warning": today['high'] > yesterday['high']
        }
    else:
        return {
            "upgrade": today['high'] > yesterday['high'] and today['close'] < yesterday['high'],
            "warning": today['low'] < yesterday['low']
        }