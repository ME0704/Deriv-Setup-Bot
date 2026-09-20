import time
from datetime import datetime
import pandas as pd
import MetaTrader5 as mt5  # Added this import at the top
import config
import mt5_layer
import core_logic
from alerts import AlertManager

def run_scan_cycle(alert_mgr: AlertManager, verified_symbols: list):
    print(f"\n[SCAN] Checking {len(verified_symbols)} symbols (D1->H4)...")

    for symbol in verified_symbols:
        # 1. Fetch the data FIRST
        daily_df = mt5_layer.get_closed_candles(symbol, config.TIMEFRAME_HTF, config.CANDLE_COUNT_HTF)
        h4_df = mt5_layer.get_closed_candles(symbol, config.TIMEFRAME_LTF, config.CANDLE_COUNT_LTF)

        if daily_df.empty or h4_df.empty or len(daily_df) < 50:
            continue

        # --- THE FIX: STRICTLY TODAY'S BOUNDARY ---
        today_boundary = daily_df.iloc[-1]['time'] + pd.Timedelta(days=1)

        # 2. RUN DIAGNOSTIC ONCE DATA IS FETCHED
        # if "Boom 1000" in symbol:
        #     print(f"\n--- DIAGNOSTIC: {symbol} ---")
        #     print(f"Daily closed candles fetched: {len(daily_df)}")
        #     print(f"H4 closed candles fetched: {len(h4_df)}")
            
        #     for direction in ["Bullish", "Bearish"]:
        #         rejection = core_logic.find_qualifying_rejection(
        #             daily_df, direction, config.DAILY_LOOKBACK, config.FRACTAL_WINDOW, config.OC_TOLERANCE_PCT
        #         )
        #         print(f"[{direction}] D1 Rejection Matched: {rejection['matched']}")
                
        #         if rejection["matched"]:
        #             confirmation = core_logic.check_ltf_confirmation(
        #                 h4_df, direction, rejection["time"], today_boundary, config.FRACTAL_WINDOW
        #             )
        #             print(f"[{direction}] 4H BOS Confirmed: {confirmation['confirmed']}")

        # 3. CONTINUE NORMAL SCAN
        trend_info = core_logic.determine_trend(daily_df, n=config.FRACTAL_WINDOW)
        daily_trend = trend_info["direction"]
        
        valid_setups = []

        for direction in ["Bullish", "Bearish"]:
            rejection = core_logic.find_qualifying_rejection(
                daily_df, direction, config.DAILY_LOOKBACK, config.FRACTAL_WINDOW, config.OC_TOLERANCE_PCT
            )
            if not rejection["matched"]: continue

            confirmation = core_logic.check_ltf_confirmation(
                h4_df, direction, rejection["time"], today_boundary, config.FRACTAL_WINDOW
            )
            
            if confirmation["confirmed"]:
                live_rates = mt5.copy_rates_from_pos(symbol, config.TIMEFRAME_HTF, 0, 2)
                live_daily_df = pd.DataFrame(live_rates)
                modifiers = core_logic.check_modifiers(live_daily_df, direction)

                valid_setups.append({
                    "direction": direction,
                    "rejection": rejection,
                    "confirmation": confirmation,
                    "modifiers": modifiers
                })

        if not valid_setups:
            continue

        valid_setups.sort(key=lambda x: x["confirmation"]["bos_time"], reverse=True)
        best_setup = valid_setups[0]

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
    alert_mgr = AlertManager(config.ALERT_HISTORY_FILE, config.TELEGRAM_BOT_TOKEN)

    try:
        while True:
            run_scan_cycle(alert_mgr, verified_symbols)
            time.sleep(config.SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping bot...")
    finally:
        mt5_layer.shutdown_mt5()

def get_latest_4h_candle_time():
    """Fetches the exact open time of the currently forming 4H candle directly from the Deriv broker."""
    # Using Volatility 75 Index as a reliable 24/7 benchmark for the broker's internal clock
    rates = mt5.copy_rates_from_pos("Volatility 75 Index", mt5.TIMEFRAME_H4, 0, 1)
    if rates is not None and len(rates) > 0:
        return rates[0]['time']
    return 0

if __name__ == "__main__":
    print("[SYSTEM] MS Synthetics connected to MT5.")
    
    # 1. Run an initial scan immediately on boot so you don't have to wait for the next 4H boundary
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Executing initial boot scan...")
    
    # -> CALL YOUR MAIN SCAN FUNCTION HERE
    main() 
    
    # 2. Record the broker's currently forming 4H candle
    last_known_4h_candle = get_latest_4h_candle_time()
    print("[SYSTEM] 24/7 Scheduler Active. Monitoring broker 4H boundaries...")

    # 3. Enter the 24/7 Loop
    while True:
        # Check the MT5 terminal every 60 seconds
        time.sleep(60)
        
        current_4h_candle = get_latest_4h_candle_time()
        
        # If the broker has opened a new 4H candle, the previous one just officially closed!
        if current_4h_candle > last_known_4h_candle:
            print(f"\n[!] 4H Boundary Crossed at {datetime.now().strftime('%H:%M:%S')}. Initiating Scan...")
            
            # -> CALL YOUR MAIN SCAN FUNCTION HERE AGAIN
            main()
            
            # Update the tracker to wait for the next 4-hour cycle
            last_known_4h_candle = current_4h_candle