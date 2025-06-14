import streamlit as st
from datetime import datetime
from sqlalchemy import text
import time
from streamlit_autorefresh import st_autorefresh # <- ADD THIS IMPORT

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Streamlit Chat",
    page_icon="💬",
    layout="centered"
)

# --- DATABASE SETUP ---
# Establishes a connection to a local SQLite database file.
conn = st.connection("chat_db", type="sql", url="sqlite:///chat.db", ttl=0)

def init_db():
    """Initializes the database table if it doesn't exist."""
    with conn.session as s:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                username TEXT,
                message TEXT,
                timestamp DATETIME
            );
        """))
        s.commit()

# --- LOGIN / ONBOARDING ---
def login_screen():
    """Displays the login screen and handles user login."""
    st.header("Welcome to the Global Chat Room 🌍")
    st.write("Please enter a username to join the chat.")
    
    with st.form("login_form"):
        username = st.text_input("Username", key="username_input", placeholder="e.g., ChattyCathy")
        submitted = st.form_submit_button("Join Chat")

        if submitted:
            if not username:
                st.warning("Please enter a username.")
            else:
                st.session_state.username = username
                st.success(f"Welcome, {username}! You can now start chatting.")
                time.sleep(1)
                st.rerun()

# --- MAIN CHAT INTERFACE ---
def chat_interface():
    """Displays the main chat interface and handles sending/receiving messages."""

    # --- AUTO-REFRESH ---
    # This is the magic part! It will rerun the script every 2 seconds.
    # The key provides a unique identity for this component.
    # A smaller interval (e.g., 1000ms) means faster updates but more server load.
    st_autorefresh(interval=2000, limit=None, key="chat_autorefresh") # <- ADD THIS LINE

    st.title("💬 Streamlit Global Chat")
    st.caption(f"Logged in as: **{st.session_state.username}**")

    # --- MESSAGE DISPLAY ---
    # This block now runs every 2 seconds automatically.
    messages_df = conn.query("SELECT * FROM messages ORDER BY timestamp ASC;", ttl=0)

    # Use a container for messages to potentially optimize rendering
    chat_container = st.container()
    with chat_container:
        for _, row in messages_df.iterrows():
            # Use a unique key for each message to help Streamlit with rendering
            with st.chat_message(name=row["username"], avatar="👤"):
                st.markdown(f"**{row['username']}**")
                st.write(row["message"])
                # Formatting the timestamp for better readability
                ts = pd.to_datetime(row["timestamp"])
                st.caption(f"_{ts.strftime('%b %d, %I:%M %p')}_")

    # --- MESSAGE INPUT ---
    if prompt := st.chat_input("Say something..."):
        with conn.session as s:
            s.execute(
                text("INSERT INTO messages (username, message, timestamp) VALUES (:user, :msg, :ts);"),
                params=dict(
                    user=st.session_state.username,
                    msg=prompt,
                    ts=datetime.now()
                )
            )
            s.commit()
        # No need to call st.rerun() here, as the autorefresh will handle it.
        # The new message will appear on the next 2-second interval.

# --- APP LOGIC ---
init_db()

if 'username' not in st.session_state:
    login_screen()
else:
    chat_interface()
