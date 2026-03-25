import streamlit as st
import tempfile, os, time, queue, threading

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="AudioMind", page_icon="🎙️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;800&family=JetBrains+Mono:wght@300;400&display=swap');

html, body, [class*="css"] {
    font-family: 'JetBrains Mono', monospace;
    background: #0a0a0f;
    color: #e8e8f0;
}
h1, h2, h3 { font-family: 'Syne', sans-serif !important; letter-spacing: -0.02em; }
.stApp { background: #0a0a0f; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0d0d1a !important;
    border-right: 1px solid #1e1e3a !important;
}
[data-testid="stSidebar"] * { color: #e8e8f0 !important; }

.nav-btn {
    display: block; width: 100%; text-align: left;
    background: transparent; border: none;
    padding: 12px 16px; margin: 4px 0;
    border-radius: 10px; cursor: pointer;
    font-family: 'Syne', sans-serif; font-size: 14px; font-weight: 600;
    color: #6a6a9a; transition: all 0.2s;
    letter-spacing: 0.03em;
}
.nav-btn:hover { background: #1a1a30; color: #e8e8f0; }
.nav-btn.active { background: #1e1e40; color: #818cf8; border-left: 3px solid #818cf8; }
.nav-btn.disabled { opacity: 0.3; cursor: not-allowed; }

/* ── Log box ── */
.log-box {
    background: #0d0d1a; border: 1px solid #1e1e3a; border-radius: 12px;
    padding: 20px 24px; font-size: 13px; line-height: 2.1;
    font-family: 'JetBrains Mono', monospace; max-height: 360px; overflow-y: auto;
}
.log-done   { color: #6ee7b7; }
.log-active { color: #fbbf24; }
.log-error  { color: #f87171; }

/* ── Chat bubbles ── */
.bubble-user {
    background: #1a1a35; border: 1px solid #2a2a55;
    border-radius: 16px 16px 4px 16px;
    padding: 12px 18px; margin: 8px 0 8px 60px;
    font-size: 14px; color: #c8c8f0;
}
.bubble-bot {
    background: #111128; border: 1px solid #1e1e40;
    border-radius: 16px 16px 16px 4px;
    padding: 12px 18px; margin: 8px 60px 8px 0;
    font-size: 14px; color: #e0e0f8; white-space: pre-wrap;
}

/* ── Buttons ── */
.stButton > button {
    font-family: 'Syne', sans-serif !important; font-weight: 600;
    border-radius: 10px; border: none; padding: 10px 28px;
    letter-spacing: 0.03em;
}
.stProgress > div > div {
    background: linear-gradient(90deg, #6ee7b7, #818cf8);
    border-radius: 4px;
}

/* ── Inputs ── */
.stTextInput > div > div > input {
    background: #11111e; border: 1px solid #2a2a50; border-radius: 10px;
    color: #e8e8f0; font-family: 'JetBrains Mono', monospace;
    font-size: 14px; padding: 12px 16px;
}
.stFileUploader > div {
    background: #11111e; border: 1.5px dashed #2a2a50; border-radius: 16px;
}

/* ── Mode badge ── */
.mode-badge {
    display: inline-block; font-family: 'Syne', sans-serif;
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.12em; text-transform: uppercase;
    padding: 4px 12px; border-radius: 20px; margin-bottom: 16px;
}
.badge-upload { background: #1a1a35; color: #818cf8; border: 1px solid #2a2a60; }
.badge-chat   { background: #0f2a1e; color: #6ee7b7; border: 1px solid #1a4a35; }
.badge-reset  { background: #2a1a0a; color: #fbbf24; border: 1px solid #4a3010; }

/* ── Status pill ── */
.status-pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 12px; border-radius: 20px;
    font-size: 11px; font-family: 'Syne', sans-serif;
    font-weight: 700; letter-spacing: 0.08em; margin-bottom: 24px;
}
.pill-ready  { background: #0f2a1e; color: #6ee7b7; border: 1px solid #1a4a35; }
.pill-empty  { background: #1a1a2e; color: #4a4a7a; border: 1px solid #2a2a4a; }
</style>
""", unsafe_allow_html=True)


# ── Session state init ─────────────────────────────────────────────────────────
def _init_state():
    defaults = {
        "mode": "upload",           # upload | processing | chat | reset
        "db_ready": False,          # True once first upload succeeds
        "chat_history": [],
        "audio_path": None,
        "log_lines": [],
        "progress": 0,
        "pipeline_done": False,
        "pipeline_error": False,
        "pipeline_running": False,
        "chat_input_key": 0,        # increment to force-clear the input widget
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ── Helpers ────────────────────────────────────────────────────────────────────
def css_for(msg: str) -> str:
    m = msg.lower()
    if any(x in m for x in ["✅", "ready", "done"]):   return "done"
    if any(x in m for x in ["❌", "error", "failed"]): return "error"
    return "active"

def render_log(lines):
    html = "".join(f'<div class="log-{css}">{msg}</div>' for msg, css in lines)
    return f'<div class="log-box">{html}</div>'


# ── Sidebar navigation ─────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🎙️ AudioMind")
        st.markdown('<hr style="border-color:#1e1e3a;margin:12px 0 20px">', unsafe_allow_html=True)

        db_ready = st.session_state.db_ready

        # Status pill
        if db_ready:
            st.markdown('<span class="status-pill pill-ready">● DB READY</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-pill pill-empty">○ NO DATA YET</span>', unsafe_allow_html=True)

        st.markdown("**Navigation**")

        processing = st.session_state.pipeline_running  # lock nav while pipeline runs

        if processing:
            st.markdown(
                '<div style="background:#1a1a0a;border:1px solid #4a3010;border-radius:8px;'
                'padding:8px 12px;font-size:11px;color:#fbbf24;margin-bottom:8px;">'
                '⏳ Processing… navigation locked</div>',
                unsafe_allow_html=True
            )

        # Upload
        upload_active = st.session_state.mode in ("upload", "processing")
        if st.button(
            ("▶ " if upload_active else "  ") + "Upload Audio",
            key="nav_upload",
            use_container_width=True,
            type="primary" if upload_active else "secondary",
            disabled=processing,   # 🔒 locked while running
        ):
            st.session_state.mode = "upload"
            st.rerun()

        # Chat — disabled until DB is ready OR while processing
        chat_active = st.session_state.mode == "chat"
        if db_ready and not processing:
            if st.button(
                ("▶ " if chat_active else "  ") + "Chat",
                key="nav_chat",
                use_container_width=True,
                type="primary" if chat_active else "secondary",
            ):
                st.session_state.mode = "chat"
                st.rerun()
        else:
            label = "  Processing…" if processing else "  Chat  (upload first)"
            st.button(label, key="nav_chat_dis", use_container_width=True, disabled=True)

        # Reset — disabled until DB is ready OR while processing
        reset_active = st.session_state.mode == "reset"
        if db_ready and not processing:
            if st.button(
                ("▶ " if reset_active else "  ") + "Reset DB",
                key="nav_reset",
                use_container_width=True,
                type="primary" if reset_active else "secondary",
            ):
                st.session_state.mode = "reset"
                st.rerun()
        else:
            label = "  Processing…" if processing else "  Reset DB  (upload first)"
            st.button(label, key="nav_reset_dis", use_container_width=True, disabled=True)

        st.markdown('<hr style="border-color:#1e1e3a;margin:20px 0 12px">', unsafe_allow_html=True)
        st.markdown('<p style="color:#3a3a6a;font-size:11px;">AudioMind v1.0</p>', unsafe_allow_html=True)


# ── UPLOAD MODE ────────────────────────────────────────────────────────────────
def upload_mode():
    st.markdown('<span class="mode-badge badge-upload">▲ Upload Mode</span>', unsafe_allow_html=True)
    st.markdown("## Upload Audio")
    if st.session_state.db_ready:
        st.markdown('<p style="color:#4a4a7a;font-size:13px;margin-top:-12px;">Uploading more audio will <b>add</b> to the existing knowledge base.</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="color:#4a4a7a;font-size:13px;margin-top:-12px;">Drop an audio file to build your knowledge base.</p>', unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Upload audio",
        type=["mp3", "mp4", "wav", "m4a", "ogg", "flac", "webm"],
        label_visibility="collapsed",
    )

    if uploaded:
        if st.button("⚡ Process Audio", use_container_width=True, type="primary"):
            suffix = os.path.splitext(uploaded.name)[1]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(uploaded.read())
            tmp.close()

            st.session_state.audio_path      = tmp.name
            st.session_state.log_lines       = []
            st.session_state.progress        = 0
            st.session_state.pipeline_done   = False
            st.session_state.pipeline_error  = False
            st.session_state.pipeline_running = True
            st.session_state.mode            = "processing"
            st.rerun()


# ── PROCESSING MODE ────────────────────────────────────────────────────────────
def processing_mode():
    st.markdown('<span class="mode-badge badge-upload">⏳ Processing</span>', unsafe_allow_html=True)
    st.markdown("## Building Knowledge Base")
    st.markdown('<p style="color:#4a4a7a;font-size:13px;margin-top:-12px;">Live progress below.</p>', unsafe_allow_html=True)

    progress_bar = st.progress(st.session_state.progress / 100)
    log_slot     = st.empty()

    if st.session_state.pipeline_running:
        from mainGraph import run_ingestion

        collected_lines = []
        collected_pct   = [0]
        msg_queue       = queue.Queue()
        error_holder    = [None]

        # ✅ Capture before thread — never touch session_state inside thread
        audio_path = st.session_state.audio_path

        def on_progress(msg: str, pct: int):
            msg_queue.put((msg, pct))   # thread-safe; NO Streamlit calls here

        def run_pipeline():
            try:
                run_ingestion(audio_path=audio_path, progress_cb=on_progress)
            except Exception as e:
                import traceback
                error_holder[0] = traceback.format_exc()
                msg_queue.put((f"❌ Error: {e}", -1))
            finally:
                msg_queue.put(None)   # sentinel

        t = threading.Thread(target=run_pipeline, daemon=True)
        t.start()

        # Main thread drains queue → safe to update Streamlit UI
        while True:
            item = msg_queue.get()
            if item is None:
                break
            msg, pct = item
            css = css_for(msg)
            collected_lines.append((msg, css))
            if pct >= 0:
                collected_pct[0] = pct
            progress_bar.progress(collected_pct[0] / 100)
            log_slot.markdown(render_log(collected_lines), unsafe_allow_html=True)

        t.join()

        st.session_state.log_lines        = collected_lines
        st.session_state.progress         = collected_pct[0]
        st.session_state.pipeline_running = False

        if error_holder[0]:
            st.session_state.pipeline_error = True
        else:
            st.session_state.pipeline_done = True
            st.session_state.db_ready      = True   # ✅ unlock Chat + Reset

        st.rerun()

    else:
        progress_bar.progress(st.session_state.progress / 100)
        log_slot.markdown(render_log(st.session_state.log_lines), unsafe_allow_html=True)

        if st.session_state.pipeline_done:
            st.success("✅ Knowledge base ready!")
            if st.button("💬 Start Chatting →", use_container_width=True, type="primary"):
                st.session_state.mode = "chat"
                st.rerun()

        elif st.session_state.pipeline_error:
            st.error("Pipeline failed. Check the log above.")
            if st.button("↩ Try Again", use_container_width=True):
                st.session_state.mode = "upload"
                st.rerun()


# ── CHAT MODE ──────────────────────────────────────────────────────────────────
def chat_mode():
    st.markdown('<span class="mode-badge badge-chat">● Chat Mode</span>', unsafe_allow_html=True)
    st.markdown("## Ask Anything")
    st.markdown('<p style="color:#4a4a7a;font-size:13px;margin-top:-12px;">Ask questions about your audio.</p>', unsafe_allow_html=True)

    # Render chat history
    for turn in st.session_state.chat_history:
        st.markdown(f'<div class="bubble-user">🧑 {turn["user"]}</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="bubble-bot">🤖</div>', unsafe_allow_html=True)
            st.markdown(turn["AI"])

    # Input row — key increments to force widget re-creation (clears text)
    col1, col2, col3 = st.columns([5, 1, 1])
    with col1:
        query = st.text_input(
            "Question",
            value="",
            placeholder="What did the speaker say about...",
            label_visibility="collapsed",
            key=f"chat_input_{st.session_state.chat_input_key}",
        )
    with col2:
        send = st.button("Send →", use_container_width=True, type="primary")
    with col3:
        exit_btn = st.button("Exit Chat", use_container_width=True)

    if exit_btn:
        # Clear chat history on exit
        st.session_state.chat_history  = []
        st.session_state.chat_input_key += 1
        st.session_state.mode = "upload"
        st.rerun()

    if send and query.strip():
        with st.spinner("Thinking..."):
            answer = _get_answer(query.strip())
        st.session_state.chat_history.append({"user": query.strip(), "AI": answer})
        st.session_state.chat_input_key += 1   # ✅ forces input widget to re-create = clears text
        st.rerun()


def _get_answer(query: str) -> str:
    from adaptiveRagSubgraph import adaptiveRag
    from prompts import generate_query_from_context_prompt
    from llm import get_llm

    history = st.session_state.chat_history
    enriched_query = query

    if history:
        query_llm = get_llm()
        enriched_query = query_llm.invoke(
            generate_query_from_context_prompt.format(
                prev_chats=history,
                query=query
            )
        ).content

    result = adaptiveRag.invoke({
        "query": enriched_query,
        "route": "",
        "pinecone_context": [],
        "neo4j_context": [],
        "context_quality": False,
        "answer": "",
        "retry_count": 0,
        "chat_history": [],
    })
    return result["answer"]


# ── RESET MODE ─────────────────────────────────────────────────────────────────
def reset_mode():
    st.markdown('<span class="mode-badge badge-reset">◆ Reset Database</span>', unsafe_allow_html=True)
    st.markdown("## Reset Knowledge Base")
    st.markdown(
        '<p style="color:#a0a0c8;font-size:14px;">This will permanently delete all data from Pinecone and Neo4j.<br>'
        'You will need to upload audio again before chatting.</p>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Yes, delete everything", use_container_width=True, type="primary"):
            with st.spinner("Wiping databases..."):
                from reset_db import reset_database
                reset_database()
            # Reset all state — only upload mode enabled after this
            st.session_state.db_ready       = False
            st.session_state.chat_history   = []
            st.session_state.chat_input_key += 1
            st.session_state.log_lines      = []
            st.session_state.progress       = 0
            st.session_state.pipeline_done  = False
            st.session_state.pipeline_error = False
            st.session_state.audio_path     = None
            st.session_state.mode           = "upload"
            st.success("✅ Databases cleared. Upload a new audio file to get started.")
            time.sleep(1.5)
            st.rerun()
    with col2:
        if st.button("↩ Cancel", use_container_width=True):
            st.session_state.mode = "upload"
            st.rerun()


# ── Router ─────────────────────────────────────────────────────────────────────
render_sidebar()

# If pipeline is running and user somehow landed elsewhere, snap back
if st.session_state.pipeline_running and st.session_state.mode != "processing":
    st.session_state.mode = "processing"
    st.rerun()

{
    "upload":     upload_mode,
    "processing": processing_mode,
    "chat":       chat_mode,
    "reset":      reset_mode,
}[st.session_state.mode]()