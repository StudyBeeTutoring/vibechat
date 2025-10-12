import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
import time
from streamlit_autorefresh import st_autorefresh
import json
import hashlib
from textblob import TextBlob
import nltk


@st.cache_resource
def download_nltk_data():
    """Download the NLTK 'punkt' tokenizer if not already present."""
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')


# --- Constants and Configuration ---
APP_NAME = "Crème"
SUPER_ADMIN_USERNAME = st.secrets["SUPER_ADMIN_USERNAME"]
SUPER_ADMIN_DEFAULT_PASS = st.secrets["SUPER_ADMIN_DEFAULT_PASS"]
APP_SALT = st.secrets["APP_SALT"]

AVATARS = {
    "Latte": "☕", "Macaron": "🍬", "Moon": "🌙", "Cloud": "☁️",
    "Feather": "🪶", "Dove": "🕊️", "Lotus": "🌸", "Harp": "🎼"
}


# --- Page and Style Configuration ---
st.set_page_config(page_title=APP_NAME, page_icon="🍦", layout="wide")

st.markdown("""
    <style>
        /* Main App & Text */
        .stApp {
            background-color: #FFF8E7; /* The main creamy background */
        }
        body, .stApp, p, h1, h2, h3, h4, h5, h6, .st-emotion-cache-16idsys p {
            color: #4A4A4A; /* Dark, readable slate gray */
        }
        
        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF; /* A clean, crisp white for the sidebar */
            border-right: 1px solid #E0E0E0;
        }

        /* Custom Title with Gradient Text */
        .creme-title {
            font-size: 3.5rem;
            font-weight: bold;
            padding-bottom: 0.5rem;
            background: -webkit-linear-gradient(45deg, #a0c4ff, #ffafcc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        /* Buttons */
        .stButton button {
            background-color: #BDE0FE; /* Soft blue */
            color: #283618; /* Dark olive green for contrast */
            border: none;
            border-radius: 8px;
            transition: all 0.2s ease-in-out;
        }
        .stButton button:hover {
            background-color: #FFC8DD; /* Soft pink on hover */
            transform: scale(1.02);
        }
        .stButton button:active {
            background-color: #FFAFCC;
        }
        
        /* Text Inputs & Select Boxes */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
            background-color: #FFFFFF;
            border: 1px solid #D0D0D0;
            border-radius: 8px;
            color: #4A4A4A;
        }
        
        /* Chat Area */
        .stChatInput {
            background-color: #FFF8E7;
        }
        [data-testid="stChatMessage"] {
            background-color: #FFFFFF;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        /* Expander styling */
        .st-emotion-cache-1h9usn1 {
            border-color: #E0E0E0;
        }
    </style>
""", unsafe_allow_html=True)


# --- Database Setup ---
conn = st.connection("chat_db", type="sql", url="sqlite:///creme_app.db", ttl=0)

def init_db():
    """Initializes the database with required tables and default admin user."""
    with conn.session as s:
        # User table
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, hashed_password TEXT NOT NULL,
                avatar TEXT, role TEXT DEFAULT 'user', status TEXT DEFAULT 'active'
            );
        """))
        # Messages table
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, username TEXT, avatar TEXT,
                message TEXT, timestamp DATETIME, sentiment REAL DEFAULT 0.0
            );
        """))
        # NEW: Table for app-wide settings
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY, value TEXT
            );
        """))
        # NEW: Table for tracking muted users
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS muted_users (
                username TEXT PRIMARY KEY, muted_until DATETIME NOT NULL
            );
        """))

        # Ensure default admin exists
        admin_user = s.execute(text("SELECT * FROM users WHERE username = :user;"), params=dict(user=SUPER_ADMIN_USERNAME)).fetchone()
        if not admin_user:
            hashed_pass = hash_password(SUPER_ADMIN_DEFAULT_PASS)
            s.execute(text("""
                INSERT INTO users (username, hashed_password, avatar, role, status)
                VALUES (:user, :hp, '👑', 'admin', 'active');
            """), params=dict(user=SUPER_ADMIN_USERNAME, hp=hashed_pass))

        # NEW: Initialize default app state values if they don't exist
        s.execute(text("INSERT OR IGNORE INTO app_state (key, value) VALUES ('chat_mute_until', '2000-01-01 00:00:00');"))
        s.execute(text("INSERT OR IGNORE INTO app_state (key, value) VALUES ('guest_login_disabled', 'false');"))
        s.commit()


