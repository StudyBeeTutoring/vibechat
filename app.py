import streamlit as st
import pandas as pd
from datetime import datetime
from sqlalchemy import text
import time
from streamlit_autorefresh import st_autorefresh
import json
import hashlib
import streamlit.components.v1 as components

# --- CONFIGURATION ---
SUPER_ADMIN_USERNAME = "admin"
SUPER_ADMIN_DEFAULT_PASS = "admin123" # The app will prompt to change this
APP_SALT = "a_super_secret_salt_for_our_app" # IMPORTANT: Change this for your own app

AVATARS = {
    "Cat": "🐱", "Dog": "🐶", "Fox": "🦊", "Bear": "🐻",
    "Panda": "🐼", "Tiger": "🐯", "Lion": "🦁", "Robot": "🤖"
}

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Streamlit Advanced Chat", page_icon="🌐", layout="wide")

# --- DATABASE SETUP ---
conn = st.connection("chat_db", type="sql", url="sqlite:///advanced_chat.db", ttl=0)

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
                id INTEGER PRIMARY KEY, username TEXT, avatar TEXT,
                message TEXT, timestamp DATETIME, reactions TEXT DEFAULT '{}'
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS user_locations (
                id INTEGER PRIMARY KEY, username TEXT, lat REAL, lon REAL,
                timestamp DATETIME
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
            st.toast(f"Admin user created! User: '{SUPER_ADMIN_USERNAME}', Pass: '{SUPER_ADMIN_DEFAULT_PASS}'")
            st.toast("Please log in as admin and change the password.", icon="🚨")
        s.commit()

# --- SECURITY & HELPERS ---
def hash_password(password):
    """Hashes a password with a salt."""
    salted_password = password + APP_SALT
    return hashlib.sha256(salted_password.encode()).hexdigest()

def verify_password(stored_hash, provided_password):
    """Verifies a provided password against a stored hash."""
    return stored_hash == hash_password(provided_password)

# --- GEOLOCATION COMPONENT ---
def get_location_component():
    """Returns an HTML component that gets the user's location and sends it back."""
    # This is a one-way communication: JS -> Streamlit
    # The return value of this component call will be the data sent from JS
    return components.html(
        """
        <script>
        const sendLocation = (position) => {
            const { latitude, longitude } = position.coords;
            // When the data is sent, it's received by Streamlit as the component's value
            window.parent.postMessage({
                type: "streamlit:setComponentValue",
                value: { lat: latitude, lon: longitude }
            }, "*");
        };
        
        // Request location
        navigator.geolocation.getCurrentPosition(sendLocation, (err) => {
            // Can optionally send error back to Streamlit as well
            console.warn(`ERROR(${err.code}): ${err.message}`);
        });
        </script>
        """,
        height=0,  # Make the component invisible
    )

# --- UI SCREENS ---
def show_welcome_screen():
    """The initial screen with Login/Register/Guest options."""
    st.title("Welcome to the Advanced Chat App 🌐")
    col1, col2, col3 = st.columns(3)
    if col1.button("🔒 Login", use_container_width=True):
        st.session_state.screen = "login"
        st.rerun()
    if col2.button("✍️ Register", use_container_width=True):
        st.session_state.screen = "register"
        st.rerun()
    if col3.button("👤 Continue as Guest", use_container_width=True):
        st.session_state.screen = "guest_setup"
        st.rerun()

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
                st.session_state.logged_in = True
                st.session_state.username = user.username
                st.session_state.avatar = user.avatar
                st.session_state.role = user.role
                st.session_state.screen = "chat"
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
                        s.execute(
                            text("INSERT INTO users (username, hashed_password, avatar) VALUES (:u, :hp, :a);"),
                            params=dict(u=username, hp=hashed_pass, a=AVATARS[avatar_label])
                        )
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

def show_chat_screen():
    """The main chat interface."""
    st_autorefresh(interval=5000, limit=None, key="chat_refresh")

    # --- SIDEBAR ---
    with st.sidebar:
        st.title(f"{st.session_state.avatar} {st.session_state.username}")
        st.caption(f"Role: {st.session_state.role.capitalize()}")
        if st.button("Log Out"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        st.divider()

        # Location Sharing Section
        st.subheader("📍 Share Location")
        st.warning("This shares your location with all users on the map. Use with caution.")
        if st.button("Update My Location", use_container_width=True):
            st.session_state.get_location = True
        
        # Admin Panel
        if st.session_state.role == 'admin':
            st.divider()
            st.subheader("Admin Controls")
            if st.button("🚨 Clear All Messages", type="primary"):
                with conn.session as s:
                    s.execute(text("DELETE FROM messages;"))
                    s.commit()
                st.toast("Chat history cleared!")
                st.rerun()
    
    # --- MAIN CHAT AREA ---
    # Handle location data if requested
    if st.session_state.get('get_location', False):
        location_data = get_location_component()
        if location_data:
            with conn.session as s:
                s.execute(
                    text("INSERT INTO user_locations (username, lat, lon, timestamp) VALUES (:u, :lat, :lon, :ts)"),
                    params=dict(u=st.session_state.username, lat=location_data['lat'], lon=location_data['lon'], ts=datetime.now())
                )
                s.commit()
            st.toast(f"Location updated: {location_data['lat']:.4f}, {location_data['lon']:.4f}")
            st.session_state.get_location = False # Reset the flag


    tab1, tab2 = st.tabs(["💬 Chat Room", "🗺️ Activity Map"])
    
    with tab1:
        messages_df = conn.query("SELECT * FROM messages ORDER BY timestamp ASC;", ttl=0)
        for _, row in messages_df.iterrows():
            with st.chat_message(name=row["username"], avatar=row["avatar"]):
                st.markdown(f"**{row['username']}**")
                st.write(row["message"])
                ts = pd.to_datetime(row["timestamp"])
                st.caption(f"_{ts.strftime('%b %d, %I:%M %p')}_")
        
        # Message input
        if prompt := st.chat_input("Say something..."):
            with conn.session as s:
                s.execute(
                    text("INSERT INTO messages (username, avatar, message, timestamp) VALUES (:u, :a, :m, :ts);"),
                    params=dict(u=st.session_state.username, a=st.session_state.avatar, m=prompt, ts=datetime.now())
                )
                s.commit()
            st.rerun()

    with tab2:
        st.header("User Location Map")
        # Query to get the LATEST location for each user
        locations_df = conn.query("""
            SELECT username, lat, lon
            FROM user_locations
            WHERE id IN (
                SELECT MAX(id)
                FROM user_locations
                GROUP BY username
            );
        """, ttl=10) # Cache for 10 seconds
        
        if not locations_df.empty:
            st.map(locations_df)
        else:
            st.info("No user locations have been shared yet. Be the first!")

# --- MAIN APP ROUTER ---
init_db()

if 'screen' not in st.session_state:
    st.session_state.screen = "welcome"

if st.session_state.screen == "welcome":
    show_welcome_screen()
elif st.session_state.screen == "login":
    show_login_screen()
elif st.session_state.screen == "register":
    show_register_screen()
elif st.session_state.screen == "guest_setup":
    show_guest_setup_screen()
elif st.session_state.screen == "chat":
    show_chat_screen()
