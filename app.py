import os
import base64
import sqlite3
import hashlib
import streamlit as st
from database.connection import get_db_connection
from chat.manager import send_message, get_chat_history, get_all_users, clear_chat_history
from ai.gemini_client import correct_grammar, generate_smart_replies, translate_text, is_ai_configured
from utils.emailer import send_verification_otp  # External import configuration

# Page Initialization
st.set_page_config(page_title="Private AI Chat Network", page_icon="🔒", layout="wide")

# Directory Setup
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# --- AUTO-DATABASE INITIALIZATION & MIGRATION ENGINE ---
def init_db():
    """Ensures core database schema and columns match backend auth requirements perfectly."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Base table creation
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                recovery_phrase TEXT NOT NULL
            );
            """)
            
            # 2. PRAGMA Live Column Migration
            cursor.execute("PRAGMA table_info(users);")
            columns = [col[1] for col in cursor.fetchall()]
            
            if "password" in columns and "password_hash" not in columns:
                cursor.execute("ALTER TABLE users RENAME COLUMN password TO password_hash;")
            elif "password_hash" not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT NOT NULL DEFAULT '';")
                
            if "recovery_phrase" not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN recovery_phrase TEXT NOT NULL DEFAULT '';")

            # 3. Create Messages table
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
            conn.commit()
    except Exception as e:
        st.error(f"Critical initialization error: {e}")

# Execute database checks and migrations immediately on boot
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

