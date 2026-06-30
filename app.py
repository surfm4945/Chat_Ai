import os
import base64
import sqlite3
import streamlit as st
from database.connection import get_db_connection
from auth.core import authenticate_user
from chat.manager import send_message, get_chat_history, get_all_users, clear_chat_history
from ai.gemini_client import correct_grammar, generate_smart_replies, translate_text, is_ai_configured

# Page Initialization
st.set_page_config(page_title="Private AI Chat Network", page_icon="🔒", layout="wide")

# Directory Setup (exist_ok=True prevents thread-reload collision crashes)
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- AUTO-DATABASE INITIALIZATION ENGINE ---
def init_db():
    """Ensures the core database schema exists seamlessly on fresh cloud instances."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Auto-build Users table if missing (Using password_hash to match backend auth)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                recovery_phrase TEXT NOT NULL
            );
            """)
            # Auto-build Messages table if missing
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

# Execute database checks immediately on boot before auth hooks fire
init_db()

# State Management Initialization
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "Dark Mode"
if "user" not in st.session_state:
    st.session_state.user = None
if "active_chat" not in st.session_state:
    st.session_state.active_chat = None

# Premium Master Visual Theme Injection Engine
if st.session_state.theme_mode == "Light Mode":
    st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    div[data-testid="stSidebar"] { background-color: #ffffff !important; border-right: 1px solid #e2e8f0; }
    
    /* Centered Compact Login Card Layout */
    .auth-container-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 24px;
        padding: 45px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05), 0 10px 10px -5px rgba(0, 0, 0, 0.02);
        margin-top: 40px;
    }
    
    /* User-friendly Chat Bubbles */
    .chat-bubble-user { background-color: #0284c7 !important; color: white !important; border-radius: 20px 20px 4px 20px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: right; clear: both; box-shadow: 0 2px 4px rgba(0,0,0,0.04); word-wrap: break-word; font-size: 0.95rem; }
    .chat-bubble-target { background-color: #f1f5f9 !important; color: #0f172a !important; border-radius: 20px 20px 20px 4px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: left; clear: both; box-shadow: 0 2px 4px rgba(0,0,0,0.02); word-wrap: break-word; font-size: 0.95rem; }
    .chat-meta { color: #64748b; font-size: 0.78rem; margin-bottom: 3px; font-weight: 500; }
    </style>
    """, unsafe_allow_html=True)
else:
    st.markdown("""
    <style>
    .stApp { background-color: #0b0f19; color: #f1f5f9; }
    div[data-testid="stSidebar"] { background-color: #111827 !important; border-right: 1px solid #1f2937; }
    
    /* Centered Compact Login Card Layout */
    .auth-container-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 24px;
        padding: 45px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
        margin-top: 40px;
    }
    
    /* User-friendly Chat Bubbles */
    .chat-bubble-user { background-color: #38bdf8 !important; color: #0b0f19 !important; border-radius: 20px 20px 4px 20px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: right; clear: both; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.15); word-wrap: break-word; font-weight: 500; font-size: 0.95rem; }
    .chat-bubble-target { background-color: #1f2937 !important; color: #f1f5f9 !important; border-radius: 20px 20px 20px 4px !important; padding: 14px 18px; margin: 6px 0; max-width: 75%; float: left; clear: both; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); word-wrap: break-word; font-size: 0.95rem; }
    .chat-meta { color: #9ca3af; font-size: 0.78rem; margin-bottom: 3px; font-weight: 500; }
    </style>
    """, unsafe_allow_html=True)

def get_base64_encoded_file(file_path: str) -> str:
    if not file_path or not os.path.exists(file_path):
        return ""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# --- BACKEND AUTH HELPER EXTENSIONS ---
def local_register_user(username, password, recovery_phrase):
    try:
        import hashlib
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
    import hashlib
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
    uploaded_file = st.session_state.media_uploader_field
    saved_path, file_mime = None, None
    
    if uploaded_file is not None:
        saved_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
        with open(saved_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        file_mime = uploaded_file.type

    if (text or saved_path) and st.session_state.user and st.session_state.active_chat:
        send_message(st.session_state.user["id"], st.session_state.active_chat["id"], text, saved_path, file_mime)
        st.session_state.msg_input_field = ""
        st.session_state.media_uploader_field = None

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
    
    chat_container = st.container(height=450, border=True)
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


# --- MID-CENTERED SINGLE AUTHENTICATION CARD ---
if st.session_state.user is None:
    st.write("## ") 
    
    _, layout_mid_canvas, _ = st.columns([1.5, 2, 1.5])
    
    with layout_mid_canvas:
        st.markdown('<div class="auth-container-card">', unsafe_allow_html=True)
        
        st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>🏪 The Mart Network</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 0.9rem; margin-bottom: 30px;'>Secure AI-Powered Communication Matrix</p>", unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["🔑 Sign In", "📝 Create Account", "🔄 Forgot Password"])
        
        with tab1:
            st.write("#### Secure Workspace Login")
            login_user = st.text_input("Username", key="login_user_input", placeholder="Enter your identity handle...").strip()
            login_pass = st.text_input("Password", type="password", key="login_pass_input", placeholder="••••••••")
            
            st.write(" ") 
            if st.button("🚀 Pull To Access Account", type="primary", use_container_width=True):
                user_record = authenticate_user(login_user, login_pass)
                if user_record:
                    st.session_state.user = user_record
                    st.success(f"Connection authorized: Welcome back, {login_user}!")
                    st.rerun()
                else:
                    st.error("Access denied. Invalid cryptographic parameters.")
                    
        with tab2:
            st.write("#### Register Identity Node")
            reg_user = st.text_input("Choose Unique Username", key="reg_user_input", placeholder="e.g., smart_developer").strip()
            reg_pass = st.text_input("Assign Strong Password", type="password", key="reg_pass_input", placeholder="Min 6 characters")
            reg_hint = st.text_input("Secret Recovery Passphrase", type="password", placeholder="Used to restore account access if credentials lost", key="reg_hint_input")
            
            if st.button("✨ Initialize Profile", use_container_width=True):
                if len(reg_user) < 3 or len(reg_pass) < 6 or not reg_hint:
                    st.warning("Ensure requirements met: User >=3, Pass >=6, and Secret Recovery Phrase filled.")
                else:
                    success, msg = local_register_user(reg_user, reg_pass, reg_hint)
                    if success:
                        st.success(msg + " Proceed to Sign In tab.")
                    else:
                        st.error(msg)
                        
        with tab3:
            st.write("#### Credential Reclamation Desk")
            forgot_user = st.text_input("Target Account Username", key="forgot_user_input").strip()
            forgot_hint = st.text_input("Your Secret Recovery Passphrase", type="password", key="forgot_hint_input")
            forgot_new_pass = st.text_input("Assign New Password", type="password", key="forgot_new_pass_input", placeholder="Min 6 characters")
            
            if st.button("🔄 Execute Password Override", type="primary", use_container_width=True):
                if forgot_user and forgot_hint and len(forgot_new_pass) >= 6:
                    if local_reset_password(forgot_user, forgot_hint, forgot_new_pass):
                        st.success("Identity matching successful! Password updated. Proceed to Sign In.")
                    else:
                        st.error("Identity matching failed. Verification phrase is completely invalid.")
                else:
                    st.warning("Please correctly fill out all configuration blocks.")
        
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
        
        # --- EXECUTE LIVE STREAM FRAGMENT (1-SEC INTERVAL POLLING) ---
        render_live_chat_stream(current_user, target_chat)

        st.write("---")

        raw_input = st.text_input("Type message...", key="msg_input_field", placeholder="Type your message here...")
        st.file_uploader("Attach media payload", type=["png", "jpg", "jpeg", "mp4", "mov", "pdf", "txt", "docx", "zip"], key="media_uploader_field", label_visibility="collapsed")
        
        col_send, col_fix, col_lang_sel, col_trans = st.columns([2, 2, 2, 2])
        with col_send:
            st.button("🚀 Send Message / File", use_container_width=True, type="primary", on_click=callback_send_message)
        with col_fix:
            st.button("✨ Auto-Fix Grammar", use_container_width=True, on_click=callback_fix_grammar)
        with col_lang_sel:
            selected_language = st.selectbox("Language Selector", ["Urdu", "English", "Saraiki", "Punjabi", "Pashto", "Sindhi", "Arabic", "Spanish", "Turkish", "French"], label_visibility="collapsed", key="target_language_dropdown")
        with col_trans:
            st.button(f"🌐 Translate Text", use_container_width=True, on_click=callback_translate, args=(selected_language,))