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

# Track failed attempts in memory: { "chat_id": {"attempts": int, "lockout_until": datetime} }
failed_attempts = {}

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

# --- ADMIN COMMAND: GENERATE BOUND & FORMATTED KEY ---
@bot.message_handler(commands=['genkey'])
def generate_key(message):
    chat_id = str(message.chat.id)
    if chat_id != config.ADMIN_CHAT_ID:
        return

    # Usage:
    # /genkey 30              -> Generates an open key for 30 days
    # /genkey 30 @username    -> Binds key to a specific Telegram username
    # /genkey 30 123456789    -> Binds key to a specific Telegram User ID
    parts = message.text.split()
    days = 30
    assigned_target = None

    if len(parts) >= 2:
        try:
            days = int(parts[1])
        except ValueError:
            bot.reply_to(message, "Usage: `/genkey <days> [@username or user_id]`\nExample: `/genkey 30 @trader_dan`", parse_mode="Markdown")
            return

    if len(parts) >= 3:
        # Strip '@' and lowercase for consistency
        assigned_target = parts[2].replace("@", "").strip().lower()

    # Generate a 12-byte segmented enterprise key: MSR-XXXX-XXXX-XXXX
    raw = secrets.token_hex(6).upper()
    new_key = f"MSR-{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"

    keys_db = load_json(config.KEYS_DB)
    keys_db[new_key] = {
        "days": days,
        "assigned_to": assigned_target,  # None, username, or chat_id
        "used": False,
        "used_by": None,
        "created_at": datetime.now().isoformat()
    }
    save_json(config.KEYS_DB, keys_db)

    target_text = f"Bound to: `@{assigned_target}`" if assigned_target else "Status: `Unbound (Any user can redeem)`"
    
    bot.reply_to(
        message,
        f"*LICENSE KEY GENERATED*\n\n"
        f"Key: `{new_key}`\n"
        f"Duration: `{days} Days`\n"
        f"{target_text}\n\n"
        f"Send this exact code to the client.",
        parse_mode="Markdown"
    )

# --- USER ACTIVATION WITH BINDING & ANTI-BRUTE-FORCE ---
@bot.message_handler(commands=['activate'])
def activate_command(message):
    chat_id = str(message.chat.id)
    parts = message.text.split()
    
    if len(parts) < 2:
        bot.send_message(chat_id, "Please include your license key:\n`/activate MSR-XXXX-XXXX-XXXX`", parse_mode="Markdown")
        return
        
    process_secure_activation(message, parts[1].strip().upper())

def process_secure_activation(message, entered_key: str):
    chat_id = str(message.chat.id)
    username = (message.from_user.username or "").lower()
    now = datetime.now()

    # 1. Anti-Brute-Force Check
    if chat_id in failed_attempts:
        lockout = failed_attempts[chat_id].get("lockout_until")
        if lockout and now < lockout:
            wait_min = int((lockout - now).total_seconds() / 60) + 1
            bot.send_message(chat_id, f"Account locked due to too many failed attempts. Try again in {wait_min} minutes.")
            return

    keys_db = load_json(config.KEYS_DB)

    # 2. Key Validity Check
    if entered_key not in keys_db:
        record_failed_attempt(chat_id)
        bot.send_message(chat_id, "Invalid activation key. Please verify the code and try again.")
        return

    key_record = keys_db[entered_key]

    # 3. Double-Spend Check
    if key_record["used"]:
        bot.send_message(chat_id, "This license key has already been redeemed.")
        return

    # 4. Identity Binding Check (Username or Chat ID)
    bound_target = key_record.get("assigned_to")
    if bound_target:
        # Check against both the username and numeric chat_id
        if bound_target != username and bound_target != chat_id:
            bot.send_message(
                chat_id, 
                "Unauthorized: This license key is cryptographically assigned to another Telegram account."
            )
            return

    # Clear failed attempt counter upon valid entry
    if chat_id in failed_attempts:
        del failed_attempts[chat_id]

    # 5. Apply Subscription
    days_to_add = key_record["days"]
    users = load_json(config.USERS_DB)
    current_expiry = now

    if chat_id in users and users[chat_id].get("expiry"):
        old_expiry = datetime.fromisoformat(users[chat_id]["expiry"])
        if old_expiry > current_expiry:
            current_expiry = old_expiry

    new_expiry = current_expiry + timedelta(days=days_to_add)
    users[chat_id] = {
        "expiry": new_expiry.isoformat(),
        "username": username
    }
    save_json(config.USERS_DB, users)

    # Mark key as consumed
    key_record["used"] = True
    key_record["used_by"] = chat_id
    key_record["redeemed_at"] = now.isoformat()
    save_json(config.KEYS_DB, keys_db)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Configure Pairs", callback_data="nav_pairs"))
    
    bot.send_message(
        chat_id,
        f"*LICENSE ACTIVATED SUCCESSFULLY*\n\n"
        f"• Plan Duration: `{days_to_add} Days`\n"
        f"• Valid Until: `{new_expiry.strftime('%Y-%m-%d %H:%M EAT')}`\n\n"
        f"Tap below to select your active markets.",
        reply_markup=markup,
        parse_mode="Markdown"
    )

