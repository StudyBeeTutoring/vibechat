import streamlit as st
from datetime import datetime
from sqlalchemy import text
import time

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Streamlit Chat",
    page_icon="💬",
    layout="centered"
)

# --- DATABASE SETUP ---
# Establishes a connection to a local SQLite database file.
# The 'ttl=0' argument ensures that we always get the latest data from the DB.
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
    
    # Using a form to prevent rerun on every character input
    with st.form("login_form"):
        username = st.text_input("Username", key="username_input", placeholder="e.g., ChattyCathy")
        submitted = st.form_submit_button("Join Chat")

        if submitted:
            if not username:
                st.warning("Please enter a username.")
            else:
                st.session_state.username = username
                st.success(f"Welcome, {username}! You can now start chatting.")
                time.sleep(1) # Brief pause to show success message
                st.rerun()

# --- MAIN CHAT INTERFACE ---
def chat_interface():
    """Displays the main chat interface and handles sending/receiving messages."""
    st.title("💬 Streamlit Global Chat")
    st.caption(f"Logged in as: **{st.session_state.username}**")

    # --- MESSAGE DISPLAY ---
    # Query all messages from the database, ordered by time.
    messages_df = conn.query("SELECT * FROM messages ORDER BY timestamp ASC;", ttl=0)

    # Display each message in the chat
    for _, row in messages_df.iterrows():
        with st.chat_message(name=row["username"]):
            st.markdown(f"**{row['username']}**")
            st.write(row["message"])
            st.caption(f"_{row['timestamp']}_")

    # --- MESSAGE INPUT ---
    # `st.chat_input` is a special widget that stays at the bottom.
    if prompt := st.chat_input("Say something..."):
        # When a new message is sent, add it to the database.
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
        # Rerun the app to display the new message immediately.
        st.rerun()

# --- APP LOGIC ---
# Initialize the database on first run.
init_db()

# Check if the user is logged in.
if 'username' not in st.session_state:
    login_screen()
else:
    chat_interface()
