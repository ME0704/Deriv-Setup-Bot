import sys
import argparse
import config
import mt5_layer
import core_logic

def run_diagnostic(symbol: str):
    print("=" * 60)
    print(f"DIAGNOSTIC TRACE FOR: {symbol}")
    print("=" * 60)

    if not mt5_layer.init_deriv_mt5(config.TERMINAL_PATH):
        sys.exit(1)

    daily_df = mt5_layer.get_closed_candles(symbol, config.TIMEFRAME_HTF, config.CANDLE_COUNT_HTF)
    h4_df = mt5_layer.get_closed_candles(symbol, config.TIMEFRAME_LTF, config.CANDLE_COUNT_LTF)

    mt5_layer.shutdown_mt5()

    if daily_df.empty or h4_df.empty:
        print(f"[ERROR] Could not fetch candle data for {symbol}.")
        return

    print(f"Candles loaded -> Daily: {len(daily_df)}, 4H: {len(h4_df)}")
    print(f"Latest Daily Closed Candle: {daily_df['time'].iloc[-1]}")
    print(f"Latest 4H Closed Candle:    {h4_df['time'].iloc[-1]}")

    # Step 1: Daily Trend
    trend_info = core_logic.determine_trend(daily_df, n=config.FRACTAL_WINDOW)
    print("\n--- STEP 1: DAILY TREND (Informational Only) ---")
    print(f"Trend Direction: {trend_info['direction']} | Level: {trend_info['price']} | Time: {trend_info['time']}")

    # Steps 2 & 3: Test Both Directions Independently
    for direction in ["Bullish", "Bearish"]:
        print(f"\n--- TESTING {direction.upper()} SETUP ---")

        # Step 2 Rejections
        rule_a = core_logic.find_rule_a_shape(daily_df, direction, lookback=config.DAILY_LOOKBACK, n=config.FRACTAL_WINDOW)
        rule_b = core_logic.find_rule_b_sweep(daily_df, direction, lookback=config.DAILY_LOOKBACK)
        rule_c = core_logic.find_rule_c_oc_level(daily_df, direction, lookback=config.DAILY_LOOKBACK, tolerance_pct=config.OC_TOLERANCE_PCT)

        print(f"Rule A (Shape):    {rule_a}")
        print(f"Rule B (Sweep):    {rule_b}")
        print(f"Rule C (OC-Level): {rule_c}")

        rejection = core_logic.find_qualifying_rejection(daily_df, direction, lookback=config.DAILY_LOOKBACK, n=config.FRACTAL_WINDOW)

        if not rejection["matched"]:
            print(f"[RESULT] No qualifying {direction} rejection found in last {config.DAILY_LOOKBACK} days.")
            continue

        print(f"[QUALIFIED] Matched {rejection['rule']} at price {rejection['price']} on {rejection['time']}")

        # Step 3 Confirmation
        confirmation = core_logic.check_ltf_confirmation(h4_df, direction, rejection['time'], n=config.FRACTAL_WINDOW)
        print(f"--- STEP 3: 4H BOS CONFIRMATION ---")
        print(f"Confirmation Result: {confirmation}")

        # Steps 4 & 5
        modifiers = core_logic.check_modifiers(daily_df, direction)
        print(f"Modifiers -> Grade A+ Upgrade: {modifiers['upgrade']} | Adverse Warning: {modifiers['warning']}")

        if confirmation["confirmed"]:
            print(f"\n>>> [FINAL VERDICT]: SETUP IS ACTIVE AND MEETS ALL ALERT CRITERIA! <<<")
        else:
            print(f"\n>>> [FINAL VERDICT]: Setup blocked. Rejection found, but NO 4H BOS occurred on or after {rejection['time']}. <<<")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deriv Symbol Diagnostics")
    parser.add_argument("--symbol", type=str, default="Volatility 75 Index", help="Exact symbol name to diagnose")
    args = parser.parse_args()
    run_diagnostic(args.symbol)