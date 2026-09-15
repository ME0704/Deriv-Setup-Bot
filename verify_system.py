import pandas as pd
import numpy as np
import core_logic
import alerts

def generate_synthetic_data() -> pd.DataFrame:
    """Generates a controlled synthetic series of 20 daily candles."""
    dates = pd.date_range("2025-01-01", periods=20, freq="D")
    base_prices = [100, 102, 105, 103, 101, 98, 95, 96, 99, 102, 106, 108, 107, 104, 100, 101, 105, 107, 106, 105]
    df = pd.DataFrame({
        "time": dates,
        "open": base_prices,
        "high": [p + 2.0 for p in base_prices],
        "low": [p - 2.0 for p in base_prices],
        "close": [p + 0.5 for p in base_prices]
    })
    return df

def test_fractals_and_bos():
    df = generate_synthetic_data()
    df_fractals = core_logic.calculate_fractals(df, n=2)
    assert 'swing_high' in df_fractals.columns
    assert 'swing_low' in df_fractals.columns

    bos_events = core_logic.detect_bos_transitions(df, n=2)
    assert isinstance(bos_events, list)
    print("[PASS] calculate_fractals and detect_bos_transitions validated.")

def test_rule_b_sweep():
    dates = pd.date_range("2025-01-01", periods=3, freq="D")
    # Day 2 sweeps Day 1 high and closes below Day 1 high
    df = pd.DataFrame({
        "time": dates,
        "open": [100, 104, 100],
        "high": [105, 108, 102],
        "low": [98, 99, 97],
        "close": [102, 103, 101]
    })
    res = core_logic.find_rule_b_sweep(df, "Bearish", lookback=3)
    assert res["matched"] is True
    assert res["rule"] == "Rule B (Sweep)"
    print("[PASS] find_rule_b_sweep Bearish sweep validated.")

def test_deduplication():
    manager = alerts.AlertManager("test_history.json", "dummy_token", "dummy_chat")
    h1 = manager.generate_event_id("V75", "Bullish", "Rule B", "2025-01-01", "2025-01-02")
    h2 = manager.generate_event_id("V75", "Bullish", "Rule B", "2025-01-01", "2025-01-02")
    assert h1 == h2
    if os.path.exists("test_history.json"):
        os.remove("test_history.json")
    print("[PASS] AlertManager event hash deduplication validated.")

if __name__ == "__main__":
    import os
    print("Running system verification checks...")
    test_fractals_and_bos()
    test_rule_b_sweep()
    test_deduplication()
    print("=" * 50)
    print("ALL MODULE VERIFICATION CHECKS PASSED SUCCESSFULLY.")
    print("=" * 50)