# --- Helper Functions ---
def hash_password(password):
    return hashlib.sha256((password + APP_SALT).encode()).hexdigest()

def verify_password(stored_hash, provided_password):
    return stored_hash == hash_password(provided_password)

def clear_old_messages():
    cutoff_time = datetime.now() - timedelta(hours=1)
    with conn.session as s:
        s.execute(text("DELETE FROM messages WHERE timestamp < :cutoff;"), params=dict(cutoff=cutoff_time))
        s.commit()

def analyze_sentiment(text_message):
    return TextBlob(text_message).sentiment.polarity

def get_sentiment_emoji(score):
    if score > 0.1: return "😊"
    elif score < -0.1: return "😠"
    else: return "😐"

# --- UI Screens ---
def show_welcome_screen():
    st.markdown(f'<p class="creme-title">Welcome to {APP_NAME}</p>', unsafe_allow_html=True)
    st.caption("A soft place to land your thoughts.")
    st.write("")
    col1, col2, col3 = st.columns(3)

    if col1.button("🔒 Login", use_container_width=True):
        st.session_state.screen = "login"
        st.rerun()
    if col2.button("✍️ Register", use_container_width=True):
        st.session_state.screen = "register"
        st.rerun()
    
    # NEW: Conditionally show the guest button based on admin settings
    guest_disabled = conn.query("SELECT value FROM app_state WHERE key = 'guest_login_disabled'").iloc[0]['value'] == 'true'
    if not guest_disabled:
        if col3.button("👤 Continue as Guest", use_container_width=True):
            st.session_state.screen = "guest_setup"
            st.rerun()
    else:
        with col3:
            st.info("Guest login is temporarily disabled by an administrator.", icon="🚫")


