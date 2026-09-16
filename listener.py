import os
import json
import time
import secrets
from datetime import datetime, timedelta
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import config

bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN)

# In-memory buffer to hold user pair selections before saving
user_drafts = {}

# --- PAYMENT & CONTACT CONFIGURATION ---
ADMIN_TELEGRAM_USERNAME = "emmas_wrld"  # Without '@'
MOBILE_MONEY_DETAILS = "MTN / Airtel: +256 704 598 003 (Name: Modi Emmanuel)"
USDT_TRC20_WALLET = "TXyvwzguyBrRR8JbREhXxWgjEgQzTwLTG6"  # Replace with your actual TRC20 address

# --- DATABASE HELPERS ---
def load_json(filepath: str) -> dict:
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json(filepath: str, data: dict):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=4)

def check_access(chat_id: str) -> bool:
    """Checks if a user has an active, unexpired subscription."""
    if chat_id == config.ADMIN_CHAT_ID:
        return True
        
    users = load_json(config.USERS_DB)
    if chat_id not in users:
        return False
        
    expiry_str = users[chat_id].get("expiry")
    if not expiry_str:
        return False
        
    expiry_date = datetime.fromisoformat(expiry_str)
    return datetime.now() < expiry_date

def get_expiry_date_str(chat_id: str) -> str:
    """Returns formatted expiration date or Inactive."""
    if chat_id == config.ADMIN_CHAT_ID:
        return "Lifetime (Admin Access)"
    users = load_json(config.USERS_DB)
    if chat_id in users and users[chat_id].get("expiry"):
        expiry_date = datetime.fromisoformat(users[chat_id]["expiry"])
        if datetime.now() < expiry_date:
            return expiry_date.strftime("%Y-%m-%d %H:%M EAT")
    return "No active subscription"

# --- KEYBOARDS ---

def build_main_menu_keyboard(has_access: bool) -> InlineKeyboardMarkup:
    """Main navigation menu with interactive buttons."""
    markup = InlineKeyboardMarkup()
    
    if has_access:
        markup.row(
            InlineKeyboardButton("Configure Pairs", callback_data="nav_pairs"),
            InlineKeyboardButton("My Account", callback_data="nav_account")
        )
    else:
        markup.row(
            InlineKeyboardButton("Plans & Pricing", callback_data="nav_plans"),
            InlineKeyboardButton("Payment Methods", callback_data="nav_payment_methods")
        )
        markup.row(
            InlineKeyboardButton("Enter License Key", callback_data="nav_enter_key"),
            InlineKeyboardButton("My Status", callback_data="nav_account")
        )
        markup.add(
            InlineKeyboardButton("Send Receipt / Contact", url=f"https://t.me/{ADMIN_TELEGRAM_USERNAME}")
        )
        
    return markup

def build_pairs_keyboard(chat_id: str) -> InlineKeyboardMarkup:
    """2-column market selection grid."""
    selected_set = user_drafts.get(chat_id, set())
    markup = InlineKeyboardMarkup()
    
    for i in range(0, len(config.SYMBOLS), 2):
        row = []
        for j in range(2):
            if i + j < len(config.SYMBOLS):
                sym = config.SYMBOLS[i + j]
                icon = "✓" if sym in selected_set else "✕"
                label = f"{icon}  {sym.replace(' Index', '')}"
                row.append(InlineKeyboardButton(text=label, callback_data=f"tog_{i+j}"))
        markup.row(*row)
        
    markup.row(
        InlineKeyboardButton("Select All", callback_data="act_select_all"),
        InlineKeyboardButton("Clear All", callback_data="act_clear_all")
    )
    markup.add(InlineKeyboardButton("Save Selection", callback_data="act_save"))
    markup.add(InlineKeyboardButton("Back to Dashboard", callback_data="nav_home"))
    return markup

