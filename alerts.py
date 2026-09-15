import os
import json
import hashlib
import requests
from datetime import datetime, timezone, timedelta

class AlertManager:
    def __init__(self, history_file: str, bot_token: str, chat_id: str):
        self.history_file = history_file
        self.bot_token = bot_token
        self.chat_id = chat_id
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

    def generate_event_id(self, symbol: str, direction: str, reject_time: str, bos_time: str) -> str:
        raw_key = f"{symbol}|D1H4|{direction}|{reject_time}|{bos_time}"
        return hashlib.md5(raw_key.encode('utf-8')).hexdigest()

    def send_alert(self, symbol: str, direction: str, rule_data: dict, 
                   bos_data: dict, htf_trend: str, upgrade: bool, warning: bool) -> bool:
        
        reject_time = rule_data['time']
        bos_time = bos_data['bos_time']
        
        event_id = self.generate_event_id(symbol, direction, str(reject_time), str(bos_time))
        if event_id in self.history:
            return False 

        reject_str = reject_time.strftime("%A, %Y-%m-%d, %H:%M")
        bos_str = bos_time.strftime("%A, %Y-%m-%d, %H:%M")

        if htf_trend == direction:
            alignment = "Aligned"
        elif htf_trend == "None":
            alignment = "No Daily trend established yet"
        else:
            alignment = "Not aligned (counter-trend)"

        if rule_data["rule_name"] == "Key level in range":
            formed_date = reject_time.strftime("%Y-%m-%d")
            dynamic_str = f"{direction.upper()} rejection at {rule_data['shape']}-shape @ {rule_data['price']:.4f} (formed {formed_date}), inside the BOS range {rule_data['bound_low']:.4f}, {rule_data['bound_high']:.4f}."
        elif rule_data["rule_name"] == "Previous candle sweep":
            formed_date = reject_time.strftime("%Y-%m-%d")
            dynamic_str = f"{direction.upper()} rejection at {rule_data['price']:.4f} (formed {formed_date}), after sweeping {rule_data['swept_level']:.4f}."
        else:
            set_date = rule_data['level_set_time'].strftime("%Y-%m-%d")
            dynamic_str = f"{direction.upper()} rejection at OC-shape @ {rule_data['price']:.4f} (level set {set_date}, rejected {reject_time.strftime('%Y-%m-%d')})."

        msg = f"{'🟢▲ BUY' if direction == 'Bullish' else '🔴▼ SELL'} · {symbol} · D1→H4\n"
        msg += "External breakout confirmed\n\n"
        
        msg += f"Rule           : {rule_data['rule_name']}\n"
        msg += f"Trend Alignment: {alignment}\n"
        msg += f"Rejection      : {reject_str}\n"
        msg += f"External BO    : {bos_str}\n"
        msg += f"Level          : {bos_data['bos_price']:.4f}\n\n"
        
        msg += f"{dynamic_str}\n\n"

        if upgrade:
            msg += "🔥 Liquidity sweep confirmed (A+)\n"
        if warning:
            msg += "⚠️ Previous day's HIGH/LOW was already swept before this setup — use confirmation entry, not a blind limit order.\n"
            
        msg += "\n⚠️ Not an entry signal. Bias only — wait for your entry model.\n\n"

        eat_time = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        msg += f"Sent {eat_time} EAT"

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": msg}

        try:
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                self.history.add(event_id)
                self._save_history() 
                print(f"[ALERT SENT] {symbol} {direction} (D1->H4)")
                return True
        except Exception as e:
            print(f"[ERROR] Alert failed: {e}")

        return False