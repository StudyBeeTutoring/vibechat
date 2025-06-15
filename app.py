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
@st.cache_resource
def download_nltk_data():
    """Downloads the necessary NLTK models for TextBlob sentiment analysis."""
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        # This will run once when the app container boots on Streamlit Cloud
        nltk.download('punkt')

# --- CONFIGURATION ---
SUPER_ADMIN_USERNAME = "admin"
SUPER_ADMIN_DEFAULT_PASS = "admin123"
APP_SALT = "a_super_secret_salt_for_a_managed_app_v6"

AVATARS = {
    "Cat": "🐱", "Dog": "🐶", "Fox": "🦊", "Bear": "🐻",
    "Panda": "🐼", "Tiger": "🐯", "Lion": "🦁", "Robot": "🤖"
}

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Managed Chat", page_icon="⚙️", layout="wide")

# --- DATABASE SETUP ---
# Using a new DB file to ensure the schema is updated with all new columns.
conn = st.connection("chat_db", type="sql", url="sqlite:///managed_chat_v1.db", ttl=0)

def init_db():
    with conn.session as s:
        # Added 'status' and 'role' to users table
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                hashed_password TEXT NOT NULL,
                avatar TEXT,
                role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'active' -- 'active' or 'banned'
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
                INSERT INTO users (username, hashed_password, avatar, role, status)
                VALUES (:user, :hp, '👑', 'admin', 'active');
            """), params=dict(user=SUPER_ADMIN_USERNAME, hp=hashed_pass))
        s.commit()

# --- SECURITY & DATA MANAGEMENT ---
def hash_password(password):
    return hashlib.sha256((password + APP_SALT).encode()).hexdigest()
def verify_password(stored_hash, provided_password):
    return stored_hash == hash_password(provided_password)
def clear_old_messages():
    cutoff_time = datetime.now() - timedelta(hours=1)
    with conn.session as s:
        s.execute(text("DELETE FROM messages WHERE timestamp < :cutoff;"), params=dict(cutoff=cutoff_time))
        s.commit()

# --- NLP & HELPERS ---
def analyze_sentiment(text_message):
    return TextBlob(text_message).sentiment.polarity
def get_sentiment_emoji(score):
    if score > 0.1: return "😊"
    elif score < -0.1: return "😠"
    else: return "😐"

# --- UI SCREENS ---
def show_welcome_screen():
    st.title("Welcome to the Managed Chat App ⚙️")
    st.write("Log in, register, or join as a guest.")
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
                if user.status == 'banned':
                    st.error("This account has been banned.")
                else:
                    st.session_state.logged_in = True; st.session_state.username = user.username; st.session_state.avatar = user.avatar; st.session_state.role = user.role; st.session_state.screen = "chat"
                    if user.role == 'admin' and verify_password(user.hashed_password, SUPER_ADMIN_DEFAULT_PASS): st.session_state.admin_using_default_pass = True
                    st.success("Login successful!"); time.sleep(1); st.rerun()
            else:
                st.error("Invalid username or password.")
    if st.button("← Back to Welcome"): st.session_state.screen = "welcome"; st.rerun()

# (show_register_screen and show_guest_setup_screen are unchanged)
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
        st.subheader(f"Reset Password for '{username_to_change}'")
    else:
        st.subheader("🔑 Change Your Password")

    with st.form(form_key):
        if not is_admin_reset:
            current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")
        submitted = st.form_submit_button("Change Password")

        if submitted:
            # Verify current password if it's a self-change
            if not is_admin_reset:
                with conn.session as s: user = s.execute(text("SELECT hashed_password FROM users WHERE username = :u"), params=dict(u=username_to_change)).fetchone()
                if not verify_password(user.hashed_password, current_password):
                    st.error("Current password is incorrect.")
                    return
            
            # Validate new password
            if new_password != confirm_password:
                st.error("New passwords do not match.")
            elif len(new_password) < 6:
                st.error("New password must be at least 6 characters long.")
            else:
                new_hashed_password = hash_password(new_password)
                with conn.session as s:
                    s.execute(text("UPDATE users SET hashed_password = :hp WHERE username = :u"), params=dict(hp=new_hashed_password, u=username_to_change)); s.commit()
                st.success(f"Password for '{username_to_change}' changed successfully!")
                if not is_admin_reset:
                    st.session_state.admin_using_default_pass = False
                time.sleep(1); st.rerun()

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
            with st.expander("🔑 Change Your Password"):
                show_change_password_form(st.session_state.username)

    tab1, tab2 = st.tabs(["💬 Chat Room", "🛡️ Admin Panel"])
    with tab1:
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
                s.execute(text("INSERT INTO messages (username, avatar, message, timestamp, sentiment) VALUES (:u, :a, :m, :ts, :senti);"),
                          params=dict(u=st.session_state.username, a=st.session_state.avatar, m=prompt, ts=datetime.now(), senti=sentiment_score))
                s.commit()
            st.rerun()

    with tab2:
        if st.session_state.role != 'admin':
            st.error("You do not have permission to view this page.")
        else:
            st.header("User Management Dashboard")
            st.info("From here, you can ban/unban users and reset their passwords.")
            all_users_df = conn.query("SELECT username, avatar, role, status FROM users ORDER BY username;")
            
            for index, user in all_users_df.iterrows():
                if user.username == SUPER_ADMIN_USERNAME: continue # Admin cannot ban themselves
                
                st.divider()
                col1, col2, col3 = st.columns([2, 2, 3])
                col1.markdown(f"**{user.avatar} {user.username}** (`{user.role}`)")
                col2.markdown(f"Status: **{user.status.capitalize()}**")

                with col3:
                    if user.status == 'active':
                        if st.button("🚫 Ban User", key=f"ban_{user.username}", type="primary"):
                            with conn.session as s: s.execute(text("UPDATE users SET status = 'banned' WHERE username = :u"), params=dict(u=user.username)); s.commit()
                            st.rerun()
                    else:
                        if st.button("✅ Unban User", key=f"unban_{user.username}"):
                            with conn.session as s: s.execute(text("UPDATE users SET status = 'active' WHERE username = :u"), params=dict(u=user.username)); s.commit()
                            st.rerun()
                
                with st.expander(f"Reset password for '{user.username}'"):
                    show_change_password_form(user.username, is_admin_reset=True)

# --- MAIN APP ROUTER ---
download_nltk_data()
init_db()
if 'screen' not in st.session_state: st.session_state.screen = "welcome"
if st.session_state.screen == "welcome": show_welcome_screen()
elif st.session_state.screen == "login": show_login_screen()
elif st.session_state.screen == "register": show_register_screen()
elif st.session_state.screen == "guest_setup": show_guest_setup_screen()
elif st.session_state.screen == "chat": show_chat_screen()
