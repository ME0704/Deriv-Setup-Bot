import os
import json
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import config

bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN)

# In-memory buffer to hold user changes before pressing Save
user_drafts = {}

def load_subscriptions() -> dict:
    """Loads confirmed subscriptions from subscriptions.json."""
    if os.path.exists(config.SUBSCRIPTIONS_FILE):
        try:
            with open(config.SUBSCRIPTIONS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_subscriptions(subs: dict):
    """Writes updated subscriptions to subscriptions.json."""
    with open(config.SUBSCRIPTIONS_FILE, 'w') as f:
        json.dump(subs, f, indent=4)

def format_button_label(symbol: str, is_active: bool) -> str:
    """
    Creates a clean, compact label without brackets.
    Trims ' Index' for sleek 2-column mobile layout.
    """
    icon = "✓" if is_active else "✕"
    short_name = symbol.replace(" Index", "")
    return f"{icon}  {short_name}"

def build_pairs_keyboard(chat_id: str) -> InlineKeyboardMarkup:
    """Builds a 2-column inline keyboard with small toggle indicators."""
    selected_set = user_drafts.get(chat_id, set())
    markup = InlineKeyboardMarkup()

    # 1. Arrange pairs into 2 columns
    for i in range(0, len(config.SYMBOLS), 2):
        row_buttons = []
        for j in range(2):
            if i + j < len(config.SYMBOLS):
                idx = i + j
                sym = config.SYMBOLS[idx]
                is_selected = sym in selected_set
                btn_text = format_button_label(sym, is_selected)
                row_buttons.append(
                    InlineKeyboardButton(text=btn_text, callback_data=f"tog_{idx}")
                )
        markup.row(*row_buttons)

    # 2. Bulk selection actions
    markup.row(
        InlineKeyboardButton(text="Select All", callback_data="act_select_all"),
        InlineKeyboardButton(text="Clear All", callback_data="act_clear_all")
    )

    # 3. Dedicated Save button
    markup.add(
        InlineKeyboardButton(text="Save Selection", callback_data="act_save")
    )

    return markup

@bot.message_handler(commands=['start', 'pairs'])
def open_pairs_menu(message):
    """Loads previous selections into draft buffer and displays the 2-column menu."""
    chat_id = str(message.chat.id)
    subs = load_subscriptions()
    
    # Load previously saved selections
    user_drafts[chat_id] = set(subs.get(chat_id, []))

    header_text = (
        "*MARKET WATCH CONFIGURATION*\n"
        "Select synthetic indices to monitor (D1 → H4).\n\n"
        "`✓ Active`   `✕ Inactive`\n"
        "Tap items to toggle, then press *Save Selection*."
    )

    bot.send_message(
        chat_id,
        header_text,
        reply_markup=build_pairs_keyboard(chat_id),
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("tog_"))
def handle_toggle(call):
    """Toggles item in the in-memory draft."""
    chat_id = str(call.message.chat.id)
    idx = int(call.data.split("_")[1])
    symbol = config.SYMBOLS[idx]

    if chat_id not in user_drafts:
        subs = load_subscriptions()
        user_drafts[chat_id] = set(subs.get(chat_id, []))

    if symbol in user_drafts[chat_id]:
        user_drafts[chat_id].remove(symbol)
    else:
        user_drafts[chat_id].add(symbol)

    bot.edit_message_reply_markup(
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=build_pairs_keyboard(chat_id)
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "act_select_all")
def handle_select_all(call):
    chat_id = str(call.message.chat.id)
    user_drafts[chat_id] = set(config.SYMBOLS)

    bot.edit_message_reply_markup(
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=build_pairs_keyboard(chat_id)
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "act_clear_all")
def handle_clear_all(call):
    chat_id = str(call.message.chat.id)
    user_drafts[chat_id] = set()

    bot.edit_message_reply_markup(
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=build_pairs_keyboard(chat_id)
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "act_save")
def handle_save(call):
    """Commits in-memory draft to subscriptions.json."""
    chat_id = str(call.message.chat.id)
    selected = list(user_drafts.get(chat_id, []))

    subs = load_subscriptions()
    subs[chat_id] = selected
    save_subscriptions(subs)

    if selected:
        list_str = "\n".join([f"• {sym}" for sym in sorted(selected)])
        summary_text = (
            "*CONFIGURATION SAVED*\n\n"
            f"Active markets ({len(selected)}):\n"
            f"{list_str}\n\n"
            "_Send /pairs anytime to modify._"
        )
    else:
        summary_text = (
            "*CONFIGURATION SAVED*\n\n"
            "_No instruments selected. Alerts are paused._\n\n"
            "_Send /pairs anytime to modify._"
        )

    bot.edit_message_text(
        text=summary_text,
        chat_id=chat_id,
        message_id=call.message.message_id,
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id, text="Configuration saved.")

if __name__ == "__main__":
    print("[READY] Listener service online (2-column layout). Awaiting /pairs...")
    bot.infinity_polling()