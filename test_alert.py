import alerts

# 1. Create a mock institutional alert message
sample_message = (
    "▲ BUY · EURUSD · D1→H4\n"
    "External breakout confirmed\n\n"
    "Rule           : Key level in range\n"
    "Trend Alignment: Aligned\n"
    "Rejection      : Friday, 18 Sep 00:00 EAT\n"
    "External BO    : Friday, 18 Sep 16:00 EAT\n"
    "Level          : 1.08950\n\n"
    "BUY rejection at V-shape @ 1.08500 (formed 2026-09-18), inside the BOS range [1.08200, 1.09100].\n\n"
    "Liquidity sweep confirmed (A+)\n\n"
    "⚠️ [WEEKEND TEST BROADCAST] ⚠️\n"
    "This is a sample alert verifying server delivery across all active accounts.\n\n"
    "Sent just now EAT"
)

# 2. Choose the pair to test (make sure your users have this pair selected in subscriptions.json)
TARGET_SYMBOL = "EURUSD"

print("=" * 60)
print(f"[TEST RUN] Broadcasting sample alert for asset: {TARGET_SYMBOL}")
print("=" * 60)

# 3. Trigger the alert dispatcher
responses = alerts.send_telegram_alert(sample_message, symbol=TARGET_SYMBOL)

print("=" * 60)
print(f"[RESULT] Successfully delivered to {len(responses)} Telegram account(s)!")
print("=" * 60)