# Premium Master Visual Theme & Sticky Input Override Matrix
if st.session_state.theme_mode == "Light Mode":
    st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    div[data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0; }
    .auth-container-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 24px;
        padding: 45px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02);
        margin-top: 40px;
    }
    .chat-bubble-user { background-color: #0284c7 !important; color: white !important; border-radius: 20px 20px 4px 20px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: right; clear: both; box-shadow: 0 2px 4px rgba(0,0,0,0.04); word-wrap: break-word; font-size: 0.95rem; }
    .chat-bubble-target { background-color: #f1f5f9 !important; color: #0f172a !important; border-radius: 20px 20px 20px 4px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: left; clear: both; box-shadow: 0 2px 4px rgba(0,0,0,0.02); word-wrap: break-word; font-size: 0.95rem; }
    .chat-meta { color: #64748b; font-size: 0.78rem; margin-bottom: 3px; font-weight: 500; }
    
    /* Dynamic Screen Safety Space Padding */
    .main .block-container { padding-bottom: 260px !important; }
    
    /* WhatsApp Frozen Console Engine */
    div:has(> #whatsapp-input-anchor) {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        background-color: #ffffff !important;
        padding: 15px 30px 25px 30px !important;
        z-index: 9999 !important;
        border-top: 1px solid #e2e8f0 !important;
        box-shadow: 0 -10px 25px rgba(15, 23, 42, 0.05) !important;
    }
    @media (min-width: 769px) {
        div:has(> #whatsapp-input-anchor) { left: 21rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    .stApp { background-color: #0b0f19; color: #f1f5f9; }
    div[data-testid="stSidebar"] { background-color: #111827 !important; border-right: 1px solid #1f2937; }
    .auth-container-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 24px;
        padding: 45px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        margin-top: 40px;
    }
    .chat-bubble-user { background-color: #38bdf8 !important; color: #0b0f19 !important; border-radius: 20px 20px 4px 20px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: right; clear: both; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.15); word-wrap: break-word; font-weight: 500; font-size: 0.95rem; }
    .chat-bubble-target { background-color: #1f2937 !important; color: #f1f5f9 !important; border-radius: 20px 20px 20px 4px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: left; clear: both; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); word-wrap: break-word; font-size: 0.95rem; }
    .chat-meta { color: #9ca3af; font-size: 0.78rem; margin-bottom: 3px; font-weight: 500; }
    
    /* Dynamic Screen Safety Space Padding */
    .main .block-container { padding-bottom: 260px !important; }
    
    /* WhatsApp Frozen Console Engine */
    div:has(> #whatsapp-input-anchor) {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        background-color: #111827 !important;
        padding: 15px 30px 25px 30px !important;
        z-index: 9999 !important;
        border-top: 1px solid #1f2937 !important;
        box-shadow: 0 -12px 30px rgba(0, 0, 0, 0.4) !important;
    }
    @media (min-width: 769px) {
        div:has(> #whatsapp-input-anchor) { left: 21rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

def get_base64_encoded_file(file_path: str) -> str:
    if not file_path or not os.path.exists(file_path):
        return ""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# --- UNIFIED LOCAL CRYPTOGRAPHIC AUTH MATRIX ---
def local_authenticate_user(username, password):
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username FROM users WHERE username = ? AND password_hash = ?;", (username, hashed_password))
            row = cursor.fetchone()
            if row:
                return {"id": row[0], "username": row[1]}
    except Exception as e:
        st.error(f"Authentication module error: {e}")
    return None

def local_register_user(username, password, recovery_phrase):
    try:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, recovery_phrase) VALUES (?, ?, ?);",
                (username, hashed_password, recovery_phrase.strip().lower())
            )
            conn.commit()
            return True, "Account configured successfully!"
    except sqlite3.IntegrityError:
        return False, "Username is already occupied on this node network."
    except Exception as e:
        return False, f"Database error: {e}"

def local_reset_password(username, recovery_phrase, new_password):
    hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
    query_verify = "SELECT id FROM users WHERE username = ? AND recovery_phrase = ?;"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query_verify, (username, recovery_phrase.strip().lower()))
        user = cursor.fetchone()
        if user:
            cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?;", (hashed_password, user[0]))
            conn.commit()
            return True
        return False


# --- STATE CALLBACK FUNCTIONS ---
def callback_send_message():
    text = st.session_state.msg_input_field.strip()
    uploader_key = f"media_uploader_{st.session_state.uploader_version}"
    uploaded_file = st.session_state.get(uploader_key)
    saved_path, file_mime = None, None
    
    if uploaded_file is not None:
        saved_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(saved_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        file_mime = uploaded_file.type

    if (text or saved_path) and st.session_state.user and st.session_state.active_chat:
        send_message(st.session_state.user["id"], st.session_state.active_chat["id"], text, saved_path, file_mime)
        st.session_state.msg_input_field = ""
        st.session_state.uploader_version += 1

def callback_fix_grammar():
    text = st.session_state.msg_input_field.strip()
    if text:
        st.session_state.msg_input_field = correct_grammar(text)

def callback_translate(target_lang):
    text = st.session_state.msg_input_field.strip()
    if text:
        st.session_state.msg_input_field = translate_text(text, target_lang)

def callback_wipe_history():
    if st.session_state.user and st.session_state.active_chat:
        clear_chat_history(st.session_state.user["id"], st.session_state.active_chat["id"])


# --- HIGH-ACCURACY ISOLATED STREAM ENGINE ---
@st.fragment(run_every=1.0)
def render_live_chat_stream(current_user, target_chat):
    history = get_chat_history(current_user["id"], target_chat["id"])
    
    chat_container = st.container(height=480, border=True)
    with chat_container:
        if not history:
            st.caption("Encrypted baseline linked. Transmission thread is blank.")
        else:
            for msg in history:
                media_html = ""
                if msg["file_path"] and msg["file_type"]:
                    b64_stream = get_base64_encoded_file(msg["file_path"])
                    filename = os.path.basename(msg["file_path"])
                    if b64_stream:
                        if msg["file_type"].startswith("image/"):
                            media_html = f'<br/><img src="data:{msg["file_type"]};base64,{b64_stream}" style="max-width: 280px; border-radius: 12px; margin-top: 8px; display: block;"/>'
                        elif msg["file_type"].startswith("video/"):
                            media_html = f'<br/><video controls style="max-width: 320px; border-radius: 12px; margin-top: 8px; display: block;"><source src="data:{msg["file_type"]};base64,{b64_stream}" type="{msg["file_type"]}"></video>'
                        else:
                            media_html = f'<br/><div style="margin-top: 8px; background: rgba(0,0,0,0.05); padding: 8px; border-radius: 6px;"><a href="data:{msg["file_type"]};base64,{b64_stream}" download="{filename}" style="color: #0ea5e9; font-weight: bold; text-decoration: underline;">📁 Download {filename}</a></div>'
                    else:
                        media_html = '<br/><span style="color: red; font-size: 0.8rem;">⚠️ Attachment missing</span>'

                full_payload = f'{msg["content"]}{media_html}' if msg["content"] else media_html

                if msg["sender_id"] == current_user["id"]:
                    st.markdown(f'<div style="width: 100%;"><div class="chat-meta" style="text-align: right;">You • {msg["timestamp"][11:16]}</div><div class="chat-bubble-user">{full_payload}</div></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="width: 100%;"><div class="chat-meta" style="text-align: left;">{target_chat["username"]} • {msg["timestamp"][11:16]}</div><div class="chat-bubble-target">{full_payload}</div></div>', unsafe_allow_html=True)

    if history and history[-1]["sender_id"] != current_user["id"] and history[-1]["content"]:
        last_incoming_msg = history[-1]["content"]
        if is_ai_configured():
            st.write("💡 *Gemini AI Contextual Suggestions:*")
            raw_replies = generate_smart_replies(last_incoming_msg)
            options = [opt.strip() for opt in raw_replies.split("|") if opt.strip()]
            cols = st.columns(len(options) if options else 1)
            for idx, opt in enumerate(options):
                if idx < len(cols):
                    if cols[idx].button(opt, key=f"suggest_{idx}", use_container_width=True):
                        send_message(current_user["id"], target_chat["id"], opt)
                        st.rerun()


# --- MID-CENTERED DYNAMIC AUTHENTICATION ENGINE ---
if st.session_state.user is None:
    st.write("## ") 
    
    _, layout_mid_canvas, _ = st.columns([1.5, 2, 1.5])
    
    with layout_mid_canvas:
        st.markdown('<div class="auth-container-card">', unsafe_allow_html=True)
        
        st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>🏪 The Mart Network</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 0.9rem; margin-bottom: 25px;'>Secure AI-Powered Communication Matrix</p>", unsafe_allow_html=True)
        
        if "auth_page" not in st.session_state:
            st.session_state.auth_page = "Sign In"
        if "otp_verified_code" not in st.session_state:
            st.session_state.otp_verified_code = None
        if "otp_sent_success" not in st.session_state:
            st.session_state.otp_sent_success = False

        # --- VIEW 1: SIGN IN SCREEN ---
        if st.session_state.auth_page == "Sign In":
            st.write("#### 🔑 Secure Workspace Login")
            login_user = st.text_input("Username", key="login_user_input", placeholder="Enter your identity handle...").strip()
            login_pass = st.text_input("Password", type="password", key="login_pass_input", placeholder="••••••••")
            
            st.write(" ") 
            if st.button("🚀 Pull To Access Account", type="primary", use_container_width=True):
                user_record = local_authenticate_user(login_user, login_pass)
                if user_record:
                    st.session_state.user = user_record
                    st.success(f"Connection authorized: Welcome back, {login_user}!")
                    st.rerun()
                else:
                    st.error("Access denied. Invalid cryptographic parameters.")
            
            st.write("---")
            col_to_reg, col_to_forgot = st.columns([1, 1])
            with col_to_reg:
                if st.button("📝 Create Account", use_container_width=True):
                    st.session_state.auth_page = "Create Account"
                    st.rerun()
            with col_to_forgot:
                if st.button("🔄 Forgot Password", use_container_width=True):
                    st.session_state.auth_page = "Forgot Password"
                    st.rerun()

        # --- VIEW 2: CREATE ACCOUNT WITH AUTOMATIC REDIRECT ROUTING ---
        elif st.session_state.auth_page == "Create Account":
            st.write("#### 📝 Register Identity Node")
            reg_user = st.text_input("Choose Unique Username", key="reg_user_input", placeholder="e.g., sami11").strip()
            reg_pass = st.text_input("Assign Strong Password", type="password", key="reg_pass_input", placeholder="Min 6 characters")
            reg_email = st.text_input("Gmail Address for Verification", placeholder="username@gmail.com", key="reg_email_input").strip()
            reg_hint = st.text_input("Secret Recovery Passphrase", type="password", placeholder="Used to restore account access if credentials lost", key="reg_hint_input")
            
            if not st.session_state.otp_sent_success:
                if st.button("📧 Send Verification Code", use_container_width=True, type="primary"):
                    if len(reg_user) < 3 or len(reg_pass) < 6 or not reg_email or not reg_hint:
                        st.warning("Ensure requirements met: User >=3, Pass >=6, Email & Recovery phrase filled.")
                    elif "@gmail.com" not in reg_email.lower():
                        st.error("Please supply a valid Gmail routing address.")
                    else:
                        with st.spinner("Dispatching secure credential tokens..."):
                            success, result = send_verification_otp(reg_email)
                            if success:
                                st.session_state.otp_verified_code = result
                                st.session_state.otp_sent_success = True
                                st.success(f"Verification code successfully dispatched to {reg_email}!")
                                st.rerun()
                            else:
                                st.error(f"Email delivery subsystem failed: {result}")
                
                if st.button("⬅️ Back to Login", use_container_width=True):
                    st.session_state.auth_page = "Sign In"
                    st.rerun()
            
            else:
                st.info(f"Verification code active. Check your email inbox: {reg_email}")
                user_otp_attempt = st.text_input("Enter 6-Digit OTP Code Verification", max_chars=6, placeholder="######", key="user_otp_input_field").strip()
                
                col_back, col_confirm = st.columns([1, 1])
                with col_back:
                    if st.button("⬅️ Change Details", use_container_width=True):
                        st.session_state.otp_sent_success = False
                        st.session_state.otp_verified_code = None
                        st.rerun()
                        
                with col_confirm:
                    if st.button("✨ Verify & Create Profile", type="primary", use_container_width=True):
                        if user_otp_attempt == st.session_state.otp_verified_code:
                            success, msg = local_register_user(reg_user, reg_pass, reg_hint)
                            if success:
                                st.session_state.otp_sent_success = False
                                st.session_state.otp_verified_code = None
                                st.session_state.auth_page = "Sign In" 
                                st.toast("Account verified successfully! Please sign in.")
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.error("Verification mismatch. Code token is completely invalid.")

        # --- VIEW 3: CREDENTIAL RECOVERY DESK ---
        elif st.session_state.auth_page == "Forgot Password":
            st.write("#### 🔄 Credential Reclamation Desk")
            forgot_user = st.text_input("Target Account Username", key="forgot_user_input").strip()
            forgot_hint = st.text_input("Your Secret Recovery Passphrase", type="password", key="forgot_hint_input")
            forgot_new_pass = st.text_input("Assign New Password", type="password", key="forgot_new_pass_input", placeholder="Min 6 characters")
            
            if st.button("🔄 Execute Password Override", type="primary", use_container_width=True):
                if forgot_user and forgot_hint and len(forgot_new_pass) >= 6:
                    if local_reset_password(forgot_user, forgot_hint, forgot_new_pass):
                        st.toast("Password updated successfully!")
                        st.session_state.auth_page = "Sign In"
                        st.rerun()
                    else:
                        st.error("Identity matching failed. Verification phrase is completely invalid.")
                else:
                    st.warning("Please correctly fill out all configuration blocks.")
                    
            if st.button("⬅️ Back to Login", use_container_width=True):
                st.session_state.auth_page = "Sign In"
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

# --- MAIN RUNTIME APPLICATION INTERFACE ---
else:
    current_user = st.session_state.user
    
    with st.sidebar:
        st.title(f"👤 {current_user['username']}")
        st.caption("Secure Connection Profile: Operational")
        
        st.session_state.theme_mode = st.radio(
            "🌓 Visual Theme Mode", ["Dark Mode", "Light Mode"], 
            index=0 if st.session_state.theme_mode == "Dark Mode" else 1, horizontal=True
        )
        
        if st.button("Secure Log Out", type="secondary", use_container_width=True):
            st.session_state.user = None
            st.session_state.active_chat = None
            st.rerun()
            
        st.write("---")
        st.write("### 💬 Active Communications")
        
        available_users = get_all_users(exclude_user_id=current_user["id"])
        if not available_users:
            st.info("No external nodes detected.")
        else:
            for user in available_users:
                is_current = st.session_state.active_chat and st.session_state.active_chat["id"] == user["id"]
                button_label = f"🔵 {user['username']}" if is_current else f"⚪ {user['username']}"
                if st.button(button_label, key=f"user_{user['id']}", use_container_width=True):
                    st.session_state.active_chat = user
                    st.rerun()

    if st.session_state.active_chat is None:
        st.title("Secure Private Workspace")
        st.info("👈 Select an operational channel from the user directory panel to establish communication links.")
    else:
        target_chat = st.session_state.active_chat
        
        col_title, col_wipe = st.columns([3, 1])
        with col_title:
            st.title(f"Channel: {target_chat['username']}")
        with col_wipe:
            st.write("") 
            st.button("🗑️ Forget History", type="secondary", use_container_width=True, help="Permanently destroy entire logs of this channel", on_click=callback_wipe_history)
        
        # Render scrollable history stream
        render_live_chat_stream(current_user, target_chat)

        # --- WHATSAPP STYLE STICKY FOOTER TOOLBAR ---
        with st.container():
            # Core identification CSS anchor tag
            st.markdown('<span id="whatsapp-input-anchor"></span>', unsafe_allow_html=True)
            
            # Row 1: Message Input + Send Command Icon Button
            col_msg_field, col_action_send = st.columns([5, 1])
            with col_msg_field:
                raw_input = st.text_input("Type message...", key="msg_input_field", placeholder="Type a message here...", label_visibility="collapsed")
            with col_action_send:
                st.button("🚀 Send", use_container_width=True, type="primary", on_click=callback_send_message)
            
            # Row 2: Media File Input Attachment Lane
            current_uploader_key = f"media_uploader_{st.session_state.uploader_version}"
            st.file_uploader("Attach media payload", type=["png", "jpg", "jpeg", "mp4", "mov", "pdf", "txt", "docx", "zip"], key=current_uploader_key, label_visibility="collapsed")
            
            # Row 3: Utility Control Action Bar (Grammar Correction & Real-time Translation)
            col_ai_fix, col_lang_menu, col_run_trans = st.columns([2, 2, 2])
            with col_ai_fix:
                st.button("✨ Auto-Fix Grammar", use_container_width=True, on_click=callback_fix_grammar)
            with col_lang_menu:
                selected_language = st.selectbox("Language Selector", ["Urdu", "English", "Saraiki", "Punjabi", "Pashto", "Sindhi", "Arabic", "Spanish", "Turkish", "French"], label_visibility="collapsed", key="target_language_dropdown")
            with col_run_trans:
                st.button("🌐 Translate Text", use_container_width=True, on_click=callback_translate, args=(selected_language,))
