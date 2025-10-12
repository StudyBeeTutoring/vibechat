# Fullstack Chat Application: "Aura"
# A modern, secure, and feature-rich chat application built with Streamlit.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
import time
from streamlit_autorefresh import st_autorefresh
import hashlib
import bleach  # For sanitizing user input to prevent XSS attacks
from textblob import TextBlob
import nltk

# --- Initial Setup: NLTK Data Download ---
# This ensures the sentiment analysis tokenizer is available.
@st.cache_resource
def download_nltk_data():
    """Download the NLTK 'punkt' tokenizer if not already present."""
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)

# --- Constants and Configuration ---
APP_NAME = "Aura"
# It's highly recommended to set these in Streamlit's secrets management (secrets.toml)
SUPER_ADMIN_USERNAME = st.secrets.get("SUPER_ADMIN_USERNAME", "admin")
SUPER_ADMIN_DEFAULT_PASS = st.secrets.get("SUPER_ADMIN_DEFAULT_PASS", "aura_admin_123")
APP_SALT = st.secrets.get("APP_SALT", "a_very_secret_and_secure_salt_string")

AVATARS = {
    "Wave": "🌊", "Star": "⭐", "Quill": "✒️", "Pixel": "👾",
    "Anchor": "⚓", "Compass": "🧭", "Atom": "⚛️", "Sprout": "🌱"
}

# --- Page and Style Configuration ---
st.set_page_config(page_title=APP_NAME, page_icon="💬", layout="centered")