def show_login_screen():
    st.header("Login to Your Account")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            with conn.session as s:
                user = s.execute(text("SELECT * FROM users WHERE username = :u;"), params=dict(u=username)).fetchone()
            if user and verify_password(user.hashed_password, password):
                if user.status == 'banned':
                    st.error("This account has been banned.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.username = user.username
                    st.session_state.avatar = user.avatar
                    st.session_state.role = user.role
                    st.session_state.screen = "chat"
                    if user.role == 'admin' and verify_password(user.hashed_password, SUPER_ADMIN_DEFAULT_PASS):
                        st.session_state.admin_using_default_pass = True
                    st.success("Login successful!")
                    time.sleep(1)
                    st.rerun()
            else:
                st.error("Invalid username or password.")
    if st.button("← Back to Welcome"):
        st.session_state.screen = "welcome"
        st.rerun()


def show_register_screen():
    st.header("Create a New Account")
    with st.form("register_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        avatar_label = st.selectbox("Choose Your Avatar", options=list(AVATARS.keys()))
        submitted = st.form_submit_button("Register")
        if submitted:
            if not username or not password:
                st.warning("Please fill out all fields.")
            else:
                hashed_pass = hash_password(password)
                try:
                    with conn.session as s:
                        s.execute(text("INSERT INTO users (username, hashed_password, avatar) VALUES (:u, :hp, :a);"), params=dict(u=username, hp=hashed_pass, a=AVATARS[avatar_label]))
                        s.commit()
                    st.success("Registration successful! Please log in.")
                    time.sleep(1)
                    st.session_state.screen = "login"
                    st.rerun()
                except Exception as e:
                    if "UNIQUE constraint failed" in str(e):
                        st.error("Username already exists.")
                    else:
                        st.error(f"An error occurred: {e}")
    if st.button("← Back to Welcome"):
        st.session_state.screen = "welcome"
        st.rerun()


def show_guest_setup_screen():
    st.header("Enter as a Guest")
    with st.form("guest_form"):
        username = st.text_input("Guest Username")
        avatar_label = st.selectbox("Choose Your Avatar", options=list(AVATARS.keys()))
        submitted = st.form_submit_button("Enter Chat")
        if submitted:
            if not username:
                st.warning("Please enter a username.")
            else:
                st.session_state.logged_in = True
                st.session_state.username = f"{username} (Guest)"
                st.session_state.avatar = AVATARS[avatar_label]
                st.session_state.role = "guest"
                st.session_state.screen = "chat"
                st.rerun()
    if st.button("← Back to Welcome"):
        st.session_state.screen = "welcome"
        st.rerun()


def show_change_password_form(username_to_change, is_admin_reset=False):
    form_key = f"change_pass_{username_to_change}"
    if is_admin_reset:
        st.write(f"Set a new password for '{username_to_change}':")
    else:
        st.subheader("🔑 Change Your Password")
    with st.form(form_key):
        if not is_admin_reset:
            current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Change Password")
        if submitted:
            if not is_admin_reset:
                with conn.session as s:
                    user = s.execute(text("SELECT hashed_password FROM users WHERE username = :u"), params=dict(u=username_to_change)).fetchone()
                if not verify_password(user.hashed_password, current_password):
                    st.error("Current password is incorrect.")
                    return
            if new_password != confirm_password:
                st.error("New passwords do not match.")
            elif len(new_password) < 6:
                st.error("New password must be at least 6 characters long.")
            else:
                new_hashed_password = hash_password(new_password)
                with conn.session as s:
                    s.execute(text("UPDATE users SET hashed_password = :hp WHERE username = :u"), params=dict(hp=new_hashed_password, u=username_to_change))
                    s.commit()
                st.success(f"Password for '{username_to_change}' changed successfully!")
                if not is_admin_reset:
                    st.session_state.admin_using_default_pass = False
                time.sleep(1)
                st.rerun()

# --- ADMIN DASHBOARD (HEAVILY MODIFIED) ---
def show_admin_dashboard():
    st.subheader("🛡️ Admin Dashboard")
    st.write("Moderate users and manage the chat room.")
    
    # --- Global Chat Controls ---
    st.markdown("---")
    st.subheader("Global Chat Controls")

    # Chat-wide mute control
    mute_status_df = conn.query("SELECT value FROM app_state WHERE key = 'chat_mute_until' LIMIT 1")
    chat_mute_until = pd.to_datetime(mute_status_df['value'][0])
    
    if chat_mute_until > datetime.now():
        st.warning(f"Chat is globally muted until {chat_mute_until.strftime('%Y-%m-%d %H:%M:%S')}", icon="🔇")
        if st.button("Lift Chat-Wide Mute", use_container_width=True):
            with conn.session as s:
                s.execute(text("UPDATE app_state SET value = :val WHERE key = 'chat_mute_until'"), params=dict(val=datetime.now() - timedelta(minutes=1)))
                s.commit()
            st.rerun()
    else:
        st.success("Chat is currently active.", icon="✅")
        with st.form("mute_chat_form"):
            duration_map = {"5 Minutes": 5, "15 Minutes": 15, "1 Hour": 60, "8 Hours": 480}
            duration = st.selectbox("Select mute duration:", options=duration_map.keys())
            submitted = st.form_submit_button("Mute Entire Chat")
            if submitted:
                mute_end_time = datetime.now() + timedelta(minutes=duration_map[duration])
                with conn.session as s:
                    s.execute(text("UPDATE app_state SET value = :val WHERE key = 'chat_mute_until'"), params=dict(val=mute_end_time))
                    s.commit()
                st.rerun()

    # Disable guest login control
    guest_disabled_val = conn.query("SELECT value FROM app_state WHERE key = 'guest_login_disabled'").iloc[0]['value']
    guest_login_disabled = guest_disabled_val == 'true'

    if guest_login_disabled:
        if st.button("✅ Enable Guest Login", use_container_width=True):
            with conn.session as s: s.execute(text("UPDATE app_state SET value='false' WHERE key='guest_login_disabled'")); s.commit()
            st.rerun()
    else:
        if st.button("🚫 Disable Guest Login", use_container_width=True, type="primary"):
            with conn.session as s: s.execute(text("UPDATE app_state SET value='true' WHERE key='guest_login_disabled'")); s.commit()
            st.rerun()

    # Clear all messages control
    if st.button("🚨 Clear All Messages", use_container_width=True):
        with st.popover("Confirm Action"):
            st.warning("This will permanently delete all messages.")
            if st.button("Yes, Delete Everything", type="primary"):
                with conn.session as s:
                    s.execute(text("DELETE FROM messages;"))
                    s.commit()
                st.toast("Chat history cleared!")
                st.rerun()

    # --- User Management ---
    st.markdown("---")
    st.subheader("User Management")
    
    # Get registered users
    registered_users_df = conn.query("SELECT username, avatar, role, status FROM users WHERE username != :admin ORDER BY username;", params=dict(admin=SUPER_ADMIN_USERNAME), ttl=10)
    
    # Get guest users active in the last hour
    hour_ago = datetime.now() - timedelta(hours=1)
    guest_users_df = conn.query(
        "SELECT DISTINCT username, avatar FROM messages WHERE username LIKE '%(Guest)' AND timestamp > :time ORDER BY username;",
        params=dict(time=hour_ago), ttl=10
    )
    guest_users_df['role'] = 'guest'
    guest_users_df['status'] = 'active'
    
    # Combine lists
    all_users_df = pd.concat([registered_users_df, guest_users_df]).drop_duplicates(subset=['username'])
    muted_users_df = conn.query("SELECT username, muted_until FROM muted_users WHERE muted_until > :now", params=dict(now=datetime.now()), ttl=5)
    muted_usernames = list(muted_users_df['username'])

    for _, user in all_users_df.iterrows():
        is_muted = user.username in muted_usernames
        status_text = f"Status: **{user.status.capitalize()}**"
        if is_muted: status_text += " / **Muted** 🔇"

        st.markdown(f"**{user.avatar} {user.username}** (`{user.role}`) - {status_text}")
        
        c1, c2, c3 = st.columns(3)
        # --- Mute/Unmute Logic ---
        with c1:
            if is_muted:
                if st.button("Unmute", key=f"unmute_{user.username}", use_container_width=True):
                    with conn.session as s: s.execute(text("DELETE FROM muted_users WHERE username = :u"), params=dict(u=user.username)); s.commit()
                    st.rerun()
            else:
                with st.popover("Mute User", use_container_width=True):
                    with st.form(f"mute_form_{user.username}"):
                        duration_map = {"5 Minutes": 5, "1 Hour": 60, "24 Hours": 1440}
                        duration = st.selectbox("Mute for:", options=duration_map.keys(), key=f"mute_dur_{user.username}")
                        submitted = st.form_submit_button("Confirm Mute")
                        if submitted:
                            mute_end = datetime.now() + timedelta(minutes=duration_map[duration])
                            with conn.session as s:
                                s.execute(text("INSERT OR REPLACE INTO muted_users (username, muted_until) VALUES (:u, :end)"), params=dict(u=user.username, end=mute_end))
                                s.commit()
                            st.rerun()
        
        # --- Ban/Unban Logic (for registered users only) ---
        if user.role != 'guest':
            with c2:
                if user.status == 'active':
                    if st.button("Ban", key=f"ban_{user.username}", use_container_width=True, type="primary"):
                        with conn.session as s: s.execute(text("UPDATE users SET status = 'banned' WHERE username = :u"), params=dict(u=user.username)); s.commit()
                        st.rerun()
                else:
                    if st.button("Unban", key=f"unban_{user.username}", use_container_width=True):
                        with conn.session as s: s.execute(text("UPDATE users SET status = 'active' WHERE username = :u"), params=dict(u=user.username)); s.commit()
                        st.rerun()
            with c3:
                 with st.popover("Reset Pass", use_container_width=True):
                    show_change_password_form(user.username, is_admin_reset=True)
        st.markdown("---")


# --- Main Chat Screen (MODIFIED) ---
def show_chat_screen():
    clear_old_messages()
    st_autorefresh(interval=5000, limit=None, key="chat_refresh")

    if st.session_state.get("admin_using_default_pass", False):
        st.warning("🚨 **Security Alert:** You are using the default admin password. Please change it immediately.", icon="⚠️")
    
    with st.sidebar:
        st.title(f"{st.session_state.avatar} {st.session_state.username}")
        st.caption(f"Role: {st.session_state.role.capitalize()}")
        if st.button("Log Out"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        if st.session_state.role == 'admin':
            st.divider()
            with st.expander("Admin Dashboard", expanded=False):
                show_admin_dashboard()
            st.divider()
            with st.expander("Change Your Password"):
                show_change_password_form(st.session_state.username)

    st.markdown(f'<p class="creme-title">{APP_NAME}</p>', unsafe_allow_html=True)
    st.caption("Messages are ephemeral and vanish after 1 hour.")

    chat_container = st.container(height=500, border=False)
    with chat_container:
        messages_df = conn.query("SELECT * FROM messages ORDER BY timestamp ASC;", ttl=0)
        for _, row in messages_df.iterrows():
            with st.chat_message(name=row["username"], avatar=row["avatar"]):
                sentiment_emoji = get_sentiment_emoji(row['sentiment'])
                st.markdown(f"**{row['username']}** {sentiment_emoji}")
                st.write(row["message"])
                ts = pd.to_datetime(row["timestamp"])
                st.caption(f"_{ts.strftime('%b %d, %I:%M %p')}_")

    # --- CHAT INPUT LOGIC (MODIFIED) ---
    # Check for global mute
    mute_status = conn.query("SELECT value FROM app_state WHERE key = 'chat_mute_until' LIMIT 1", ttl=5).iloc[0]['value']
    is_globally_muted = pd.to_datetime(mute_status) > datetime.now()

    # Check for individual mute
    user_mute_status = conn.query("SELECT muted_until FROM muted_users WHERE username = :u", params=dict(u=st.session_state.username), ttl=5)
    is_individually_muted = not user_mute_status.empty and pd.to_datetime(user_mute_status.iloc[0]['muted_until']) > datetime.now()
    
    # Determine if chat input should be disabled
    is_admin = st.session_state.role == 'admin'
    chat_disabled = (is_globally_muted and not is_admin) or is_individually_muted
    
    # Display appropriate message or input box
    if is_globally_muted and not is_admin:
        st.info("The chat is currently muted by an administrator. Please try again later.", icon="🔇")
    elif is_individually_muted:
        mute_end_time = pd.to_datetime(user_mute_status.iloc[0]['muted_until']).strftime('%I:%M %p')
        st.error(f"You have been muted by an administrator. You can chat again after {mute_end_time}.", icon="🔇")

    prompt = st.chat_input("Share your thoughts...", disabled=chat_disabled)
    if prompt:
        sentiment_score = analyze_sentiment(prompt)
        with conn.session as s:
            s.execute(text("INSERT INTO messages (username, avatar, message, timestamp, sentiment) VALUES (:u, :a, :m, :ts, :senti);"),
                      params=dict(u=st.session_state.username, a=st.session_state.avatar, m=prompt, ts=datetime.now(), senti=sentiment_score))
            s.commit()
        st.rerun()


# --- Main App Logic ---
def main():
    download_nltk_data()
    init_db()

    if 'screen' not in st.session_state:
        st.session_state.screen = "welcome"

    screen = st.session_state.screen
    if screen == "welcome":
        show_welcome_screen()
    elif screen == "login":
        show_login_screen()
    elif screen == "register":
        show_register_screen()
    elif screen == "guest_setup":
        show_guest_setup_screen()
    elif screen == "chat":
        show_chat_screen()

if __name__ == "__main__":
    main()
