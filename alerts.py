import os
import json
import hashlib
import requests
from datetime import datetime, timezone, timedelta
import config

class AlertManager:
    def __init__(self, history_file: str, bot_token: str):
        self.history_file = history_file
        self.bot_token = bot_token
        self.history = self._load_history()

    def _load_history(self) -> set:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return set(json.load(f))
            except Exception:
                return set()
        return set()

    def _save_history(self):
        try:
            with open(self.history_file, 'w') as f:
                json.dump(list(self.history), f)
        except Exception as e:
            print(f"[ERROR] Failed to save alert history: {e}")

    def _get_subscribers_for_symbol(self, symbol: str) -> list:
            """Returns a list of ACTIVE chat IDs subscribed to this specific symbol."""
            if not os.path.exists(config.SUBSCRIPTIONS_FILE):
                return []
                
            try:
                with open(config.SUBSCRIPTIONS_FILE, 'r') as f:
                    subs = json.load(f)
                    
                # Load the users database to verify expiration dates
                valid_users = []
                if os.path.exists(config.USERS_DB):
                    with open(config.USERS_DB, 'r') as f:
                        users_db = json.load(f)
                        for user_id, user_data in users_db.items():
                            if "expiry" in user_data:
                                expiry = datetime.fromisoformat(user_data["expiry"])
                                # Add timezon-naive current time check
                                if datetime.now() < expiry:
                                    valid_users.append(user_id)
                                    
                # Admin always gets alerts regardless of expiration
                if config.ADMIN_CHAT_ID not in valid_users and config.ADMIN_CHAT_ID:
                    valid_users.append(config.ADMIN_CHAT_ID)
                    
                # Return only users who are both Subscribed to the symbol AND have an active license
                return [chat_id for chat_id, pairs in subs.items() if symbol in pairs and chat_id in valid_users]
                
            except Exception as e:
                print(f"[ERROR] Reading subscriptions: {e}")
                return []

    def generate_event_id(self, symbol: str, direction: str, reject_time: str, bos_time: str) -> str:
        raw_key = f"{symbol}|D1H4|{direction}|{reject_time}|{bos_time}"
        return hashlib.md5(raw_key.encode('utf-8')).hexdigest()

    def send_alert(self, symbol: str, direction: str, rule_data: dict, 
                   bos_data: dict, htf_trend: str, upgrade: bool, warning: bool) -> bool:
        
        # 1. Fetch exactly who wants this alert
        subscribers = self._get_subscribers_for_symbol(symbol)
        if not subscribers:
            return False 

        reject_time = rule_data['time']
        bos_time = bos_data['bos_time']
        
        event_id = self.generate_event_id(symbol, direction, str(reject_time), str(bos_time))
        if event_id in self.history:
            return False 

        is_bullish = direction.lower() == "bullish"
        header_icon = "🟢" if is_bullish else "🔴"
        side = "BUY" if is_bullish else "SELL"

        # Determine exact key level rejection shape & type with formed date
        shape = rule_data.get('shape', 'V')
        formed_date_str = reject_time.strftime("%a %d %b")  # e.g., Wed 26 Aug

        if rule_data["rule_name"] == "Key level in range":
            rej_type = f"{shape}-shape KL · Formed {formed_date_str}"
        elif rule_data["rule_name"] == "Previous candle sweep":
            rej_type = f"{shape}-shape KL (Liquidity Sweep) · Formed {formed_date_str}"
        else:
            rej_type = f"OC Level · Formed {formed_date_str}"

        # Trend alignment badge
        if htf_trend == direction:
            trend_badge = "Aligned ✅"
        elif htf_trend == "None":
            trend_badge = "None established"
        else:
            trend_badge = "Counter-Trend ⚠️"

        bos_str = bos_time.strftime("%a %d %b, %H:%M EAT")
        clean_symbol = symbol.replace(" Index", "")

        # Format price cleanly
        rej_price = f"{rule_data['price']:.2f}" if rule_data['price'] >= 100 else f"{rule_data['price']:.4f}"
        bos_price = f"{bos_data['bos_price']:.2f}" if bos_data['bos_price'] >= 100 else f"{bos_data['bos_price']:.4f}"

        # Construct the streamlined alert
        lines = [
            f"{header_icon} {side} BIAS · {clean_symbol} [D1 ➔ H4]",
            "",
            f"🎯 D1 Rejection: {rej_price} ({rej_type})",
            f"⚡ 4H External BOS: {bos_price} at {bos_str}",
            f"📊 Daily Trend: {trend_badge}",
        ]

        if upgrade:
            lines.append("\n🔥 Grade A+ (Liquidity sweep confirmed)")

        if warning:
            adverse_level = "High" if is_bullish else "Low"
            lines.append(f"\n⚠️ Warning: Previous Daily {adverse_level} has been taken. Use confirmation entry.")

        lines += [
            "",
            "⏳ Bias only. Execute via your own model."
        ]

        msg = "\n".join(lines)

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        any_success = False

        # 2. Dispatch to subscribers
        for chat_id in subscribers:
            payload = {
                "chat_id": chat_id, 
                "text": msg,
                "parse_mode": "Markdown",
                "protect_content": False
            }
            try:
                res = requests.post(url, json=payload, timeout=10)
                if res.status_code == 200:
                    any_success = True
            except Exception as e:
                print(f"[ERROR] Failed sending to {chat_id}: {e}")

        if any_success:
            self.history.add(event_id)
            self._save_history() 
            print(f"[ALERT SENT] {symbol} {direction} to {len(subscribers)} subscribers.")
            return True

        return False