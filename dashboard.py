import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. CORE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="MS Radar & Synthetics | Executive Terminal",
    page_icon="■",
    layout="wide",
    initial_sidebar_state="expanded"
)

LOGO_PATH = "msradarbot.jpg"  # Ensure this file is in the same folder
USERS_DB = "users.json"
KEYS_DB = "keys.json"
SUBS_DB = "subscriptions.json"
PRICE_PER_30_DAYS = 30.0

ADMIN_PASSWORD = os.getenv("ADMIN_DASHBOARD_PASS", "admin2026")

# ==========================================
# 2. AUTHENTICATION (REDESIGNED LOGIN)
# ==========================================
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def handle_login(password_input: str):
    if password_input == ADMIN_PASSWORD:
        st.session_state["authenticated"] = True
        st.rerun()
    else:
        st.error("Authentication Failed. Invalid Key.")

def handle_logout():
    st.session_state["authenticated"] = False
    st.rerun()

# --- LOGIN SCREEN UI ---
if not st.session_state["authenticated"]:
    # Force dark terminal aesthetic strictly for the login gate
    st.markdown("""
        <style>
            .stApp { background-color: #04070B; color: #F8FAFC; font-family: -apple-system, sans-serif; }
            .login-container {
                max-width: 480px;
                margin: 10vh auto;
                background-color: #0A111A;
                border: 1px solid #162436;
                border-top: 3px solid #00E5FF;
                border-radius: 8px;
                padding: 45px 40px;
                box-shadow: 0 15px 35px rgba(0, 229, 255, 0.05);
                text-align: center;
            }
            .login-title { font-size: 1.5rem; font-weight: 800; letter-spacing: 0.05em; color: #F8FAFC; margin-bottom: 8px; }
            .login-sub { font-size: 0.85rem; color: #8B949E; margin-bottom: 30px; }
            .stTextInput>div>div>input {
                background-color: #05080D !important;
                border: 1px solid #162436 !important;
                color: #00E5FF !important;
                text-align: center;
                font-size: 1.2rem;
                letter-spacing: 0.2em;
            }
            .stButton>button {
                background-color: #00E5FF !important;
                color: #04070B !important;
                font-weight: 700 !important;
                border: none !important;
                padding: 22px 24px !important;
                width: 100%;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-top: 20px;
                transition: all 0.2s ease;
            }
            .stButton>button:hover { background-color: #00B4D8 !important; box-shadow: 0 0 15px rgba(0,229,255,0.3); }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="login-container">
            <h1 class="login-title">MS COMMAND TERMINAL</h1>
            <p class="login-sub">SECURE ADMINISTRATIVE GATEWAY</p>
        </div>
    """, unsafe_allow_html=True)
    
    col_l1, col_l2, col_l3 = st.columns([1, 1.2, 1])
    with col_l2:
        pwd = st.text_input("AUTHORIZATION KEY", type="password", placeholder="••••••••", label_visibility="collapsed")
        if st.button("Initialize Terminal"):
            handle_login(pwd)
    st.stop()

# ==========================================
# 3. DYNAMIC THEME ENGINE (POST-AUTH)
# ==========================================
st.sidebar.markdown("### SYSTEM PREFERENCES")
theme_choice = st.sidebar.radio("Interface Theme", ["Dark Mode (Teal Accent)", "Light Mode (Corporate)"], index=0)
is_dark = theme_choice.startswith("Dark")

if is_dark:
    # Deep Terminal Colors
    bg_canvas = "#04070B"
    card_surface = "#0A111A"
    card_stroke = "#162436"
    teal_accent = "#00E5FF"
    teal_dim = "rgba(0, 229, 255, 0.1)"
    fg_primary = "#F8FAFC"
    fg_muted = "#8B949E"
    plot_template = "plotly_dark"
    table_hover = "#0D1724"
else:
    # Crisp Light Mode Colors
    bg_canvas = "#F8FAFC"
    card_surface = "#FFFFFF"
    card_stroke = "#E2E8F0"
    teal_accent = "#0D9488"
    teal_dim = "rgba(13, 148, 136, 0.08)"
    fg_primary = "#0F172A"
    fg_muted = "#64748B"
    plot_template = "plotly_white"
    table_hover = "#F1F5F9"

