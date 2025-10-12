import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
import time
from streamlit_autorefresh import st_autorefresh
import hashlib
from textblob import TextBlob
import nltk

# --- Initial Setup: NLTK Data Download ---
@st.cache_resource
def download_nltk_data():
    """Download the NLTK 'punkt' tokenizer if not already present."""
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')

# --- Constants and Configuration ---
APP_NAME = "Crème"
SUPER_ADMIN_USERNAME = st.secrets.get("SUPER_ADMIN_USERNAME", "admin")
SUPER_ADMIN_DEFAULT_PASS = st.secrets.get("SUPER_ADMIN_DEFAULT_PASS", "creme_admin_123")
APP_SALT = st.secrets.get("APP_SALT", "default_salt_string_for_testing")

AVATARS = {
    "Latte": "☕", "Macaron": "🍬", "Moon": "🌙", "Cloud": "☁️",
    "Feather": "🪶", "Dove": "🕊️", "Lotus": "🌸", "Harp": "🎼"
}

# --- Page and Style Configuration ---
st.set_page_config(page_title=APP_NAME, page_icon="🍦", layout="wide")

# --- STYLES: The Complete UI Overhaul ---
# --- STYLES: The Complete UI Overhaul ---
st.markdown("""
    <!-- 1. Font Imports: Using <link> for better loading -->
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;700&display=swap">
    <link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">

    <style>
        /* 2. Specific rule for icons to override the general font */
        .st-emotion-cache-1oe5k7p, .st-emotion-cache-19rxjzo, [data-testid="stTickData"], [data-testid="stMetricValue"], [data-testid="stImage"] {
            font-family: 'Material Icons', sans-serif !important;
        }

        /* Main App & Text */
        html, body, [class*="st-"] {
            font-family: 'Quicksand', sans-serif;
        }
        .stApp {
            background-color: #FDF5E6; /* A warmer, softer cream */
        }
        p, h1, h2, h3, h4, h5, h6, .st-emotion-cache-16idsys p {
            color: #5E454B; /* A warm, dark brown for text */
        }
        
        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-right: 2px solid #F5EADD;
        }

        /* Custom Title with a new gradient */
        .creme-title {
            font-size: 4rem;
            font-weight: 700;
            padding-bottom: 0.5rem;
            background: -webkit-linear-gradient(45deg, #EABBAA, #D4A3A3);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        /* Welcome Screen Card */
        .welcome-card {
            background-color: #FFFFFF;
            padding: 2.5rem;
            border-radius: 15px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.05);
            border: 1px solid #F5EADD;
        }

        /* Buttons */
        .stButton button {
            background-color: #A68A64; /* Muted coffee brown */
            color: #FFFFFF;
            border: none;
            border-radius: 10px;
            padding: 12px 20px;
            font-weight: 500;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .stButton button:hover {
            background-color: #5E454B; /* Darker brown on hover */
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }
        .stButton button:active {
            background-color: #5E454B;
            transform: translateY(0);
        }
        
        /* Text Inputs & Select Boxes */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
            background-color: #FDF5E6; /* Match app background */
            border: 1px solid #EAE0D5;
            border-radius: 10px;
            color: #5E454B;
        }
        
        /* Chat Area */
        .stChatInput {
            background-color: #FDF5E6;
            border-top: 2px solid #F5EADD;
        }

        /* Custom Chat Bubbles */
        .chat-bubble {
            padding: 0.8rem 1.2rem;
            border-radius: 20px;
            margin-bottom: 0.5rem;
            max-width: 75%;
            box-shadow: 0 2px 4px rgba(0,0,0,0.04);
            display: inline-block; /* Allows bubble to fit content */
        }
        .chat-bubble.user {
            background-color: #FFFFFF;
            border: 1px solid #F5EADD;
            border-bottom-left-radius: 5px;
        }
        .chat-bubble.current-user {
            background-color: #D4A3A3; /* A soft, dusty rose */
            color: white;
            border-bottom-right-radius: 5px;
        }
        .message-container {
            display: flex;
            width: 100%;
            margin-bottom: 0.5rem;
        }
        .message-container.current-user {
            justify-content: flex-end; /* Align to the right */
        }
        .message-container.user {
            justify-content: flex-start; /* Align to the left */
        }
    </style>
""", unsafe_allow_html=True)