# --- ADMIN COMMAND: GENERATE KEYS ---
@bot.message_handler(commands=['genkey'])
def generate_key(message):
    chat_id = str(message.chat.id)
    if chat_id != config.ADMIN_CHAT_ID:
        return

    try:
        parts = message.text.split()
        days = int(parts[1]) if len(parts) > 1 else 30
    except ValueError:
        bot.reply_to(message, "Usage: `/genkey <days>`\nExample: `/genkey 30`", parse_mode="Markdown")
        return

    new_key = secrets.token_hex(4).upper()
    keys_db = load_json(config.KEYS_DB)
    keys_db[new_key] = {"days": days, "used": False, "used_by": None}
    save_json(config.KEYS_DB, keys_db)
    
    bot.reply_to(
        message, 
        f"*LICENSE KEY GENERATED*\n\nKey: `{new_key}`\nDuration: `{days} Days`\n\nForward this code to the user.",
        parse_mode="Markdown"
    )

# --- USER COMMAND: ACTIVATE KEY ---
@bot.message_handler(commands=['activate'])
def activate_account(message):
    chat_id = str(message.chat.id)
    parts = message.text.split()
    
    if len(parts) < 2:
        bot.send_message(chat_id, "Please include your license key:\n`/activate YOUR_CODE`", parse_mode="Markdown")
        return
        
    process_key_activation(chat_id, parts[1].strip().upper())

def process_key_activation(chat_id: str, entered_key: str):
    keys_db = load_json(config.KEYS_DB)
    
    if entered_key not in keys_db:
        bot.send_message(chat_id, "Invalid activation key. Please verify with admin.")
        return
        
    if keys_db[entered_key]["used"]:
        bot.send_message(chat_id, "This license key has already been redeemed.")
        return

    days_to_add = keys_db[entered_key]["days"]
    users = load_json(config.USERS_DB)
    current_expiry = datetime.now()
    
    if chat_id in users and users[chat_id].get("expiry"):
        old_expiry = datetime.fromisoformat(users[chat_id]["expiry"])
        if old_expiry > current_expiry:
            current_expiry = old_expiry
            
    new_expiry = current_expiry + timedelta(days=days_to_add)
    users[chat_id] = {"expiry": new_expiry.isoformat()}
    save_json(config.USERS_DB, users)
    
    keys_db[entered_key]["used"] = True
    keys_db[entered_key]["used_by"] = chat_id
    save_json(config.KEYS_DB, keys_db)
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Configure Active Pairs", callback_data="nav_pairs"))
    
    bot.send_message(
        chat_id,
        f"*ACCESS GRANTED*\n\n"
        f"Your license has been activated.\n"
        f"• Duration: `{days_to_add} Days`\n"
        f"• Valid Until: `{new_expiry.strftime('%Y-%m-%d %H:%M EAT')}`\n\n"
        f"Tap below to choose your instruments.",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# --- CORE ROUTING ---

@bot.message_handler(func=lambda message: message.chat.type != 'private')
def auto_leave_groups(message):
    try:
        bot.leave_chat(message.chat.id)
    except Exception:
        pass

@bot.message_handler(commands=['start', 'menu'])
def show_dashboard(message):
    if message.chat.type != 'private':
        return
    chat_id = str(message.chat.id)
    is_active = check_access(chat_id)
    status_text = "ACTIVE" if is_active else "INACTIVE / EXPIRED"
    
    text = (
        "*SYNTHETIC INDICES ALERT SYSTEM*\n"
        "Algorithmic structure & liquidity bias (D1 → H4).\n\n"
        f"• Account Status: `{status_text}`\n"
        f"• Valid Until: `{get_expiry_date_str(chat_id)}`\n\n"
        "Select an option below:"
    )
    bot.send_message(chat_id, text, reply_markup=build_main_menu_keyboard(is_active), parse_mode="Markdown")

@bot.message_handler(commands=['pairs'])
def open_pairs_menu(message):
    if message.chat.type != 'private':
        return
    chat_id = str(message.chat.id)
    if not check_access(chat_id):
        show_dashboard(message)
        return

    subs = load_json(config.SUBSCRIPTIONS_FILE)
    user_drafts[chat_id] = set(subs.get(chat_id, []))
    
    bot.send_message(
        chat_id,
        "*INSTRUMENT CONFIGURATION*\nSelect indices to monitor:\n\nTap items to toggle, then press *Save Selection*.",
        reply_markup=build_pairs_keyboard(chat_id),
        parse_mode="Markdown"
    )

# --- NAVIGATION CALLBACK HANDLERS ---

@bot.callback_query_handler(func=lambda call: call.data == "nav_home")
def callback_home(call):
    chat_id = str(call.message.chat.id)
    is_active = check_access(chat_id)
    status_text = "ACTIVE" if is_active else "INACTIVE / EXPIRED"
    
    text = (
        "*SYNTHETIC INDICES ALERT SYSTEM*\n"
        "Algorithmic structure & liquidity bias (D1 → H4).\n\n"
        f"• Account Status: `{status_text}`\n"
        f"• Valid Until: `{get_expiry_date_str(chat_id)}`\n\n"
        "Select an option below:"
    )
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=build_main_menu_keyboard(is_active), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "nav_plans")
def callback_plans(call):
    text = (
        "*AVAILABLE SUBSCRIPTION PLANS*\n\n"
        "*1. Standard Monthly (30 Days)*\n"
        "• Full access to all 12 Synthetic Indices\n"
        "• Real-time D1 → H4 bias notifications\n"
        "• A+ liquidity sweep warnings & modifiers\n"
        "• Price: `Set Price`\n\n"
        "*2. Quarterly Access (90 Days)*\n"
        "• Uninterrupted alerts for 3 months\n"
        "• Priority support & setup guide\n"
        "• Price: `Discounted Price`\n\n"
        "Tap *Payment Methods* below to proceed."
    )
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Payment Methods", callback_data="nav_payment_methods"),
        InlineKeyboardButton("Back", callback_data="nav_home")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- PAYMENT METHOD SELECTION & DETAILS ---

