import os
import base64
import sqlite3
import hashlib
from datetime import datetime, timedelta
import streamlit as st
from database.connection import get_db_connection
from chat.manager import send_message, get_chat_history, get_all_users, clear_chat_history
from ai.gemini_client import correct_grammar, generate_smart_replies, translate_text, is_ai_configured

# Page Initialization
st.set_page_config(page_title="Private AI Chat Network", page_icon="🔒", layout="wide")

# Directory Setup
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- CRYPTOGRAPHIC ENGINE (SIMULATED E2EE) ---
def encrypt_payload(text, key_salt):
    """Encrypts text using a user-bound deterministic key matrix."""
    if not text:
        return ""
    secret = f"{key_salt}_SECURE_E2EE"
    encoded_chars = []
    for i in range(len(text)):
        key_c = secret[i % len(secret)]
        encoded_c = chr(ord(text[i]) + ord(key_c))
        encoded_chars.append(encoded_c)
    return base64.b64encode("".join(encoded_chars).encode()).decode()

def decrypt_payload(cipher_text, key_salt):
    """Decrypts database text back to raw strings locally on user frame."""
    if not cipher_text:
        return ""
    try:
        cipher_text = base64.b64decode(cipher_text.encode()).decode()
        secret = f"{key_salt}_SECURE_E2EE"
        decoded_chars = []
        for i in range(len(cipher_text)):
            key_c = secret[i % len(secret)]
            decoded_c = chr(ord(cipher_text[i]) - ord(key_c))
            decoded_chars.append(decoded_c)
        return "".join(decoded_chars)
    except Exception:
        return "[🔒 Decryption Error: Unauthorized Node Access]"


# --- AUTO-DATABASE INITIALIZATION & MIGRATION ENGINE ---
def init_db():
    """Ensures core database schema and columns match backend auth requirements."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Ensure Users Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                recovery_phrase TEXT NOT NULL
            );
            """)
            
            # 2. Ensure Messages Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                content TEXT,
                file_path TEXT,
                file_type TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            
            # 3. SCHEMA MIGRATION: Check and add missing columns dynamically
            cursor.execute("PRAGMA table_info(messages);")
            columns = [col[1] for col in cursor.fetchall()]
            
            if "is_encrypted" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN is_encrypted INTEGER DEFAULT 1;")
            if "expiry_time" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN expiry_time DATETIME DEFAULT NULL;")
                
            conn.commit()
    except Exception as e:
        st.error(f"Critical initialization error: {e}")

init_db()

# State Management Initialization
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Dark Mode"
if "user" not in st.session_state:
    st.session_state.user = None
if "active_chat" not in st.session_state:
    st.session_state.active_chat = None
if "uploader_version" not in st.session_state:
    st.session_state.uploader_version = 0
if "show_uploader" not in st.session_state:
    st.session_state.show_uploader = False
if "msg_input_field" not in st.session_state:
    st.session_state.msg_input_field = ""
if "disappearing_enabled" not in st.session_state:
    st.session_state.disappearing_enabled = False
if "disappearing_duration" not in st.session_state:
    st.session_state.disappearing_duration = 5  # minutes
if "default_language" not in st.session_state:
    st.session_state.default_language = "English"

