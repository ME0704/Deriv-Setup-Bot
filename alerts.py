import os
import json
import hashlib
import requests
from datetime import datetime, timezone, timedelta
import config

class AlertManager:
    def __init__(self, history_file: str, bot_token: str):
        # Notice we removed chat_id from the initialization
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
        """Returns a list of chat IDs subscribed to this specific symbol."""
        if not os.path.exists(config.SUBSCRIPTIONS_FILE):
            return []
        try:
            with open(config.SUBSCRIPTIONS_FILE, 'r') as f:
                subs = json.load(f)
            # Find all users where the symbol is in their opted-in list
            return [chat_id for chat_id, pairs in subs.items() if symbol in pairs]
        except Exception:
            return []

    def generate_event_id(self, symbol: str, direction: str, reject_time: str, bos_time: str) -> str:
        raw_key = f"{symbol}|D1H4|{direction}|{reject_time}|{bos_time}"
        return hashlib.md5(raw_key.encode('utf-8')).hexdigest()

    def send_alert(self, symbol: str, direction: str, rule_data: dict, 
                   bos_data: dict, htf_trend: str, upgrade: bool, warning: bool) -> bool:
        
        # 1. Fetch exactly who wants this alert
        subscribers = self._get_subscribers_for_symbol(symbol)
        if not subscribers:
            # If nobody is subscribed to Step Index, quietly skip sending.
            return False 

        reject_time = rule_data['time']
        bos_time = bos_data['bos_time']
        
        event_id = self.generate_event_id(symbol, direction, str(reject_time), str(bos_time))
        if event_id in self.history:
            return False 

        bos_str = bos_time.strftime("%A, %Y-%m-%d %H:%M")
        reject_date_str = reject_time.strftime("%Y-%m-%d")

        if htf_trend == direction:
            alignment = "Aligned"
        elif htf_trend == "None":
            alignment = "No Daily trend established yet"
        else:
            alignment = "Counter-trend (Not aligned)"

        if rule_data["rule_name"] == "Key level in range":
            dynamic_str = f"The Daily timeframe formed a {rule_data['shape']}-shape rejection at {rule_data['price']:.4f} on {reject_date_str}. This occurred safely inside the structural boundaries of {rule_data['bound_low']:.4f} and {rule_data['bound_high']:.4f}."
        elif rule_data["rule_name"] == "Previous candle sweep":
            dynamic_str = f"The Daily timeframe swept liquidity at {rule_data['swept_level']:.4f} and aggressively rejected from {rule_data['price']:.4f} on {reject_date_str}."
        else:
            set_date = rule_data['level_set_time'].strftime("%Y-%m-%d")
            dynamic_str = f"Price returned to an untested open/close (OC) level established on {set_date}, rejecting perfectly at {rule_data['price']:.4f} on {reject_date_str}."
        
        dynamic_str += " The setup was officially triggered by a fresh 4H Break of Structure."

        msg = f"*{direction.upper()} BIAS CONFIRMED*\n"
        msg += f"*Asset:* {symbol} (D1 -> H4)\n"
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        msg += "*[ SYNTHESIS ]*\n"
        msg += f"{dynamic_str}\n\n"
        
        msg += "*[ DATA POINTS ]*\n"
        msg += f"• *Primary Rule:* {rule_data['rule_name']}\n"
        msg += f"• *Daily Trend:* {alignment}\n"
        msg += f"• *Break Level:* {bos_data['bos_price']:.4f}\n"
        msg += f"• *Break Time:* {bos_str}\n\n"
        
        if upgrade or warning:
            msg += "*[ MODIFIERS ]*\n"
            if upgrade:
                msg += "**+ GRADE A+:** Favorable liquidity sweep confirmed.\n"
            if warning:
                msg += "**- WARNING:** Previous extreme was compromised. Use confirmation entry.\n"
            msg += "\n"

        msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += "_Note: This is a directional bias, not an execution signal. Apply your entry model._\n"

        eat_time = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        msg += f"Sent: {eat_time} EAT"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        any_success = False

        # 2. Loop through only the users who subscribed to this pair
        for chat_id in subscribers:
            payload = {
                "chat_id": chat_id, 
                "text": msg,
                "parse_mode": "Markdown"
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