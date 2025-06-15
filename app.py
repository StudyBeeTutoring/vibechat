import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
import time
from streamlit_autorefresh import st_autorefresh
import json
import hashlib

# --- CONFIGURATION ---
SUPER_ADMIN_USERNAME = "admin"
SUPER_ADMIN_DEFAULT_PASS = "admin123"
# IMPORTANT: For a real app, you should change this salt to a unique, random string.
APP_SALT = "a_super_secret_salt_for_a_privacy_focused_app"

AVATARS = {
    "Cat": "🐱", "Dog": "🐶", "Fox": "🦊", "Bear": "🐻",
    "Panda": "🐼", "Tiger": "🐯", "Lion": "🦁", "Robot": "🤖"
}

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Streamlit Chat App", page_icon="💬", layout="wide")

# --- DATABASE SETUP ---
# Using a new DB file to reflect the final version without location data.
conn = st.connection("chat_db", type="sql", url="sqlite:///chat_app_final.db", ttl=0)

def init_db():
    """Initializes all necessary database tables."""
    with conn.session as s:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                hashed_password TEXT NOT NULL,
                avatar TEXT,
                role TEXT DEFAULT 'user'
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                username TEXT,
                avatar TEXT,
                message TEXT,
                timestamp DATETIME,
                reactions TEXT DEFAULT '{}'
            );
        """))
        # Check if admin user exists, if not, create it.
        admin_user = s.execute(text("SELECT * FROM users WHERE username = :user;"), params=dict(user=SUPER_ADMIN_USERNAME)).fetchone()
        if not admin_user:
            hashed_pass = hash_password(SUPER_ADMIN_DEFAULT_PASS)
            s.execute(text("""
                INSERT INTO users (username, hashed_password, avatar, role)
                VALUES (:user, :hp, '👑', 'admin');
            """), params=dict(user=SUPER_ADMIN_USERNAME, hp=hashed_pass))
        s.commit()

# --- SECURITY & DATA MANAGEMENT ---
def hash_password(password):
    """Hashes a password with the app's salt."""
    salted_password = password + APP_SALT
    return hashlib.sha256(salted_password.encode()).hexdigest()

def verify_password(stored_hash, provided_password):
    """Verifies a provided password against a stored hash."""
    return stored_hash == hash_password(provided_password)

def clear_old_messages():
    """Deletes messages from the database that are older than 1 hour."""
    cutoff_time = datetime.now() - timedelta(hours=1)
    with conn.session as s:
        s.execute(
            text("DELETE FROM messages WHERE timestamp < :cutoff;"),
            params=dict(cutoff=cutoff_time)
        )
        s.commit()

# --- UI SCREENS (Welcome, Login, Register, Guest, Change Password are unchanged) ---
def show_welcome_screen():
    st.title("Welcome to the Streamlit Chat App 💬")
    st.write("Log in to an existing account, register a new one, or join temporarily as a guest.")
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

def show_chat_screen():
    clear_old_messages()
    st_autorefresh(interval=5000, limit=None, key="chat_refresh")

    if st.session_state.get("admin_using_default_pass", False):
        st.warning("🚨 **Security Alert:** You are using the default administrator password. Please change it immediately in the sidebar.", icon="⚠️")
    
    with st.sidebar:
        st.title(f"{st.session_state.avatar} {st.session_state.username}")
        st.caption(f"Role: {st.session_state.role.capitalize()}")
        if st.button("Log Out"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.rerun()
        
        if st.session_state.role == 'admin':
            st.divider()
            with st.expander("Admin Controls", expanded=False):
                if st.button("🚨 Clear All Messages", type="primary", use_container_width=True):
                    with conn.session as s: s.execute(text("DELETE FROM messages;")); s.commit()
                    st.toast("Chat history cleared!"); st.rerun()
                st.subheader("Registered Users")
                all_users_df = conn.query("SELECT username, avatar, role FROM users ORDER BY username;")
                st.dataframe(all_users_df, use_container_width=True, hide_index=True)
                st.caption("Note: Hashed passwords are not displayed for security.")
            st.divider()
            show_change_password_form()

    # --- MAIN CHAT UI (Simplified without tabs) ---
    st.title("Global Chat Room")
    st.caption("Messages are automatically deleted after 1 hour.")

    chat_container = st.container(height=500)
    with chat_container:
        messages_df = conn.query("SELECT * FROM messages ORDER BY timestamp ASC;", ttl=0)
        for _, row in messages_df.iterrows():
            with st.chat_message(name=row["username"], avatar=row["avatar"]):
                st.markdown(f"**{row['username']}**"); st.write(row["message"])
                ts = pd.to_datetime(row["timestamp"])
                st.caption(f"_{ts.strftime('%b %d, %I:%M %p')}_")

    if prompt := st.chat_input("Say something..."):
        with conn.session as s:
            s.execute(text("INSERT INTO messages (username, avatar, message, timestamp) VALUES (:u, :a, :m, :ts);"), 
                      params=dict(u=st.session_state.username, a=st.session_state.avatar, m=prompt, ts=datetime.now()))
            s.commit()
        st.rerun()

# --- MAIN APP ROUTER ---
init_db()
if 'screen' not in st.session_state: st.session_state.screen = "welcome"
if st.session_state.screen == "welcome": show_welcome_screen()
elif st.session_state.screen == "login": show_login_screen()
elif st.session_state.screen == "register": show_register_screen()
elif st.session_state.screen == "guest_setup": show_guest_setup_screen()
elif st.session_state.screen == "chat": show_chat_screen()