# --- Database Setup and Helpers ---
conn = st.connection("chat_db", type="sql", url="sqlite:///creme_app.db")

def init_db():
    """Initializes the database with required tables and default admin user."""
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, hashed_password TEXT NOT NULL, avatar TEXT, role TEXT DEFAULT 'user', status TEXT DEFAULT 'active');"))
        s.execute(text("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, username TEXT, avatar TEXT, message TEXT, timestamp DATETIME, sentiment REAL DEFAULT 0.0);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS muted_users (username TEXT PRIMARY KEY, muted_until DATETIME NOT NULL);"))
        
        admin_user = s.execute(text("SELECT * FROM users WHERE username = :user;"), params=dict(user=SUPER_ADMIN_USERNAME)).fetchone()
        if not admin_user:
            hashed_pass = hash_password(SUPER_ADMIN_DEFAULT_PASS)
            s.execute(text("INSERT INTO users (username, hashed_password, avatar, role, status) VALUES (:user, :hp, '👑', 'admin', 'active');"), params=dict(user=SUPER_ADMIN_USERNAME, hp=hashed_pass))
        
        s.execute(text("INSERT OR IGNORE INTO app_state (key, value) VALUES ('chat_mute_until', '2000-01-01 00:00:00');"))
        s.execute(text("INSERT OR IGNORE INTO app_state (key, value) VALUES ('guest_login_disabled', 'false');"))
        s.commit()

# --- Security and Utility Functions ---
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

# --- Cached Data Fetching Functions ---
@st.cache_data(ttl=5)
def get_app_state():
    return conn.query("SELECT key, value FROM app_state;", ttl=0)

@st.cache_data(ttl=5)
def get_all_messages():
    return conn.query("SELECT * FROM messages ORDER BY timestamp ASC;", ttl=0)

@st.cache_data(ttl=10)
def get_all_users_for_admin():
    registered_users = conn.query("SELECT username, avatar, role, status FROM users WHERE username != :admin ORDER BY username;", params=dict(admin=SUPER_ADMIN_USERNAME), ttl=0)
    guest_users = conn.query("SELECT DISTINCT username, avatar FROM messages WHERE username LIKE '%(Guest)' AND timestamp > :time;", params=dict(time=datetime.now() - timedelta(hours=1)), ttl=0)
    guest_users['role'], guest_users['status'] = 'guest', 'active'
    return pd.concat([registered_users, guest_users]).drop_duplicates(subset=['username'])

@st.cache_data(ttl=5)
def get_muted_users_list():
    return list(conn.query("SELECT username FROM muted_users WHERE muted_until > :now", params=dict(now=datetime.now()), ttl=0)['username'])

@st.cache_data(ttl=5)
def get_user_mute_status(username):
    return conn.query("SELECT muted_until FROM muted_users WHERE username = :u", params=dict(u=username), ttl=0)


# --- UI Screens ---
def show_welcome_screen():
    _, center_col, _ = st.columns([1, 1.5, 1])
    with center_col:
        st.markdown(f'<div style="text-align: center;"><p class="creme-title">{APP_NAME}</p></div>', unsafe_allow_html=True)
        st.subheader("A soft place to land your thoughts.", anchor=False, divider="rainbow")
        st.write("")
    
    col1, col2 = st.columns([1.5, 1], gap="large")
    with col1:
        st.write("Join our cozy corner of the internet. Share your ideas, catch up with friends, or simply unwind. Messages here are ephemeral, disappearing after an hour to keep things fresh and light.")

    with col2:
        st.markdown('<div class="welcome-card">', unsafe_allow_html=True)
        st.subheader("Get Started", anchor=False)
        if st.button("🔒 Login", use_container_width=True):
            st.session_state.screen = "login"; st.rerun()
        if st.button("✍️ Register", use_container_width=True):
            st.session_state.screen = "register"; st.rerun()
        
        app_state_df = get_app_state()
        guest_disabled_row = app_state_df[app_state_df['key'] == 'guest_login_disabled']
        guest_disabled = not guest_disabled_row.empty and guest_disabled_row.iloc[0]['value'] == 'true'
        
        if not guest_disabled:
            if st.button("👤 Continue as Guest", use_container_width=True):
                st.session_state.screen = "guest_setup"; st.rerun()
        else:
            st.info("Guest login is temporarily disabled.", icon="🚫")
        st.markdown('</div>', unsafe_allow_html=True)