st.markdown(f"""
    <style>
        /* Global Canvas */
        .stApp {{ background-color: {bg_canvas}; color: {fg_primary}; }}
        div[data-testid="stSidebar"] {{ background-color: {card_surface}; border-right: 1px solid {card_stroke}; }}
        
        /* KPI Cards */
        .kpi-container {{
            background-color: {card_surface};
            border: 1px solid {card_stroke};
            border-top: 3px solid {teal_accent};
            border-radius: 6px;
            padding: 20px 24px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.02);
        }}
        .kpi-title {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em; color: {fg_muted}; font-weight: 700; }}
        .kpi-metric {{ font-size: 2.1rem; font-weight: 800; color: {fg_primary}; letter-spacing: -0.02em; margin-top: 6px; }}
        .kpi-note {{ font-size: 0.75rem; color: {teal_accent}; margin-top: 6px; font-weight: 600; }}
        
        /* Custom HTML Data Tables (Fixes Light Mode Bug) */
        .custom-table-container {{ overflow-x: auto; margin-top: 10px; border: 1px solid {card_stroke}; border-radius: 6px; }}
        .custom-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; text-align: left; background-color: {card_surface}; }}
        .custom-table th {{ background-color: {teal_dim}; color: {teal_accent}; padding: 14px 16px; font-weight: 700; border-bottom: 2px solid {teal_accent}; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }}
        .custom-table td {{ padding: 14px 16px; border-bottom: 1px solid {card_stroke}; color: {fg_primary}; }}
        .custom-table tr:hover {{ background-color: {table_hover}; }}
        
        /* Badges & HR */
        .status-pill {{ background-color: {teal_dim}; color: {teal_accent}; border: 1px solid {teal_accent}; padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; }}
        hr {{ border-color: {card_stroke}; margin: 24px 0; }}
    </style>
""", unsafe_allow_html=True)

st.sidebar.markdown("<br>", unsafe_allow_html=True)
if st.sidebar.button("Sign Out / Lock Session", use_container_width=True):
    handle_logout()

# ==========================================
# 4. DATABASE INGESTION
# ==========================================
def load_db(path):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception: pass
    return {}

users_data = load_db(USERS_DB)
keys_data = load_db(KEYS_DB)
subs_data = load_db(SUBS_DB)

now = datetime.now()
active_licenses = 0
expired_licenses = 0
gross_revenue = 0.0
redeemed_keys = 0
available_keys = 0

user_rows = []
asset_demand = {}

for chat_id, u_info in users_data.items():
    raw_exp = u_info.get("expiry", "")
    username = u_info.get("username", "") or "Not Set"
    is_valid = False

    if raw_exp:
        try:
            if now < datetime.fromisoformat(raw_exp):
                is_valid = True
                active_licenses += 1
            else:
                expired_licenses += 1
        except Exception: expired_licenses += 1
    else: expired_licenses += 1

    selected_pairs = subs_data.get(chat_id, [])
    for sym in selected_pairs: asset_demand[sym] = asset_demand.get(sym, 0) + 1

    user_rows.append({
        "Chat ID": chat_id,
        "Username": f"@{username}" if username != "Not Set" else username,
        "Status": "ACTIVE" if is_valid else "EXPIRED",
        "Expiration": raw_exp.replace("T", " ")[:16] if raw_exp else "N/A",
        "Pairs": len(selected_pairs),
        "Watchlist": ", ".join(selected_pairs) if selected_pairs else "None"
    })

key_rows = []
for k_str, k_info in keys_data.items():
    is_consumed = k_info.get("used", False)
    plan_days = k_info.get("days", 30)
    bound_to = k_info.get("assigned_to") or "OPEN"
    consumed_by = k_info.get("used_by") or "N/A"
    
    if is_consumed:
        redeemed_keys += 1
        gross_revenue += (plan_days / 30.0) * PRICE_PER_30_DAYS
    else:
        available_keys += 1

    key_rows.append({
        "License Key": k_str,
        "Duration": f"{plan_days} Days",
        "Status": "REDEEMED" if is_consumed else "AVAILABLE",
        "Bound Target": f"@{bound_to}" if bound_to != "OPEN" else "Unbound",
        "Redeemed By ID": consumed_by
    })

df_users = pd.DataFrame(user_rows)
df_keys = pd.DataFrame(key_rows)

# ==========================================
# 5. MAIN HEADER (LOGO INTEGRATION)
# ==========================================
head_logo, head_title, head_actions = st.columns([0.5, 3.5, 1.2])

with head_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=80)
    else:
        st.markdown(f"""
            <svg width="70" height="70" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="46" fill="{card_surface}" stroke="{teal_accent}" stroke-width="3"/>
                <circle cx="28" cy="72" r="6" fill="{teal_accent}"/>
                <path d="M 28 46 A 26 26 0 0 1 54 72" fill="none" stroke="{teal_accent}" stroke-width="3"/>
            </svg>
        """, unsafe_allow_html=True)

with head_title:
    st.markdown(f"<h1 style='margin:0; padding-top:10px; font-size:1.9rem; font-weight:800; color:{fg_primary}; letter-spacing:-0.02em;'>MS COMMAND TERMINAL</h1>", unsafe_allow_html=True)

with head_actions:
    st.markdown(f"""
        <div style="text-align:right; padding-top:15px;">
            <span class="status-pill">SYSTEM ONLINE</span>
            <div style="font-size:0.75rem; color:{fg_muted}; margin-top:8px;">{now.strftime('%d %b %Y | %H:%M:%S')}</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='margin:20px 0;'>", unsafe_allow_html=True)

# ==========================================
# 6. KPI CARDS
# ==========================================
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-title">Gross Revenue</div>
            <div class="kpi-metric">${gross_revenue:,.2f}</div>
            <div class="kpi-note">Base: ${PRICE_PER_30_DAYS:,.0f} / 30-Day Unit</div>
        </div>
    """, unsafe_allow_html=True)