# --- MODERN UI STYLES (Baby Blue Theme) ---
st.markdown("""
    <!-- Import Google Font and Icons -->
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap">
    <link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">

    <style>
        /* Specific rule to fix icon rendering */
        [data-testid="stSelectbox"] span, [data-testid="stExpanderHeader"] span {
            font-family: 'Material Icons' !important;
        }

        /* Main App & Text */
        html, body, [class*="st-"] {
            font-family: 'Poppins', sans-serif;
        }
        .stApp {
            background-color: #E0F7FA; /* Light baby blue */
        }
        p, h1, h2, h3, h4, h5, h6 {
            color: #01579B; /* Darker blue for text */
        }
        
        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF;
            border-right: 2px solid #B3E5FC;
        }

        /* Custom Title */
        .aura-title {
            font-size: 4rem;
            font-weight: 700;
            text-align: center;
            padding-bottom: 0.5rem;
            background: -webkit-linear-gradient(45deg, #0288D1, #26C6DA);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        /* Welcome/Login Card */
        .welcome-card {
            background-color: #FFFFFF;
            padding: 2.5rem;
            border-radius: 20px;
            box-shadow: 0 8px 30px rgba(0,0,0,0.08);
            border: 1px solid #B3E5FC;
        }

        /* Buttons */
        .stButton button {
            background-color: #0288D1; /* Primary blue */
            color: #FFFFFF;
            border: none;
            border-radius: 12px;
            padding: 14px 24px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(2, 136, 209, 0.2);
        }
        .stButton button:hover {
            background-color: #01579B; /* Darker blue on hover */
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(1, 87, 155, 0.3);
        }
        .stButton button:active {
            transform: translateY(0);
        }
        
        /* Text Inputs & Select Boxes */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
            background-color: #FFFFFF;
            border: 2px solid #B3E5FC;
            border-radius: 12px;
            color: #01579B;
        }
        .stTextInput input:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within {
            border-color: #0288D1;
            box-shadow: 0 0 0 3px rgba(2, 136, 209, 0.2);
        }
        
        /* Chat Area */
        .stChatInput {
            background-color: #FFFFFF;
            border-top: 2px solid #B3E5FC;
        }

        /* Custom Chat Bubbles */
        .chat-bubble {
            padding: 0.9rem 1.3rem;
            border-radius: 25px;
            margin-bottom: 0.75rem;
            max-width: 70%;
            box-shadow: 0 4px 10px rgba(0,0,0,0.05);
            display: inline-block;
            word-wrap: break-word;
        }
        .chat-bubble.other-user {
            background-color: #FFFFFF;
            border: 1px solid #B3E5FC;
            border-bottom-left-radius: 5px;
        }
        .chat-bubble.current-user {
            background-color: #0288D1; /* Primary blue */
            color: white;
            border-bottom-right-radius: 5px;
        }
        .message-container {
            display: flex;
            width: 100%;
            margin-bottom: 0.5rem;
            align-items: flex-end; /* Align avatar and bubble nicely */
        }
        .message-container.current-user {
            justify-content: flex-end;
        }
        .message-container.other-user {
            justify-content: flex-start;
        }
        .avatar {
            font-size: 1.5rem;
            margin: 0 0.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# --- Database Setup and Helpers ---
conn = st.connection("chat_db", type="sql", url="sqlite:///aura_app.db")

def init_db():
    """Initializes the database with required tables and default admin user."""
    with conn.session as s:
        s.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, hashed_password TEXT NOT NULL, avatar TEXT, role TEXT DEFAULT 'user', status TEXT DEFAULT 'active');"))
        s.execute(text("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, username TEXT, avatar TEXT, message TEXT, timestamp DATETIME, sentiment REAL);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS app_state (key TEXT PRIMARY KEY, value TEXT);"))
        s.execute(text("CREATE TABLE IF NOT EXISTS muted_users (username TEXT PRIMARY KEY, muted_until DATETIME NOT NULL);"))
        
        admin_user = s.execute(text("SELECT 1 FROM users WHERE username = :user;"), params=dict(user=SUPER_ADMIN_USERNAME)).fetchone()
        if not admin_user:
            hashed_pass = hash_password(SUPER_ADMIN_DEFAULT_PASS)
            s.execute(text("INSERT INTO users (username, hashed_password, avatar, role, status) VALUES (:user, :hp, '👑', 'admin', 'active');"), params=dict(user=SUPER_ADMIN_USERNAME, hp=hashed_pass))
        
        s.execute(text("INSERT OR IGNORE INTO app_state (key, value) VALUES ('chat_mute_until', '2000-01-01 00:00:00');"))
        s.execute(text("INSERT OR IGNORE INTO app_state (key, value) VALUES ('guest_login_disabled', 'false');"))
        s.commit()

# --- Security and Utility Functions ---
def sanitize_input(raw_input):
    """Sanitizes user input to prevent XSS attacks."""
    return bleach.clean(raw_input)

def hash_password(password):
    """Hashes a password with a salt using SHA256."""
    return hashlib.sha256((password + APP_SALT).encode()).hexdigest()

def verify_password(stored_hash, provided_password):
    """Verifies a provided password against a stored hash."""
    return stored_hash == hash_password(provided_password)

def clear_old_messages():
    """Deletes messages older than 1 hour to keep the chat fresh."""
    cutoff_time = datetime.now() - timedelta(hours=1)
    with conn.session as s:
        s.execute(text("DELETE FROM messages WHERE timestamp < :cutoff;"), params=dict(cutoff=cutoff_time))
        s.commit()

def analyze_sentiment(text_message):
    """Analyzes the sentiment polarity of a message."""
    return TextBlob(text_message).sentiment.polarity

# --- Cached Data Fetching ---
@st.cache_data(ttl=5)
def get_app_state():
    """Fetches global app state from the database."""
    return conn.query("SELECT key, value FROM app_state;", ttl=0)

@st.cache_data(ttl=3)
def get_all_messages():
    """Fetches all recent messages."""
    return conn.query("SELECT * FROM messages ORDER BY timestamp ASC;", ttl=0)

@st.cache_data(ttl=10)
def get_all_users_for_admin():
    """Fetches all registered and active guest users for the admin panel."""
    registered = conn.query("SELECT username, avatar, role, status FROM users WHERE username != :admin;", params=dict(admin=SUPER_ADMIN_USERNAME), ttl=0)
    cutoff = datetime.now() - timedelta(hours=1)
    guests = conn.query("SELECT DISTINCT username, avatar FROM messages WHERE username LIKE '%(Guest)' AND timestamp > :time;", params=dict(time=cutoff), ttl=0)
    guests['role'], guests['status'] = 'guest', 'active'
    return pd.concat([registered, guests]).drop_duplicates(subset=['username'])

@st.cache_data(ttl=5)
def get_user_mute_status(username):
    """Checks if a specific user is currently muted."""
    return conn.query("SELECT muted_until FROM muted_users WHERE username = :u AND muted_until > :now", params=dict(u=username, now=datetime.now()), ttl=0)

# --- UI Screens ---
def show_welcome_screen():
    st.markdown(f'<p class="aura-title">{APP_NAME}</p>', unsafe_allow_html=True)
    st.subheader("A modern space for fleeting thoughts.", anchor=False, divider="rainbow")
    st.write("")
    
    with st.container(border=False):
        st.markdown('<div class="welcome-card">', unsafe_allow_html=True)
        col1, col2 = st.columns([1, 1])
        with col1:
            st.write("Join a conversation where every message is ephemeral. Share your ideas, chat with friends, and enjoy a clean, clutter-free space. Messages disappear after one hour.")
        with col2:
            st.subheader("Get Started", anchor=False)
            if st.button("🔒 Login", use_container_width=True):
                st.session_state.screen = "login"; st.rerun()
            if st.button("✍️ Register", use_container_width=True):
                st.session_state.screen = "register"; st.rerun()
            
            app_state = get_app_state()
            guest_disabled = app_state[app_state['key'] == 'guest_login_disabled'].iloc[0]['value'] == 'true'
            if not guest_disabled:
                if st.button("👤 Continue as Guest", use_container_width=True):
                    st.session_state.screen = "guest_setup"; st.rerun()
            else:
                st.info("Guest login is temporarily disabled by an admin.", icon="🚫")
        st.markdown('</div>', unsafe_allow_html=True)

def show_login_screen():
    with st.container():
        st.markdown('<div class="welcome-card">', unsafe_allow_html=True)
        st.markdown('<h2 style="text-align: center;">Login to Aura</h2>', unsafe_allow_html=True)
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Your username")
            password = st.text_input("Password", type="password", placeholder="Your password")
            submitted = st.form_submit_button("Login", use_container_width=True)
            if submitted:
                clean_username = sanitize_input(username)
                user = conn.query("SELECT * FROM users WHERE username = :u;", params=dict(u=clean_username), ttl=0)
                if not user.empty and verify_password(user.iloc[0]['hashed_password'], password):
                    user_data = user.iloc[0]
                    if user_data['status'] == 'banned':
                        st.error("This account has been banned.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.username = user_data['username']
                        st.session_state.avatar = user_data['avatar']
                        st.session_state.role = user_data['role']
                        st.session_state.screen = "chat"
                        
                        default_pass_hash = hash_password(SUPER_ADMIN_DEFAULT_PASS)
                        if user_data['role'] == 'admin' and user_data['hashed_password'] == default_pass_hash:
                            st.session_state.admin_using_default_pass = True
                        
                        st.success("Login successful!"); time.sleep(1.5); st.rerun()
                else:
                    st.error("Invalid username or password.")
        if st.button("← Back to Welcome", use_container_width=True):
            st.session_state.screen = "welcome"; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def show_register_screen():
    with st.container():
        st.markdown('<div class="welcome-card">', unsafe_allow_html=True)
        st.markdown('<h2 style="text-align: center;">Create an Account</h2>', unsafe_allow_html=True)
        with st.form("register_form"):
            username = st.text_input("Username", placeholder="Choose a unique username")
            password = st.text_input("Password", type="password", placeholder="Choose a secure password")
            avatar_label = st.selectbox("Choose Your Avatar", options=list(AVATARS.keys()))
            submitted = st.form_submit_button("Register", use_container_width=True)
            if submitted:
                clean_username = sanitize_input(username)
                if not clean_username or not password:
                    st.warning("Please fill out all fields.")
                else:
                    try:
                        with conn.session as s:
                            s.execute(text("INSERT INTO users (username, hashed_password, avatar) VALUES (:u, :hp, :a);"), params=dict(u=clean_username, hp=hash_password(password), a=AVATARS[avatar_label]))
                            s.commit()
                        st.success("Registration successful! Please log in."); time.sleep(1.5)
                        st.session_state.screen = "login"; st.rerun()
                    except Exception as e:
                        if "UNIQUE constraint failed" in str(e):
                            st.error("Username already exists.")
                        else: st.error("An unexpected error occurred.")
        if st.button("← Back to Welcome", use_container_width=True):
            st.session_state.screen = "welcome"; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def show_guest_setup_screen():
    with st.container():
        st.markdown('<div class="welcome-card">', unsafe_allow_html=True)
        st.markdown('<h2 style="text-align: center;">Guest Setup</h2>', unsafe_allow_html=True)
        with st.form("guest_form"):
            username = st.text_input("Guest Username", placeholder="Enter a temporary name")
            avatar_label = st.selectbox("Choose Your Avatar", options=list(AVATARS.keys()))
            submitted = st.form_submit_button("Enter Chat", use_container_width=True)
            if submitted:
                clean_username = sanitize_input(username)
                if not clean_username:
                    st.warning("Please enter a username.")
                else:
                    user_exists = conn.query("SELECT 1 FROM users WHERE username = :u", params=dict(u=clean_username), ttl=0)
                    if not user_exists.empty:
                        st.error("This name is taken by a registered user. Please choose another.")
                    else:
                        st.session_state.logged_in = True
                        st.session_state.username = f"{clean_username} (Guest)"
                        st.session_state.avatar = AVATARS[avatar_label]
                        st.session_state.role = "guest"
                        st.session_state.screen = "chat"
                        st.rerun()
        if st.button("← Back to Welcome", use_container_width=True):
            st.session_state.screen = "welcome"; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def show_admin_dashboard():
    st.subheader("🛡️ Admin Panel", anchor=False)
    with st.expander("🌐 Global Chat Controls", expanded=True):
        app_state = get_app_state()
        chat_mute_until = pd.to_datetime(app_state[app_state['key'] == 'chat_mute_until'].iloc[0]['value'])
        
        if chat_mute_until > datetime.now():
            st.warning(f"Chat is globally muted until {chat_mute_until.strftime('%H:%M:%S')}", icon="🔇")
            if st.button("Lift Mute"):
                with conn.session as s: s.execute(text("UPDATE app_state SET value = :val WHERE key = 'chat_mute_until'"), params=dict(val=datetime.now() - timedelta(minutes=1))); s.commit()
                st.rerun()
        else:
            duration = st.selectbox("Mute entire chat for:", options=["5 Minutes", "15 Minutes", "1 Hour"], key="global_mute_dur")
            if st.button("Mute Entire Chat"):
                duration_map = {"5 Minutes": 5, "15 Minutes": 15, "1 Hour": 60}
                mute_end = datetime.now() + timedelta(minutes=duration_map[duration])
                with conn.session as s: s.execute(text("UPDATE app_state SET value = :val WHERE key = 'chat_mute_until'"), params=dict(val=mute_end)); s.commit()
                st.rerun()

        guest_disabled = app_state[app_state['key'] == 'guest_login_disabled'].iloc[0]['value'] == 'true'
        if guest_disabled:
            if st.button("✅ Enable Guest Login"):
                with conn.session as s: s.execute(text("UPDATE app_state SET value='false' WHERE key='guest_login_disabled'")); s.commit()
                st.rerun()
        else:
            if st.button("🚫 Disable Guest Login", type="primary"):
                with conn.session as s: s.execute(text("UPDATE app_state SET value='true' WHERE key='guest_login_disabled'")); s.commit()
                st.rerun()
    
    with st.expander("👥 User Management"):
        all_users = get_all_users_for_admin()
        muted_users = conn.query("SELECT username FROM muted_users WHERE muted_until > :now", params=dict(now=datetime.now()), ttl=5)['username'].tolist()
        
        if all_users.empty: st.write("No other active users found.")
        
        for _, user in all_users.iterrows():
            is_muted = user['username'] in muted_users
            st.markdown(f"**{user['avatar']} {user['username']}** (`{user['role']}`)")
            c1, c2 = st.columns(2)
            with c1:
                if is_muted:
                    if st.button("Unmute", key=f"unmute_{user['username']}", use_container_width=True):
                        with conn.session as s: s.execute(text("DELETE FROM muted_users WHERE username = :u"), params=dict(u=user['username'])); s.commit()
                        st.rerun()
                else:
                    if st.button("Mute (15 min)", key=f"mute_{user['username']}", use_container_width=True):
                        end = datetime.now() + timedelta(minutes=15)
                        with conn.session as s: s.execute(text("INSERT OR REPLACE INTO muted_users (username, muted_until) VALUES (:u, :end)"), params=dict(u=user['username'], end=end)); s.commit()
                        st.rerun()
            if user['role'] != 'guest':
                with c2:
                    if user['status'] == 'active':
                        if st.button("Ban", key=f"ban_{user['username']}", type="primary", use_container_width=True):
                            with conn.session as s: s.execute(text("UPDATE users SET status = 'banned' WHERE username = :u"), params=dict(u=user['username'])); s.commit()
                            st.rerun()
                    else:
                        if st.button("Unban", key=f"unban_{user['username']}", use_container_width=True):
                            with conn.session as s: s.execute(text("UPDATE users SET status = 'active' WHERE username = :u"), params=dict(u=user['username'])); s.commit()
                            st.rerun()
            st.markdown("---")

def show_chat_screen():
    clear_old_messages()
    st_autorefresh(interval=5000, limit=None, key="chat_refresh")

    with st.sidebar:
        st.title(f"{st.session_state.avatar} {st.session_state.username}")
        st.caption(f"Role: {st.session_state.role.capitalize()}")
        if st.button("Log Out", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()
        
        if st.session_state.role == 'admin':
            st.divider()
            if st.session_state.get("admin_using_default_pass", False):
                st.warning("You're using the default admin password. Please change it below.", icon="⚠️")
            show_admin_dashboard()
    
    st.markdown(f'<p class="aura-title" style="font-size: 3rem;">{APP_NAME}</p>', unsafe_allow_html=True)
    
    chat_container = st.container(height=500, border=False)
    messages_df = get_all_messages()
    for _, row in messages_df.iterrows():
        is_current_user = row["username"] == st.session_state.username
        align_class = "current-user" if is_current_user else "other-user"
        
        with chat_container:
            col1, col2 = st.columns([1, 10]) if not is_current_user else st.columns([10, 1])
            avatar_col = col1 if not is_current_user else col2
            message_col = col2 if not is_current_user else col1
            
            with avatar_col:
                st.markdown(f"<div class='avatar'>{row['avatar']}</div>", unsafe_allow_html=True)
            with message_col:
                bubble_html = f"""
                <div class="message-container {align_class}">
                    <div class="chat-bubble {align_class}">
                        <b style="font-weight: 600;">{row['username']}</b>
                        <p style="margin: 0; color: inherit;">{row['message']}</p>
                        <div style="font-size: 0.7rem; text-align: right; opacity: 0.8;">
                            {pd.to_datetime(row['timestamp']).strftime('%I:%M %p')}
                        </div>
                    </div>
                </div>"""
                st.markdown(bubble_html, unsafe_allow_html=True)

    # Check Mute Status
    app_state = get_app_state()
    global_mute_until = pd.to_datetime(app_state[app_state['key'] == 'chat_mute_until'].iloc[0]['value'])
    is_globally_muted = global_mute_until > datetime.now()
    user_mute_status = get_user_mute_status(st.session_state.username)
    is_individually_muted = not user_mute_status.empty
    
    chat_disabled = (is_globally_muted and st.session_state.role != 'admin') or is_individually_muted
    
    if is_globally_muted and st.session_state.role != 'admin':
        st.info("The chat is currently muted by an administrator.", icon="🔇")
    elif is_individually_muted:
        mute_end_time = pd.to_datetime(user_mute_status.iloc[0]['muted_until']).strftime('%I:%M %p')
        st.error(f"You have been muted. You can chat again after {mute_end_time}.", icon="🔇")

    # Anti-Spam Rate Limiting
    if 'last_message_time' not in st.session_state:
        st.session_state.last_message_time = datetime.min
    
    time_since_last_message = (datetime.now() - st.session_state.last_message_time).total_seconds()
    is_rate_limited = time_since_last_message < 3.0 # 3 second cooldown

    prompt = st.chat_input("Share a thought...", disabled=chat_disabled or is_rate_limited)
    if prompt:
        clean_prompt = sanitize_input(prompt)
        sentiment_score = analyze_sentiment(clean_prompt)
        with conn.session as s:
            s.execute(text("INSERT INTO messages (username, avatar, message, timestamp, sentiment) VALUES (:u, :a, :m, :ts, :senti);"),
                      params=dict(u=st.session_state.username, a=st.session_state.avatar, m=clean_prompt, ts=datetime.now(), senti=sentiment_score))
            s.commit()
        st.session_state.last_message_time = datetime.now()
        st.rerun()

# --- Main App Logic ---
def main():
    download_nltk_data()
    init_db()

    if 'screen' not in st.session_state:
        st.session_state.screen = "welcome"

    screen = st.session_state.screen
    
    if screen == "chat":
        show_chat_screen()
    elif screen == "login":
        show_login_screen()
    elif screen == "register":
        show_register_screen()
    elif screen == "guest_setup":
        show_guest_setup_screen()
    else:
        show_welcome_screen()

if __name__ == "__main__":
    main()
