import time
import config
import mt5_layer
import core_logic
from alerts import AlertManager

def run_scan_cycle(alert_mgr: AlertManager, verified_symbols: list):
    print(f"\n[SCAN] Checking {len(verified_symbols)} symbols (D1->H4)...")

    for symbol in verified_symbols:
        daily_df = mt5_layer.get_closed_candles(symbol, config.TIMEFRAME_HTF, config.CANDLE_COUNT_HTF)
        h4_df = mt5_layer.get_closed_candles(symbol, config.TIMEFRAME_LTF, config.CANDLE_COUNT_LTF)

        if daily_df.empty or h4_df.empty or len(daily_df) < 50:
            continue

        # Extract Daily Trend
        trend_info = core_logic.determine_trend(daily_df, n=config.FRACTAL_WINDOW)
        daily_trend = trend_info["direction"]
        
        # FRESHNESS BOUNDARY: The open time of the most recent closed Daily candle
        today_boundary = daily_df.iloc[-1]['time']

        valid_setups = []

        for direction in ["Bullish", "Bearish"]:
            # Step 2: Find Rejection on Daily
            rejection = core_logic.find_qualifying_rejection(
                daily_df, direction, config.DAILY_LOOKBACK, config.FRACTAL_WINDOW, config.OC_TOLERANCE_PCT
            )
            if not rejection["matched"]: continue

            # Step 3: Confirm 4H BOS happens ON or AFTER today's open
            confirmation = core_logic.check_ltf_confirmation(
                h4_df, direction, rejection["time"], today_boundary, config.FRACTAL_WINDOW
            )
            
            if confirmation["confirmed"]:
                modifiers = core_logic.check_modifiers(daily_df, direction)
                valid_setups.append({
                    "direction": direction,
                    "rejection": rejection,
                    "confirmation": confirmation,
                    "modifiers": modifiers
                })

        if not valid_setups:
            continue

        # Conflict Resolution: Only one bias per cycle. Pick newest BOS.
        valid_setups.sort(key=lambda x: x["confirmation"]["bos_time"], reverse=True)
        best_setup = valid_setups[0]

        # Tie-breaker: If both sides broke structure on the exact same 4H candle, side with Daily trend
        if len(valid_setups) > 1 and valid_setups[0]["confirmation"]["bos_time"] == valid_setups[1]["confirmation"]["bos_time"]:
            if valid_setups[1]["direction"] == daily_trend:
                best_setup = valid_setups[1]

        alert_mgr.send_alert(
            symbol=symbol,
            direction=best_setup["direction"],
            rule_data=best_setup["rejection"],
            bos_data=best_setup["confirmation"],
            htf_trend=daily_trend,
            upgrade=best_setup["modifiers"]["upgrade"],
            warning=best_setup["modifiers"]["warning"]
        )

def main():
    print("Starting AI Trading Bot (D1->H4 Mode)...")
    if not mt5_layer.init_deriv_mt5(config.TERMINAL_PATH):
        return

    verified_symbols = mt5_layer.verify_market_watch_symbols(config.SYMBOLS)
    alert_mgr = AlertManager(config.ALERT_HISTORY_FILE, config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)

    try:
        while True:
            run_scan_cycle(alert_mgr, verified_symbols)
            time.sleep(config.SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping bot...")
    finally:
        mt5_layer.shutdown_mt5()

if __name__ == "__main__":
    main()