@bot.callback_query_handler(func=lambda call: call.data == "nav_payment_methods")
def callback_payment_methods(call):
    text = (
        "*SELECT PAYMENT METHOD*\n\n"
        "Choose your preferred payment method below to view payment details:"
    )
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Mobile Money", callback_data="pay_momo"),
        InlineKeyboardButton("USDT (TRC20)", callback_data="pay_usdt")
    )
    markup.row(
        InlineKeyboardButton("Enter License Key", callback_data="nav_enter_key"),
        InlineKeyboardButton("Back", callback_data="nav_home")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "pay_momo")
def callback_pay_momo(call):
    text = (
        "*MOBILE MONEY PAYMENT*\n\n"
        "*1. Send Payment:*\n"
        f"`{MOBILE_MONEY_DETAILS}`\n\n"
        "*2. Submit Confirmation:*\n"
        "Send your transaction reference or screenshot to admin.\n\n"
        "*3. Activate:*\n"
        "You will receive an 8-character key. Tap *Enter License Key* below to activate."
    )
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Send Receipt (Telegram)", url=f"https://t.me/{ADMIN_TELEGRAM_USERNAME}"),
        InlineKeyboardButton("Enter License Key", callback_data="nav_enter_key")
    )
    markup.add(InlineKeyboardButton("Back to Payment Methods", callback_data="nav_payment_methods"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "pay_usdt")
def callback_pay_usdt(call):
    text = (
        "*USDT (TRC20) CRYPTO PAYMENT*\n\n"
        "*Network:* `TRON (TRC20)`\n"
        "*Deposit Address (Tap to copy):*\n"
        f"`{USDT_TRC20_WALLET}`\n\n"
        "*Important Notice:*\n"
        "• Send ONLY USDT via the TRC20 network. Sending via other networks (e.g. ERC20, BEP20) will result in lost funds.\n\n"
        "*Next Steps:*\n"
        "1. Complete the transfer.\n"
        "2. Copy the Transaction Hash (TxID) or screenshot.\n"
        "3. Click *Submit TxID to Admin* below.\n"
        "4. Receive your license key and activate."
    )
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Submit TxID to Admin", url=f"https://t.me/{ADMIN_TELEGRAM_USERNAME}"),
        InlineKeyboardButton("Enter License Key", callback_data="nav_enter_key")
    )
    markup.add(InlineKeyboardButton("Back to Payment Methods", callback_data="nav_payment_methods"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "nav_enter_key")
def callback_prompt_key(call):
    chat_id = str(call.message.chat.id)
    msg = bot.send_message(
        chat_id,
        "Please reply with your *8-character license key* (or send `/activate YOUR_KEY`):",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, process_key_reply)
    bot.answer_callback_query(call.id)

def process_key_reply(message):
    key = message.text.strip().replace("/activate", "").strip().upper()
    process_key_activation(str(message.chat.id), key)

@bot.callback_query_handler(func=lambda call: call.data == "nav_account")
def callback_account(call):
    chat_id = str(call.message.chat.id)
    subs = load_json(config.SUBSCRIPTIONS_FILE)
    active_pairs = subs.get(chat_id, [])
    
    pairs_list = "\n".join([f"• {p}" for p in active_pairs]) if active_pairs else "_No pairs configured._"
    
    text = (
        "*ACCOUNT OVERVIEW*\n\n"
        f"• *Telegram ID:* `{chat_id}`\n"
        f"• *Status:* `{'ACTIVE' if check_access(chat_id) else 'EXPIRED'}`\n"
        f"• *Valid Until:* `{get_expiry_date_str(chat_id)}`\n\n"
        f"*Active Monitored Pairs ({len(active_pairs)}):*\n{pairs_list}"
    )
    markup = InlineKeyboardMarkup()
    if check_access(chat_id):
        markup.add(InlineKeyboardButton("Edit Pairs", callback_data="nav_pairs"))
    else:
        markup.add(InlineKeyboardButton("Renew Subscription", callback_data="nav_plans"))
    markup.add(InlineKeyboardButton("Back", callback_data="nav_home"))
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "nav_pairs")
def callback_open_pairs(call):
    chat_id = str(call.message.chat.id)
    if not check_access(chat_id):
        callback_home(call)
        return
        
    subs = load_json(config.SUBSCRIPTIONS_FILE)
    user_drafts[chat_id] = set(subs.get(chat_id, []))
    
    bot.edit_message_text(
        "*INSTRUMENT CONFIGURATION*\nSelect indices to monitor:\n\nTap items to toggle, then press *Save Selection*.",
        chat_id,
        call.message.message_id,
        reply_markup=build_pairs_keyboard(chat_id),
        parse_mode="Markdown"
    )