with c2:
    st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-title">Active Subscriptions</div>
            <div class="kpi-metric">{active_licenses}</div>
            <div class="kpi-note">{expired_licenses} Expired / Inactive</div>
        </div>
    """, unsafe_allow_html=True)
with c3:
    st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-title">Redeemed Keys</div>
            <div class="kpi-metric">{redeemed_keys}</div>
            <div class="kpi-note">{len(keys_data)} Generated In Total</div>
        </div>
    """, unsafe_allow_html=True)
with c4:
    st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-title">Key Inventory</div>
            <div class="kpi-metric">{available_keys}</div>
            <div class="kpi-note">Available for Allocation</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr>", unsafe_allow_html=True)

# ==========================================
# 7. ANALYTICS GRAPHS
# ==========================================
col_donut, col_bar = st.columns([1, 2.5])

with col_donut:
    st.markdown(f"<h4 style='font-size:0.85rem; font-weight:700; color:{fg_muted}; text-transform:uppercase;'>Subscription Health</h4>", unsafe_allow_html=True)
    if (active_licenses + expired_licenses) > 0:
        fig_donut = go.Figure(data=[go.Pie(
            labels=["Active", "Expired"],
            values=[active_licenses, expired_licenses],
            hole=0.65,
            marker=dict(colors=[teal_accent, "#334155" if is_dark else "#CBD5E1"]),
            textinfo="value",
            hoverinfo="label+percent"
        )])
        fig_donut.update_layout(
            template=plot_template,
            height=280,
            margin=dict(t=20, b=20, l=20, r=20),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("No active or expired subscriptions recorded.")

with col_bar:
    st.markdown(f"<h4 style='font-size:0.85rem; font-weight:700; color:{fg_muted}; text-transform:uppercase;'>Asset Subscriber Demand</h4>", unsafe_allow_html=True)
    if asset_demand:
        df_p = pd.DataFrame(list(asset_demand.items()), columns=["Asset", "Subscribers"]).sort_values(by="Subscribers", ascending=True)
        fig_bar = px.bar(
            df_p,
            x="Subscribers",
            y="Asset",
            orientation="h",
            template=plot_template,
            color_discrete_sequence=[teal_accent]
        )
        fig_bar.update_layout(
            height=280,
            bargap=0.3,
            margin=dict(t=20, b=20, l=10, r=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor=card_stroke, tickformat="d", title=""),
            yaxis=dict(gridcolor=card_stroke, title="")
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No market pairs configured by subscribers yet.")

st.markdown("<hr>", unsafe_allow_html=True)

# ==========================================
# 8. CUSTOM HTML TABLES (FIXES LIGHT MODE)
# ==========================================
def render_html_table(df):
    if df.empty:
        st.info("No records found.")
        return
    # Convert DataFrame to HTML with our custom CSS classes
    html_table = df.to_html(index=False, classes="custom-table", border=0)
    st.markdown(f'<div class="custom-table-container">{html_table}</div>', unsafe_allow_html=True)

st.markdown(f"<h4 style='font-size:0.95rem; font-weight:700; color:{fg_primary};'>CLIENT ACCOUNT DIRECTORY</h4>", unsafe_allow_html=True)
filter_col, _ = st.columns([1, 4])
with filter_col:
    status_filter = st.selectbox("Status Filter", ["ALL", "ACTIVE", "EXPIRED"], index=0, label_visibility="collapsed")

filtered_users = df_users if status_filter == "ALL" else df_users[df_users["Status"] == status_filter]
render_html_table(filtered_users)

st.markdown("<br><br>", unsafe_allow_html=True)

st.markdown(f"<h4 style='font-size:0.95rem; font-weight:700; color:{fg_primary};'>LICENSE KEY LEDGER</h4>", unsafe_allow_html=True)
render_html_table(df_keys)

st.markdown("<hr>", unsafe_allow_html=True)

# ==========================================
# 9. EXPORT LEDGER
# ==========================================
st.markdown(f"<h4 style='font-size:0.95rem; font-weight:700; color:{fg_primary};'>FINANCIAL AUDIT EXPORT</h4>", unsafe_allow_html=True)

exp_c1, exp_c2 = st.columns(2)
with exp_c1:
    if not df_users.empty:
        st.download_button("Download Client Directory (CSV)", data=df_users.to_csv(index=False).encode("utf-8"), file_name=f"MS_Clients_{now.strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)
with exp_c2:
    if not df_keys.empty:
        st.download_button("Download Key Ledger (CSV)", data=df_keys.to_csv(index=False).encode("utf-8"), file_name=f"MS_Ledger_{now.strftime('%Y%m%d')}.csv", mime="text/csv", use_container_width=True)