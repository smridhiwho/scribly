import streamlit as st
import requests
from datetime import datetime

API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="scribly.",
    page_icon="📝",
    layout="wide"
)

st.markdown("""
    <style>
    .stTextArea textarea {
        background-color: #F5E6B3;
        border: none;
        border-radius: 15px;
        font-size: 18px;
        padding: 20px;
        font-family: 'Courier New', monospace;
    }
    h1 {
        font-size: 4em;
        font-weight: 900;
    }
    </style>
""", unsafe_allow_html=True)

def create_scribble(content, tags, is_confidential):
    try:
        response = requests.post(
            f"{API_URL}/scribbles",
            json={"content": content, "tags": tags, "is_confidential": is_confidential}
        )
        return response.json()
    except Exception as e:
        st.error(f"Error: {e}")
        return None

def get_categories():
    try:
        response = requests.get(f"{API_URL}/categories")
        return response.json()
    except:
        return {}

def get_scribbles_by_category(category):
    try:
        response = requests.get(f"{API_URL}/categories/{category}")
        return response.json()
    except:
        return []

def delete_scribble(scribble_id):
    try:
        requests.delete(f"{API_URL}/scribbles/{scribble_id}")
        return True
    except:
        return False

if 'selected_tags' not in st.session_state:
    st.session_state.selected_tags = []
if 'is_confidential' not in st.session_state:
    st.session_state.is_confidential = False

page = st.sidebar.radio("Nav", ["✍️ Scribble", "📁 My Feed"], label_visibility="hidden")

if page == "✍️ Scribble":
    st.markdown("<h1>scribly.</h1>", unsafe_allow_html=True)
    st.markdown("**Scribble your thoughts - we'll organise them for you**")
    
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔔 RemindMe", key="btn_remindme"):
            if "/remindme" not in st.session_state.selected_tags:
                st.session_state.selected_tags.append("/remindme")
    with col2:
        if st.button("📰 Newsletter", key="btn_newsletter"):
            if "/newsletter" not in st.session_state.selected_tags:
                st.session_state.selected_tags.append("/newsletter")
    with col3:
        if st.button("🔒 Confidential", key="btn_confidential"):
            st.session_state.is_confidential = True
    with col4:
        if st.button("💭 Quote", key="btn_quote"):
            if "/quote" not in st.session_state.selected_tags:
                st.session_state.selected_tags.append("/quote")
    
    if st.session_state.selected_tags or st.session_state.is_confidential:
        tags_text = ", ".join(st.session_state.selected_tags)
        if st.session_state.is_confidential:
            tags_text += " [CONFIDENTIAL]"
        st.info(f"Tags: {tags_text}")
    
    scribble_content = st.text_area(
        "Your scribble",
        height=300,
        placeholder="Just scribble anything...",
        label_visibility="hidden",
        key="scribble_input"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 Save Scribble", type="primary", use_container_width=True, key="btn_save"):
            if scribble_content.strip():
                result = create_scribble(
                    scribble_content,
                    st.session_state.selected_tags,
                    st.session_state.is_confidential
                )
                if result:
                    st.success(f"✅ Saved to: {result['category']}")
                    st.session_state.selected_tags = []
                    st.session_state.is_confidential = False
            else:
                st.warning("Please write something first!")
                
    with col2:
        if st.button("Clear", use_container_width=True, key="btn_clear"):
            st.session_state.selected_tags = []
            st.session_state.is_confidential = False

elif page == "📁 My Feed":
    st.markdown("<h1>my feed.</h1>", unsafe_allow_html=True)
    
    categories = get_categories()
    
    icons = {
        "newsletter": "📰",
        "reminders": "🔔",
        "confidential": "🔒",
        "quotes": "💭",
        "ideas": "💡",
        "videos": "📹",
        "contacts": "👤",
        "uncategorized": "📦"
    }
    
    for category, count in categories.items():
        if count > 0:
            icon = icons.get(category, "📁")
            with st.expander(f"{icon} {category.upper()} ({count})", expanded=True):
                scribbles = get_scribbles_by_category(category)
                for scribble in scribbles:
                    col1, col2 = st.columns([9, 1])
                    with col1:
                        st.write(scribble['content'])
                        st.caption(datetime.fromisoformat(scribble['created_at']).strftime('%b %d, %Y %I:%M %p'))
                        if scribble.get('reminder_date'):
                            st.info(f"⏰ Reminder: {scribble['reminder_date']}")
                    with col2:
                        if st.button("🗑️", key=f"del_{scribble['id']}"):
                            if delete_scribble(scribble['id']):
                                st.rerun()
    
    if sum(categories.values()) == 0:
        st.info("No scribbles yet!")