# --- PAIR TOGGLE & BULK ACTIONS ---

@bot.callback_query_handler(func=lambda call: call.data.startswith("tog_"))
def handle_toggle(call):
    chat_id = str(call.message.chat.id)
    if not check_access(chat_id): return
    
    idx = int(call.data.split("_")[1])
    symbol = config.SYMBOLS[idx]
    if chat_id not in user_drafts:
        user_drafts[chat_id] = set(load_json(config.SUBSCRIPTIONS_FILE).get(chat_id, []))
    
    if symbol in user_drafts[chat_id]:
        user_drafts[chat_id].remove(symbol)
    else:
        user_drafts[chat_id].add(symbol)
        
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=build_pairs_keyboard(chat_id))

@bot.callback_query_handler(func=lambda call: call.data in ["act_select_all", "act_clear_all"])
def handle_bulk(call):
    chat_id = str(call.message.chat.id)
    if not check_access(chat_id): return
    
    user_drafts[chat_id] = set(config.SYMBOLS) if call.data == "act_select_all" else set()
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=build_pairs_keyboard(chat_id))

@bot.callback_query_handler(func=lambda call: call.data == "act_save")
def handle_save(call):
    chat_id = str(call.message.chat.id)
    if not check_access(chat_id): return
    
    selected = list(user_drafts.get(chat_id, []))
    subs = load_json(config.SUBSCRIPTIONS_FILE)
    subs[chat_id] = selected
    save_json(config.SUBSCRIPTIONS_FILE, subs)

    text = f"*CONFIGURATION SAVED*\n\nActive markets ({len(selected)}):\n" + "\n".join([f"• {s}" for s in sorted(selected)]) if selected else "*CONFIGURATION SAVED*\n\n_Alerts paused._"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Back to Dashboard", callback_data="nav_home"))
    bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

if __name__ == "__main__":
    print("[READY] Interactive Listener & Dashboard online with Crypto (TRC20) support...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"[NETWORK WARNING] Reconnecting in 5s... Error: {e}")
            time.sleep(5)