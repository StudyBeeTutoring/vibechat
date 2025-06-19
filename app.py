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
    
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')


APP_NAME = "Crème"
SUPER_ADMIN_USERNAME = st.secrets["SUPER_ADMIN_USERNAME"]
SUPER_ADMIN_DEFAULT_PASS = st.secrets["SUPER_ADMIN_DEFAULT_PASS"]
APP_SALT = st.secrets["APP_SALT"]

AVATARS = {
    "Latte": "☕", "Macaron": "🍬", "Moon": "🌙", "Cloud": "☁️",
    "Feather": "🪶", "Dove": "🕊️", "Lotus": "🌸", "Harp": "🎼"
}


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




conn = st.connection("chat_db", type="sql", url="sqlite:///creme_app.db", ttl=0)

def init_db():
    with conn.session as s:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, hashed_password TEXT NOT NULL,
                avatar TEXT, role TEXT DEFAULT 'user', status TEXT DEFAULT 'active'
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, username TEXT, avatar TEXT,
                message TEXT, timestamp DATETIME, sentiment REAL DEFAULT 0.0
            );
        """))
        admin_user = s.execute(text("SELECT * FROM users WHERE username = :user;"), params=dict(user=SUPER_ADMIN_USERNAME)).fetchone()
        if not admin_user:
            hashed_pass = hash_password(SUPER_ADMIN_DEFAULT_PASS)
            s.execute(text("""
                INSERT INTO users (username, hashed_password, avatar, role, status)
                VALUES (:user, :hp, '👑', 'admin', 'active');
            """), params=dict(user=SUPER_ADMIN_USERNAME, hp=hashed_pass))
        s.commit()


def hash_password(password):
    return hashlib.sha256((password + APP_SALT).encode()).hexdigest()
def verify_password(stored_hash, provided_password):
    return stored_hash == hash_password(provided_password)
def clear_old_messages():
    cutoff_time = datetime.now() - timedelta(hours=1)
    with conn.session as s: s.execute(text("DELETE FROM messages WHERE timestamp < :cutoff;"), params=dict(cutoff=cutoff_time)); s.commit()
def analyze_sentiment(text_message):
    return TextBlob(text_message).sentiment.polarity
def get_sentiment_emoji(score):
    if score > 0.1: return "😊"
    elif score < -0.1: return "😠"
    else: return "😐"


def show_welcome_screen():
    st.markdown(f'<p class="creme-title">Welcome to {APP_NAME}</p>', unsafe_allow_html=True)
    st.caption("A soft place to land your thoughts.")
    st.write("")
    col1, col2, col3 = st.columns(3)
    if col1.button("🔒 Login", use_container_width=True): st.session_state.screen = "login"; st.rerun()
    if col2.button("✍️ Register", use_container_width=True): st.session_state.screen = "register"; st.rerun()
    if col3.button("👤 Continue as Guest", use_container_width=True): st.session_state.screen = "guest_setup"; st.rerun()

def show_login_screen():
    st.header("Login to Your Account")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            with conn.session as s: user = s.execute(text("SELECT * FROM users WHERE username = :u;"), params=dict(u=username)).fetchone()
            if user and verify_password(user.hashed_password, password):
                if user.status == 'banned': st.error("This account has been banned.")
                else:
                    st.session_state.logged_in = True; st.session_state.username = user.username; st.session_state.avatar = user.avatar; st.session_state.role = user.role; st.session_state.screen = "chat"
                    if user.role == 'admin' and verify_password(user.hashed_password, SUPER_ADMIN_DEFAULT_PASS): st.session_state.admin_using_default_pass = True
                    st.success("Login successful!"); time.sleep(1); st.rerun()
            else: st.error("Invalid username or password.")
    if st.button("← Back to Welcome"): st.session_state.screen = "welcome"; st.rerun()

def show_register_screen():
    st.header("Create a New Account")
    with st.form("register_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        avatar_label = st.selectbox("Choose Your Avatar", options=list(AVATARS.keys()))
        submitted = st.form_submit_button("Register")
        if submitted:
            if not username or not password: st.warning("Please fill out all fields.")
            else:
                hashed_pass = hash_password(password)
                try:
                    with conn.session as s: s.execute(text("INSERT INTO users (username, hashed_password, avatar) VALUES (:u, :hp, :a);"), params=dict(u=username, hp=hashed_pass, a=AVATARS[avatar_label])); s.commit()
                    st.success("Registration successful! Please log in."); time.sleep(1); st.session_state.screen = "login"; st.rerun()
                except Exception as e:
                    if "UNIQUE constraint failed" in str(e): st.error("Username already exists.")
                    else: st.error(f"An error occurred: {e}")
    if st.button("← Back to Welcome"): st.session_state.screen = "welcome"; st.rerun()

def show_guest_setup_screen():
    st.header("Enter as a Guest")
    with st.form("guest_form"):
        username = st.text_input("Guest Username")
        avatar_label = st.selectbox("Choose Your Avatar", options=list(AVATARS.keys()))
        submitted = st.form_submit_button("Enter Chat")
        if submitted:
            if not username: st.warning("Please enter a username.")
            else:
                st.session_state.logged_in = True; st.session_state.username = f"{username} (Guest)"; st.session_state.avatar = AVATARS[avatar_label]; st.session_state.role = "guest"; st.session_state.screen = "chat"; st.rerun()
    if st.button("← Back to Welcome"): st.session_state.screen = "welcome"; st.rerun()

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
                with conn.session as s: user = s.execute(text("SELECT hashed_password FROM users WHERE username = :u"), params=dict(u=username_to_change)).fetchone()
                if not verify_password(user.hashed_password, current_password):
                    st.error("Current password is incorrect."); return
            if new_password != confirm_password: st.error("New passwords do not match.")
            elif len(new_password) < 6: st.error("New password must be at least 6 characters long.")
            else:
                new_hashed_password = hash_password(new_password)
                with conn.session as s: s.execute(text("UPDATE users SET hashed_password = :hp WHERE username = :u"), params=dict(hp=new_hashed_password, u=username_to_change)); s.commit()
                st.success(f"Password for '{username_to_change}' changed successfully!")
                if not is_admin_reset: st.session_state.admin_using_default_pass = False
                time.sleep(1); st.rerun()

def show_admin_dashboard():
    st.subheader("🛡️ Admin Dashboard")
    st.write("Moderate users and manage the chat room.")
    
    st.markdown("---")
    st.subheader("User Management")
    all_users_df = conn.query("SELECT username, avatar, role, status FROM users ORDER BY username;", ttl=10)
    
    for _, user in all_users_df.iterrows():
        if user.username == SUPER_ADMIN_USERNAME: continue
        st.markdown(f"**{user.avatar} {user.username}** (`{user.role}`) - Status: **{user.status.capitalize()}**")
        col1, col2 = st.columns(2)
        with col1:
            if user.status == 'active':
                if st.button("🚫 Ban", key=f"ban_{user.username}", use_container_width=True, type="primary"):
                    with conn.session as s: s.execute(text("UPDATE users SET status = 'banned' WHERE username = :u"), params=dict(u=user.username)); s.commit()
                    st.rerun()
            else:
                if st.button("✅ Unban", key=f"unban_{user.username}", use_container_width=True):
                    with conn.session as s: s.execute(text("UPDATE users SET status = 'active' WHERE username = :u"), params=dict(u=user.username)); s.commit()
                    st.rerun()
        with col2:
            with st.popover("Reset Password", use_container_width=True):
                show_change_password_form(user.username, is_admin_reset=True)
        st.markdown("---")

    st.subheader("Chat Controls")
    if st.button("🚨 Clear All Messages", use_container_width=True):
        with st.popover("Confirm Action"):
            st.warning("This will permanently delete all messages.")
            if st.button("Yes, Delete Everything", type="primary"):
                with conn.session as s: s.execute(text("DELETE FROM messages;")); s.commit()
                st.toast("Chat history cleared!"); st.rerun()

def show_chat_screen():
    clear_old_messages()
    st_autorefresh(interval=5000, limit=None, key="chat_refresh")
    if st.session_state.get("admin_using_default_pass", False):
        st.warning("🚨 **Security Alert:** You are using the default admin password. Please change it immediately.", icon="⚠️")
    
    with st.sidebar:
        st.title(f"{st.session_state.avatar} {st.session_state.username}")
        st.caption(f"Role: {st.session_state.role.capitalize()}")
        if st.button("Log Out"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()
        
        if st.session_state.role == 'admin':
            st.divider()
            with st.expander("Admin Dashboard", expanded=True):
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

    if prompt := st.chat_input("Share your thoughts..."):
        sentiment_score = analyze_sentiment(prompt)
        with conn.session as s:
            s.execute(text("INSERT INTO messages (username, avatar, message, timestamp, sentiment) VALUES (:u, :a, :m, :ts, :senti);"),
                      params=dict(u=st.session_state.username, a=st.session_state.avatar, m=prompt, ts=datetime.now(), senti=sentiment_score))
            s.commit()
        st.rerun()




download_nltk_data()
init_db()
if 'screen' not in st.session_state: st.session_state.screen = "welcome"
if st.session_state.screen == "welcome": show_welcome_screen()
elif st.session_state.screen == "login": show_login_screen()
elif st.session_state.screen == "register": show_register_screen()
elif st.session_state.screen == "guest_setup": show_guest_setup_screen()
elif st.session_state.screen == "chat": show_chat_screen()