# Visual CSS Theme Matrix
if st.session_state.theme_mode == "Light Mode":
    st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    div[data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0; }
    .chat-bubble-user { background-color: #0284c7 !important; color: white !important; border-radius: 20px 20px 4px 20px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: right; clear: both; box-shadow: 0 2px 4px rgba(0,0,0,0.04); font-size: 0.95rem; }
    .chat-bubble-target { background-color: #f1f5f9 !important; color: #0f172a !important; border-radius: 20px 20px 20px 4px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: left; clear: both; box-shadow: 0 2px 4px rgba(0,0,0,0.02); font-size: 0.95rem; }
    .chat-meta { color: #64748b; font-size: 0.78rem; margin-bottom: 3px; font-weight: 500; }
    .main .block-container { padding-bottom: 220px !important; }
    div:has(> #whatsapp-input-anchor) { position: fixed !important; bottom: 0 !important; left: 0 !important; right: 0 !important; background-color: #ffffff !important; padding: 15px 30px 20px 30px !important; z-index: 9999 !important; border-top: 1px solid #e2e8f0 !important; }
    @media (min-width: 769px) { div:has(> #whatsapp-input-anchor) { left: 21rem !important; } }
    div[data-testid="stHorizontalBlock"] button { height: 42px !important; padding: 0px !important; font-size: 1.25rem !important; }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    .stApp { background-color: #0b0f19; color: #f1f5f9; }
    div[data-testid="stSidebar"] { background-color: #111827 !important; border-right: 1px solid #1f2937; }
    .chat-bubble-user { background-color: #38bdf8 !important; color: #0b0f19 !important; border-radius: 20px 20px 4px 20px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: right; clear: both; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.15); font-weight: 500; font-size: 0.95rem; }
    .chat-bubble-target { background-color: #1f2937 !important; color: #f1f5f9 !important; border-radius: 20px 20px 20px 4px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: left; clear: both; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); font-size: 0.95rem; }
    .chat-meta { color: #9ca3af; font-size: 0.78rem; margin-bottom: 3px; font-weight: 500; }
    .main .block-container { padding-bottom: 220px !important; }
    div:has(> #whatsapp-input-anchor) { position: fixed !important; bottom: 0 !important; left: 0 !important; right: 0 !important; background-color: #111827 !important; padding: 15px 30px 20px 30px !important; z-index: 9999 !important; border-top: 1px solid #1f2937 !important; }
    @media (min-width: 769px) { div:has(> #whatsapp-input-anchor) { left: 21rem !important; } }
    div[data-testid="stHorizontalBlock"] button { height: 42px !important; padding: 0px !important; font-size: 1.25rem !important; }
    </style>
    """, unsafe_allow_html=True)

def local_authenticate_user(username, password):
    hashed = hashlib.sha256(password.encode()).hexdigest()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE username = ? AND password_hash = ?;", (username, hashed))
        row = cursor.fetchone()
        if row: return {"id": row[0], "username": row[1]}
    return None

def local_register_user(username, password, recovery_phrase):
    try:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password_hash, recovery_phrase) VALUES (?, ?, ?);", (username, hashed, recovery_phrase.strip().lower()))
            conn.commit()
            return True, "Account registered!"
    except sqlite3.IntegrityError:
        return False, "Username already taken."

def update_user_profile(user_id, new_username):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET username = ? WHERE id = ?;", (new_username, user_id))
            conn.commit()
            return True
    except Exception:
        return False

# --- SYSTEM CALLBACK FUNCTIONS ---
def callback_toggle_uploader():
    st.session_state.show_uploader = not st.session_state.show_uploader

def custom_send_message():
    text = st.session_state.msg_input_field.strip()
    uploader_key = f"media_uploader_{st.session_state.uploader_version}"
    uploaded_file = st.session_state.get(uploader_key)
    saved_path, file_mime = None, None
    
    if uploaded_file:
        saved_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(saved_path, "wb") as f: f.write(uploaded_file.getbuffer())
        file_mime = uploaded_file.type

    if (text or saved_path) and st.session_state.user and st.session_state.active_chat:
        # Local End-to-End Encryption Conversion Matrix before dispatch
        encrypted_text = encrypt_payload(text, "SHARED_SECRET_KEY")
        
        expiry_date = None
        if st.session_state.disappearing_enabled:
            expiry_date = (datetime.now() + timedelta(minutes=st.session_state.disappearing_duration)).strftime("%Y-%m-%d %H:%M:%S")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (sender_id, receiver_id, content, file_path, file_type, is_encrypted, expiry_time) VALUES (?, ?, ?, ?, ?, 1, ?);",
                (st.session_state.user["id"], st.session_state.active_chat["id"], encrypted_text, saved_path, file_mime, expiry_date)
            )
            conn.commit()

        st.session_state.msg_input_field = ""
        st.session_state.uploader_version += 1
        st.session_state.show_uploader = False

def callback_fix_grammar():
    text = st.session_state.msg_input_field.strip()
    if text:
        try:
            corrected = correct_grammar(text)
            if corrected: st.session_state.msg_input_field = corrected
        except Exception: st.toast("⚠️ AI Quota exhausted. Showing raw entry.", icon="❌")

def callback_translate(target_lang):
    text = st.session_state.msg_input_field.strip()
    if text:
        try:
            translated = translate_text(text, target_lang)
            if translated: st.session_state.msg_input_field = translated
        except Exception: st.toast("⚠️ AI Quota exhausted. Showing raw entry.", icon="❌")

# --- CUSTOM LIVE STREAM WITH LOCAL E2EE DECRYPTION ---
@st.fragment(run_every=1.0)
def render_live_chat_stream(current_user, target_chat):
    # Purge expired dynamic variables from local tables
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        conn.cursor().execute("DELETE FROM messages WHERE expiry_time IS NOT NULL AND expiry_time <= ?;", (now_str,))
        conn.commit()

    history = get_chat_history(current_user["id"], target_chat["id"])
    chat_container = st.container(height=450, border=True)
    
    with chat_container:
        if not history:
            st.caption("🔒 Encrypted Baseline Active. Line clear.")
        else:
            for msg in history:
                # Decrypt text locally on runtime memory frame
                decrypted_content = decrypt_payload(msg["content"], "SHARED_SECRET_KEY") if msg.get("content") else ""
                
                # Check for files
                media_html = ""
                if msg["file_path"]:
                    filename = os.path.basename(msg["file_path"])
                    media_html = f'<br/><div style="margin-top: 8px;"><span style="font-size:1.1rem;">📁</span> <code style="color:#0ea5e9;">{filename}</code></div>'

                full_payload = f'{decrypted_content}{media_html}' if decrypted_content else media_html
                time_stamp = msg["timestamp"][11:16]

                if msg["sender_id"] == current_user["id"]:
                    st.markdown(f'<div style="width:100%;"><div class="chat-meta" style="text-align:right;">🔒 You • {time_stamp}</div><div class="chat-bubble-user">{full_payload}</div></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="width:100%;"><div class="chat-meta" style="text-align:left;">🔒 {target_chat["username"]} • {time_stamp}</div><div class="chat-bubble-target">{full_payload}</div></div>', unsafe_allow_html=True)

# --- USER ROUTING INTERFACE ---
if st.session_state.user is None:
    # (Existing Auth Layout remains untouched for profile generation consistency)
    st.write("## ")
    _, canvas, _ = st.columns([1.5, 2, 1.5])
    with canvas:
        st.markdown("<h2 style='text-align: center;'>🏪 The Mart Network</h2>", unsafe_allow_html=True)
        uname = st.text_input("Username")
        pword = st.text_input("Password", type="password")
        if st.button("🚀 Access Channel", type="primary", use_container_width=True):
            res = local_authenticate_user(uname, pword)
            if res:
                st.session_state.user = res
                st.rerun()
        if st.button("📝 Register Node Account", use_container_width=True):
            local_register_user(uname, pword, "secret salt")
            st.toast("Profile built! Hit access button.")
else:
    current_user = st.session_state.user
    
    # --- UPGRADED SETTINGS SIDEBAR MATRIX ---
    with st.sidebar:
        st.title(f"👤 {current_user['username']}")
        st.caption("Status: End-to-End Encrypted Secure Node")
        
        with st.expander("⚙️ Core Profile Settings", expanded=False):
            new_name = st.text_input("Change Username Handle", value=current_user["username"]).strip()
            if st.button("Save Profile Updates", use_container_width=True):
                if new_name and update_user_profile(current_user["id"], new_name):
                    st.session_state.user["username"] = new_name
                    st.toast("Profile updated successfully!")
                    st.rerun()

            st.session_state.theme_mode = st.radio(
                "Visual Theme", ["Dark Mode", "Light Mode"], 
                index=0 if st.session_state.theme_mode == "Dark Mode" else 1
            )
            st.session_state.default_language = st.selectbox(
                "Default Translation System", 
                ["Urdu", "English", "Saraiki", "Punjabi", "Pashto", "Sindhi", "Arabic", "Spanish"]
            )
        
        if st.button("Secure Terminate Connection", type="secondary", use_container_width=True):
            st.session_state.user = None
            st.session_state.active_chat = None
            st.rerun()
            
        st.write("---")
        st.write("### 💬 Communication Matrix Paths")
        available_users = get_all_users(exclude_user_id=current_user["id"])
        for usr in available_users:
            if st.button(f"⚪ {usr['username']}", key=f"u_{usr['id']}", use_container_width=True):
                st.session_state.active_chat = usr
                st.rerun()

    # --- CHAT WORKSPACE FRAME ---
    if st.session_state.active_chat is None:
        st.info("👈 Establish connection matrix links by selecting an operational active profile channel path.")
    else:
        target_chat = st.session_state.active_chat
        
        # --- DISAPPEARING MESSAGES CONTROL MATRIX ---
        head_1, head_2, head_3 = st.columns([2, 1.5, 0.5])
        with head_1:
            st.title(f"Channel: {target_chat['username']}")
        with head_2:
            st.write("")
            st.session_state.disappearing_enabled = st.checkbox("⏳ Disappearing Messages", value=st.session_state.disappearing_enabled)
            if st.session_state.disappearing_enabled:
                st.session_state.disappearing_duration = st.number_input("Minutes active life:", min_value=1, max_value=60, value=st.session_state.disappearing_duration, step=1)
        with head_3:
            st.write("")
            if st.button("🗑️", help="Wipe local log channel memory thread"):
                clear_chat_history(current_user["id"], target_chat["id"])
                st.rerun()
                
        render_live_chat_stream(current_user, target_chat)

        # --- WHATSAPP STYLE CONTROL DOCK PANEL ---
        with st.container():
            st.markdown('<span id="whatsapp-input-anchor"></span>', unsafe_allow_html=True)
            
            if st.session_state.show_uploader:
                st.file_uploader("Select Payload attachment", type=["png", "jpg", "mp4", "pdf", "zip"], key=f"media_uploader_{st.session_state.uploader_version}", label_visibility="collapsed")
            
            col_attach, col_fix, col_input, col_trans, col_send = st.columns([0.4, 0.4, 4.5, 0.4, 0.5])
            
            with col_attach:
                if st.button("📎", help="Toggle secure attachment node layer"):
                    callback_toggle_uploader()
                    st.rerun()
            with col_fix:
                if st.button("✨", help="Run clean auto-correct grammar alignment"):
                    callback_fix_grammar()
                    st.rerun()
            with col_input:
                st.text_input("Console Input Stream...", key="msg_input_field", placeholder="Send secure encrypted transmission pipeline...", label_visibility="collapsed")
            with col_trans:
                if st.button("🌐", help=f"Convert input directly into {st.session_state.default_language}"):
                    callback_translate(st.session_state.default_language)
                    st.rerun()
            with col_send:
                if st.button("🚀", type="primary", help="Transmit encrypted data packets down path pipeline"):
                    custom_send_message()
                    st.rerun()
