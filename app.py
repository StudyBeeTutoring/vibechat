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

# --- ONE-TIME SETUP for TextBlob ---
# REMOVED @st.cache_resource decorator to fix the CacheReplayClosureError.
# This function will now run on each script run, but the internal check is fast.
def download_nltk_data():
    """Downloads the necessary NLTK models for TextBlob sentiment analysis."""
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        st.toast("Performing first-time setup for sentiment analysis...", icon="⏳")
        nltk.download('punkt')
        st.toast("Setup complete! The app is ready.", icon="🎉")

# --- CONFIGURATION ---
SUPER_ADMIN_USERNAME = "admin"
SUPER_ADMIN_DEFAULT_PASS = "admin123"
APP_SALT = "a_super_secret_salt_for_a_sentiment_app_v5"

AVATARS = {
    "Cat": "🐱", "Dog": "🐶", "Fox": "🦊", "Bear": "🐻",
    "Panda": "🐼", "Tiger": "🐯", "Lion": "🦁", "Robot": "🤖"
}

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Sentimental Chat", page_icon="😊", layout="wide")

# --- DATABASE SETUP ---
conn = st.connection("chat_db", type="sql", url="sqlite:///sentimental_chat.db", ttl=0)

def init_db():
    with conn.session as s:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, hashed_password TEXT NOT NULL,
                avatar TEXT, role TEXT DEFAULT 'user'
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, username TEXT, avatar TEXT,
                message TEXT, timestamp DATETIME,
                sentiment REAL DEFAULT 0.0
            );
        """))
        admin_user = s.execute(text("SELECT * FROM users WHERE username = :user;"), params=dict(user=SUPER_ADMIN_USERNAME)).fetchone()
        if not admin_user:
            hashed_pass = hash_password(SUPER_ADMIN_DEFAULT_PASS)
            s.execute(text("""
                INSERT INTO users (username, hashed_password, avatar, role)
                VALUES (:user, :hp, '👑', 'admin');
            """), params=dict(user=SUPER_ADMIN_USERNAME, hp=hashed_pass))
        s.commit()

# --- NLP & HELPERS ---
def analyze_sentiment(text_message):
    return TextBlob(text_message).sentiment.polarity

def get_sentiment_emoji(score):
    if score > 0.1: return "😊"
    elif score < -0.1: return "😠"
    else: return "😐"

def hash_password(password):
    return hashlib.sha256((password + APP_SALT).encode()).hexdigest()

def verify_password(stored_hash, provided_password):
    return stored_hash == hash_password(provided_password)

def clear_old_messages():
    cutoff_time = datetime.now() - timedelta(hours=1)
    with conn.session as s:
        s.execute(text("DELETE FROM messages WHERE timestamp < :cutoff;"), params=dict(cutoff=cutoff_time))
        s.commit()

# --- UI SCREENS ---
def show_welcome_screen():
    st.title("Welcome to Sentimental Chat 😊")
    st.write("A chat app that understands the mood of the conversation.")
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

def show_change_password_form():
    st.subheader("🔑 Change Password")
    with st.form("change_password_form"):
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Change Password")
        if submitted:
            with conn.session as s: user = s.execute(text("SELECT hashed_password FROM users WHERE username = :u"), params=dict(u=st.session_state.username)).fetchone()
            if not verify_password(user.hashed_password, current_password): st.error("Current password is incorrect.")
            elif new_password != confirm_password: st.error("New passwords do not match.")
            elif len(new_password) < 6: st.error("New password must be at least 6 characters long.")
            else:
                new_hashed_password = hash_password(new_password)
                with conn.session as s: s.execute(text("UPDATE users SET hashed_password = :hp WHERE username = :u"), params=dict(hp=new_hashed_password, u=st.session_state.username)); s.commit()
                st.success("Password changed successfully!"); st.session_state.admin_using_default_pass = False; time.sleep(1); st.rerun()

def show_chat_vibe():
    st.subheader("💬 Chat Vibe")
    recent_sentiments = conn.query("SELECT sentiment FROM messages ORDER BY timestamp DESC LIMIT 20;")['sentiment'].tolist()
    if recent_sentiments:
        avg_sentiment = sum(recent_sentiments) / len(recent_sentiments)
        vibe_emoji = get_sentiment_emoji(avg_sentiment)
        st.metric(label=f"Overall Mood: {vibe_emoji}", value=f"{avg_sentiment:.2f}")
        st.progress((avg_sentiment + 1) / 2)
        st.caption("Based on the last 20 messages.")
    else:
        st.info("Not enough messages to determine the chat vibe.")

def show_chat_screen():
    clear_old_messages()
    st_autorefresh(interval=5000, limit=None, key="chat_refresh")
    if st.session_state.get("admin_using_default_pass", False):
        st.warning("🚨 **Security Alert:** You are using the default administrator password. Please change it immediately.", icon="⚠️")
    
    with st.sidebar:
        st.title(f"{st.session_state.avatar} {st.session_state.username}")
        st.caption(f"Role: {st.session_state.role.capitalize()}")
        if st.button("Log Out"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()
        st.divider()
        show_chat_vibe()
        
        if st.session_state.role == 'admin':
            st.divider()
            with st.expander("Admin Controls", expanded=False):
                if st.button("🚨 Clear All Messages", type="primary", use_container_width=True):
                    with conn.session as s: s.execute(text("DELETE FROM messages;")); s.commit()
                    st.toast("Chat history cleared!"); st.rerun()
                st.subheader("Registered Users")
                all_users_df = conn.query("SELECT username, avatar, role FROM users ORDER BY username;")
                st.dataframe(all_users_df, use_container_width=True, hide_index=True)
            st.divider()
            show_change_password_form()

    st.title("Global Chat Room")
    st.caption("Messages are automatically deleted after 1 hour.")

    chat_container = st.container(height=500)
    with chat_container:
        messages_df = conn.query("SELECT * FROM messages ORDER BY timestamp ASC;", ttl=0)
        for _, row in messages_df.iterrows():
            with st.chat_message(name=row["username"], avatar=row["avatar"]):
                sentiment_emoji = get_sentiment_emoji(row['sentiment'])
                st.markdown(f"**{row['username']}** {sentiment_emoji}")
                st.write(row["message"])
                ts = pd.to_datetime(row["timestamp"])
                st.caption(f"_{ts.strftime('%b %d, %I:%M %p')}_")

    if prompt := st.chat_input("Say something..."):
        sentiment_score = analyze_sentiment(prompt)
        with conn.session as s:
            s.execute(text("""
                INSERT INTO messages (username, avatar, message, timestamp, sentiment) 
                VALUES (:u, :a, :m, :ts, :senti);
            """), params=dict(
                u=st.session_state.username, a=st.session_state.avatar, 
                m=prompt, ts=datetime.now(), senti=sentiment_score
            ))
            s.commit()
        st.rerun()

# --- MAIN APP ROUTER ---
download_nltk_data()
init_db()
if 'screen' not in st.session_state: st.session_state.screen = "welcome"
if st.session_state.screen == "welcome": show_welcome_screen()
elif st.session_state.screen == "login": show_login_screen()
elif st.session_state.screen == "register": show_register_screen()
elif st.session_state.screen == "guest_setup": show_guest_setup_screen()
elif st.session_state.screen == "chat": show_chat_screen()