def show_login_screen():
    st.markdown(f'<p class="creme-title" style="text-align: center; font-size: 3rem;">Login</p>', unsafe_allow_html=True)
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Your username")
        password = st.text_input("Password", type="password", placeholder="Your password")
        submitted = st.form_submit_button("Login", use_container_width=True)
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
                    
                    default_pass_hash = hash_password(SUPER_ADMIN_DEFAULT_PASS)
                    if user.role == 'admin' and user.hashed_password == default_pass_hash:
                        st.session_state.admin_using_default_pass = True

                    st.success("Login successful!")
                    time.sleep(1.5)
                    st.rerun()
            else:
                st.error("Invalid username or password.")
    if st.button("← Back to Welcome", use_container_width=True):
        st.session_state.screen = "welcome"
        st.rerun()

def show_register_screen():
    st.markdown(f'<p class="creme-title" style="text-align: center; font-size: 3rem;">Register</p>', unsafe_allow_html=True)
    with st.form("register_form"):
        username = st.text_input("Username", placeholder="Choose a unique username")
        password = st.text_input("Password", type="password", placeholder="Choose a secure password")
        avatar_label = st.selectbox("Choose Your Avatar", options=list(AVATARS.keys()))
        submitted = st.form_submit_button("Register", use_container_width=True)
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
                    time.sleep(1.5)
                    st.session_state.screen = "login"
                    st.rerun()
                except Exception as e:
                    if "UNIQUE constraint failed" in str(e):
                        st.error("Username already exists.")
                    else: st.error(f"An error occurred: {e}")
    if st.button("← Back to Welcome", use_container_width=True):
        st.session_state.screen = "welcome"
        st.rerun()