def record_failed_attempt(chat_id: str):
    now = datetime.now()
    if chat_id not in failed_attempts:
        failed_attempts[chat_id] = {"attempts": 1, "lockout_until": None}
    else:
        failed_attempts[chat_id]["attempts"] += 1

    if failed_attempts[chat_id]["attempts"] >= 3:
        failed_attempts[chat_id]["lockout_until"] = now + timedelta(minutes=30)
        bot.send_message(chat_id, "Too many failed attempts. You have been locked out for 30 minutes.")

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

@bot.message_handler(commands=['stats', 'admin'])
def admin_dashboard(message):
    chat_id = str(message.chat.id)
    if chat_id != config.ADMIN_CHAT_ID:
        return

    # 1. Load Databases
    users = load_json(config.USERS_DB)
    keys_db = load_json(config.KEYS_DB)

    # 2. Calculate User Metrics
    active_users = 0
    expired_users = 0
    now = datetime.now()

    for uid, data in users.items():
        if "expiry" in data:
            if now < datetime.fromisoformat(data["expiry"]):
                active_users += 1
            else:
                expired_users += 1

    # 3. Calculate Revenue & Keys (Assuming $30 per 30-day key)
    MONTHLY_PRICE = 30
    total_revenue = 0
    used_keys = 0
    unused_keys = 0

    for key, data in keys_db.items():
        if data.get("used"):
            used_keys += 1
            # Calculate revenue based on the duration of the key sold
            months_sold = data.get("days", 30) / 30
            total_revenue += (months_sold * MONTHLY_PRICE)
        else:
            unused_keys += 1

    # 4. Format the Dashboard Report
    report = (
        "📊 *MS RADAR ADMIN DASHBOARD*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "*💰 FINANCIAL OVERVIEW*\n"
        f"• Total Est. Revenue: `${total_revenue:,.2f}`\n\n"
        "*👥 USER METRICS*\n"
        f"• Active Subscriptions: `{active_users}`\n"
        f"• Expired Subscriptions: `{expired_users}`\n"
        f"• Total Users in DB: `{len(users)}`\n\n"
        "*🔑 LICENSE KEY STATUS*\n"
        f"• Keys Redeemed: `{used_keys}`\n"
        f"• Keys Pending (Unused): `{unused_keys}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "_Data pulled live from local JSON databases._"
    )

    bot.send_message(chat_id, report, parse_mode="Markdown")

if __name__ == "__main__":
    print("[READY] Interactive Listener & Dashboard online with Crypto (TRC20) support...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"[NETWORK WARNING] Reconnecting in 5s... Error: {e}")
            time.sleep(5)