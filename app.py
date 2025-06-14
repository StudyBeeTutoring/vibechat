import streamlit as st
from datetime import datetime
from sqlalchemy import text
import time
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import json

# --- CONFIGURATION ---
ADMIN_USERNAMES = ["admin", "super_user"]
AVATARS = {
    "Cat": "🐱", "Dog": "🐶", "Fox": "🦊", "Bear": "🐻",
    "Panda": "🐼", "Tiger": "🐯", "Lion": "🦁", "Robot": "🤖"
}

# --- PAGE CONFIG ---
st.set_page_config(page_title="Streamlit Chat V2", page_icon="🚀", layout="wide")

# --- DATABASE SETUP ---
conn = st.connection("chat_db", type="sql", url="sqlite:///chat_v2.db", ttl=0)

def init_db():
    with conn.session as s:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, username TEXT, avatar TEXT,
                message TEXT, timestamp DATETIME, reactions TEXT DEFAULT '{}'
            );
        """))
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS active_users (
                username TEXT PRIMARY KEY, last_seen DATETIME
            );
        """))
        s.commit()

# --- HELPER FUNCTIONS ---
def update_user_activity():
    if 'username' in st.session_state:
        with conn.session as s:
            s.execute(
                text("INSERT OR REPLACE INTO active_users (username, last_seen) VALUES (:user, :ts);"),
                params=dict(user=st.session_state.username, ts=datetime.now())
            )
            s.commit()

def get_active_users():
    cutoff = datetime.now() - pd.Timedelta(minutes=2)
    active_users_df = conn.query(
        "SELECT username FROM active_users WHERE last_seen > :cutoff;",
        params={"cutoff": cutoff}
    )
    return active_users_df["username"].tolist()

def add_reaction(message_id, emoji):
    with conn.session as s:
        result = s.execute(text("SELECT reactions FROM messages WHERE id = :id;"), params=dict(id=message_id)).fetchone()
        reactions = json.loads(result[0]) if result and result[0] else {}
        reactions[emoji] = reactions.get(emoji, 0) + 1
        s.execute(
            text("UPDATE messages SET reactions = :reactions WHERE id = :id;"),
            params=dict(reactions=json.dumps(reactions), id=message_id)
        )
        s.commit()

# --- UI COMPONENTS ---
def login_screen():
    st.header("Welcome to the Streamlit Chat V2 🚀")
    st.write("Choose a username and an avatar to join.")
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="e.g., ChattyCathy")
        avatar_label = st.selectbox("Choose Your Avatar", options=list(AVATARS.keys()))
        submitted = st.form_submit_button("Join Chat")
        if submitted:
            if not username:
                st.warning("Please enter a username.")
            else:
                st.session_state.username = username
                st.session_state.avatar = AVATARS[avatar_label]
                st.success(f"Welcome, {username}! You can now start chatting.")
                time.sleep(1)
                st.rerun()

def admin_panel():
    st.subheader("Admin Controls")
    with st.expander("🚨 Clear Chat History"):
        st.warning("This action is irreversible and will delete all messages for everyone.")
        if st.button("Delete All Messages", type="primary"):
            with conn.session as s:
                s.execute(text("DELETE FROM messages;"))
                s.execute(text("VACUUM;"))
                s.commit()
            st.success("Chat history cleared.")
            time.sleep(1)
            st.rerun()

def chat_interface():
    st_autorefresh(interval=2000, limit=None, key="chat_autorefresh")
    update_user_activity()
    with st.sidebar:
        st.title(f"{st.session_state.avatar} {st.session_state.username}")
        st.divider()
        st.subheader("🟢 Online Users")
        active_users = get_active_users()
        for user in active_users:
            st.write(user)
        st.divider()
        if st.session_state.username in ADMIN_USERNAMES:
            admin_panel()
    st.title("💬 Global Chat Room")
    messages_df = conn.query("SELECT * FROM messages ORDER BY timestamp ASC;", ttl=0)
    for _, row in messages_df.iterrows():
        with st.chat_message(name=row["username"], avatar=row["avatar"]):
            col1, col2 = st.columns([10, 1])
            with col1:
                st.markdown(f"**{row['username']}**")
                st.write(row["message"])
                reactions = json.loads(row["reactions"])
                if reactions:
                    reaction_str = " ".join([f"{emoji}{count}" for emoji, count in reactions.items()])
                    st.caption(reaction_str)
            if st.session_state.username in ADMIN_USERNAMES:
                with col2:
                    if st.button("🗑️", key=f"del_{row['id']}", help="Delete this message"):
                        with conn.session as s:
                            s.execute(text("DELETE FROM messages WHERE id = :id;"), params=dict(id=row['id']))
                            s.commit()
                        st.rerun()
            ts = pd.to_datetime(row["timestamp"])
            st.caption(f"_{ts.strftime('%b %d, %I:%M %p')}_")
    st.write("---")
    if not messages_df.empty:
        st.subheader("React to the Latest Message")
        latest_message_id = messages_df["id"].iloc[-1]
        react_cols = st.columns(3)
        if react_cols[0].button("❤️", key=f"react_love_{latest_message_id}"):
            add_reaction(latest_message_id, "❤️")
            st.rerun()
        if react_cols[1].button("👍", key=f"react_thumb_{latest_message_id}"):
            add_reaction(latest_message_id, "👍")
            st.rerun()
        if react_cols[2].button("😂", key=f"react_laugh_{latest_message_id}"):
            add_reaction(latest_message_id, "😂")
            st.rerun()
    if prompt := st.chat_input("Say something..."):
        with conn.session as s:
            s.execute(
                text("INSERT INTO messages (username, avatar, message, timestamp) VALUES (:user, :avatar, :msg, :ts);"),
                params=dict(
                    user=st.session_state.username, avatar=st.session_state.avatar,
                    msg=prompt, ts=datetime.now()
                )
            )
            s.commit()

# --- APP LOGIC ---
init_db()

# A user is only logged in if BOTH username and avatar are in the session.
if 'username' not in st.session_state or 'avatar' not in st.session_state:
    login_screen()
else:
    chat_interface()