def show_guest_setup_screen():
    st.markdown(f'<p class="creme-title" style="text-align: center; font-size: 3rem;">Guest Setup</p>', unsafe_allow_html=True)
    with st.form("guest_form"):
        username = st.text_input("Guest Username", placeholder="Enter a temporary name")
        avatar_label = st.selectbox("Choose Your Avatar", options=list(AVATARS.keys()))
        submitted = st.form_submit_button("Enter Chat", use_container_width=True)
        if submitted:
            if not username:
                st.warning("Please enter a username.")
            else:
                user_exists = conn.query("SELECT 1 FROM users WHERE username = :u", params=dict(u=username), ttl=0)
                if not user_exists.empty:
                    st.error("This username is taken by a registered user. Please choose another.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.username = f"{username} (Guest)"
                    st.session_state.avatar = AVATARS[avatar_label]
                    st.session_state.role = "guest"
                    st.session_state.screen = "chat"
                    st.rerun()
    if st.button("← Back to Welcome", use_container_width=True):
        st.session_state.screen = "welcome"
        st.rerun()

def show_change_password_form(username_to_change, is_admin_reset=False):
    if not is_admin_reset and username_to_change != st.session_state.get("username"):
        st.error("You are not authorized to perform this action.")
        return

    form_key = f"change_pass_{username_to_change}"
    if is_admin_reset:
        st.write(f"Set a new password for '{username_to_change}':")
    else:
        st.subheader("🔑 Change Your Password", anchor=False)
        
    with st.form(form_key):
        if not is_admin_reset:
            current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Change Password")
        if submitted:
            if not is_admin_reset:
                user = conn.query("SELECT hashed_password FROM users WHERE username = :u", params=dict(u=username_to_change), ttl=0).iloc[0]
                if not verify_password(user['hashed_password'], current_password):
                    st.error("Current password is incorrect."); return
            
            if new_password != confirm_password: st.error("New passwords do not match.")
            elif len(new_password) < 6: st.error("New password must be at least 6 characters long.")
            else:
                new_hashed_password = hash_password(new_password)
                with conn.session as s:
                    s.execute(text("UPDATE users SET hashed_password = :hp WHERE username = :u"), params=dict(hp=new_hashed_password, u=username_to_change))
                    s.commit()
                st.success(f"Password for '{username_to_change}' changed successfully!")
                if not is_admin_reset and st.session_state.get("admin_using_default_pass"):
                    st.session_state.admin_using_default_pass = False
                time.sleep(1.5); st.rerun()

def show_admin_dashboard():
    with st.expander("🌐 **Global Chat Controls**", expanded=True):
        app_state_df = get_app_state()
        chat_mute_row = app_state_df[app_state_df['key'] == 'chat_mute_until']
        chat_mute_until = pd.to_datetime(chat_mute_row.iloc[0]['value']) if not chat_mute_row.empty else datetime.now()
        
        if chat_mute_until > datetime.now():
            st.warning(f"Chat is globally muted until {chat_mute_until.strftime('%H:%M:%S')}", icon="🔇")
            if st.button("Lift Mute", use_container_width=True):
                with conn.session as s: s.execute(text("UPDATE app_state SET value = :val WHERE key = 'chat_mute_until'"), params=dict(val=datetime.now() - timedelta(minutes=1))); s.commit()
                st.rerun()
        else:
            with st.form("mute_chat_form"):
                duration_map = {"5 Minutes": 5, "15 Minutes": 15, "1 Hour": 60, "8 Hours": 480}
                duration = st.selectbox("Select mute duration:", options=duration_map.keys())
                submitted = st.form_submit_button("Mute Entire Chat")
                if submitted:
                    mute_end_time = datetime.now() + timedelta(minutes=duration_map[duration])
                    with conn.session as s: s.execute(text("UPDATE app_state SET value = :val WHERE key = 'chat_mute_until'"), params=dict(val=mute_end_time)); s.commit()
                    st.rerun()

        guest_disabled_row = app_state_df[app_state_df['key'] == 'guest_login_disabled']
        guest_disabled_val = guest_disabled_row.iloc[0]['value'] if not guest_disabled_row.empty else 'false'
        if guest_disabled_val == 'true':
            if st.button("✅ Enable Guest Login", use_container_width=True):
                with conn.session as s: s.execute(text("UPDATE app_state SET value='false' WHERE key='guest_login_disabled'")); s.commit()
                st.rerun()
        else:
            if st.button("🚫 Disable Guest Login", use_container_width=True, type="primary"):
                with conn.session as s: s.execute(text("UPDATE app_state SET value='true' WHERE key='guest_login_disabled'")); s.commit()
                st.rerun()

        st.divider()
        if st.session_state.get("confirm_delete_all_messages", False):
            st.warning("**Are you sure?** This will permanently delete all messages.", icon="⚠️")
            c1, c2 = st.columns(2)
            if c1.button("Yes, Delete Everything", use_container_width=True, type="primary"):
                with conn.session as s: s.execute(text("DELETE FROM messages;")); s.commit()
                st.session_state.confirm_delete_all_messages = False
                st.toast("Chat history cleared!")
                time.sleep(1.5); st.rerun()
            if c2.button("Cancel", use_container_width=True):
                st.session_state.confirm_delete_all_messages = False; st.rerun()
        else:
            if st.button("🗑️ Clear All Messages", use_container_width=True):
                st.session_state.confirm_delete_all_messages = True; st.rerun()

    with st.expander("👥 **User Management**"):
        all_users = get_all_users_for_admin()
        muted_users = get_muted_users_list()
        
        if all_users.empty:
            st.write("No other active users found.")

        for _, user in all_users.iterrows():
            is_muted = user.username in muted_users
            status_text = f"Status: **{user.status.capitalize()}**"
            if is_muted: status_text += " / **Muted** 🔇"
            st.markdown(f"**{user.avatar} {user.username}** (`{user.role}`)<br>{status_text}", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            with c1:
                if is_muted:
                    if st.button("Unmute", key=f"unmute_{user.username}", use_container_width=True):
                        with conn.session as s: s.execute(text("DELETE FROM muted_users WHERE username = :u"), params=dict(u=user.username)); s.commit()
                        st.rerun()
                else:
                    with st.popover("Mute", use_container_width=True):
                        with st.form(f"mute_form_{user.username}"):
                            d_map = {"5 Minutes": 5, "1 Hour": 60, "24 Hours": 1440}
                            dur = st.selectbox("Mute for:", options=d_map.keys(), key=f"mdur_{user.username}")
                            if st.form_submit_button("Confirm Mute"):
                                end = datetime.now() + timedelta(minutes=d_map[dur])
                                with conn.session as s: s.execute(text("INSERT OR REPLACE INTO muted_users (username, muted_until) VALUES (:u, :end)"), params=dict(u=user.username, end=end)); s.commit()
                                st.rerun()
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

def show_chat_screen():
    clear_old_messages()
    st_autorefresh(interval=5000, limit=None, key="chat_refresh")

    if st.session_state.get("admin_using_default_pass", False):
        st.warning("🚨 **Security Alert:** You are using the default admin password. Please change it immediately.", icon="⚠️")
    
    with st.sidebar:
        st.title(f"{st.session_state.avatar} {st.session_state.username}", anchor=False)
        st.caption(f"Role: {st.session_state.role.capitalize()}")
        if st.button("Log Out"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()
        
        if st.session_state.role == 'admin':
            st.divider()
            st.subheader("🛡️ Admin Panel", anchor=False)
            show_admin_dashboard()
            st.divider()
            with st.expander("🔑 Change Your Password"):
                show_change_password_form(st.session_state.username)

    _, center_col, _ = st.columns([1, 6, 1])
    with center_col:
        st.markdown(f'<p class="creme-title" style="text-align:center; font-size: 3rem;">{APP_NAME}</p>', unsafe_allow_html=True)
        st.caption("Messages are ephemeral and vanish after 1 hour.")

        chat_container = st.container(height=500, border=False)
        with chat_container:
            messages_df = get_all_messages()
            for _, row in messages_df.iterrows():
                is_current_user = row["username"] == st.session_state.username
                container_class = "current-user" if is_current_user else "user"
                bubble_class = "current-user" if is_current_user else "user"
                
                message_html = f"""
                    <div class="message-container {container_class}">
                        <div class="chat-bubble {bubble_class}">
                            <b>{row['avatar']} {row['username']} {get_sentiment_emoji(row['sentiment'])}</b>
                            <p style="margin: 0;">{row['message']}</p>
                            <div style="font-size: 0.7rem; opacity: 0.8; text-align: right;">
                                {pd.to_datetime(row['timestamp']).strftime('%I:%M %p')}
                            </div>
                        </div>
                    </div>"""
                st.markdown(message_html, unsafe_allow_html=True)

    app_state_df = get_app_state()
    chat_mute_row = app_state_df[app_state_df['key'] == 'chat_mute_until']
    is_globally_muted = not chat_mute_row.empty and pd.to_datetime(chat_mute_row.iloc[0]['value']) > datetime.now()
    
    user_mute_status = get_user_mute_status(st.session_state.username)
    is_individually_muted = not user_mute_status.empty and pd.to_datetime(user_mute_status.iloc[0]['muted_until']) > datetime.now()
    
    chat_disabled = (is_globally_muted and st.session_state.role != 'admin') or is_individually_muted
    
    if is_globally_muted and st.session_state.role != 'admin':
        st.info("The chat is currently muted by an administrator. Please try again later.", icon="🔇")
    elif is_individually_muted:
        mute_end_time = pd.to_datetime(user_mute_status.iloc[0]['muted_until']).strftime('%I:%M %p')
        st.error(f"You have been muted. You can chat again after {mute_end_time}.", icon="🔇")

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
    
    if screen in ["login", "register", "guest_setup"]:
        _, center_col, _ = st.columns([2, 1.5, 2])
        with center_col:
            if screen == "login": show_login_screen()
            elif screen == "register": show_register_screen()
            elif screen == "guest_setup": show_guest_setup_screen()
    elif screen == "chat":
        show_chat_screen()
    else:
        show_welcome_screen()

if __name__ == "__main__":
    main()
