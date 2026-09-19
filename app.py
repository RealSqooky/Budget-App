import streamlit as st
import json
import os
import requests
from bs4 import BeautifulSoup
from PIL import Image
import io
import re
import math
from datetime import datetime, timedelta
import uuid

# --- CONFIGURATION & DATA I/O ---
st.set_page_config(page_title="Wishlist Tracker", layout="wide", initial_sidebar_state="expanded")

DATA_FILE = "wishlist_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"categories": [], "theme": "dark", "bg_color": "#1e1e1e"}
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {"categories": [], "theme": "dark", "bg_color": "#1e1e1e"}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

if 'data' not in st.session_state:
    st.session_state.data = load_data()
if 'view' not in st.session_state:
    st.session_state.view = 'home' # home, category, subcategory, item
if 'current_cat' not in st.session_state:
    st.session_state.current_cat = None
if 'current_sub' not in st.session_state:
    st.session_state.current_sub = None
if 'current_item' not in st.session_state:
    st.session_state.current_item = None
if 'carousel_idx' not in st.session_state:
    st.session_state.carousel_idx = 0

# --- UTILITY & SCRAPING ENGINE ---
def calculate_luminance(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def get_dominant_color(img_bytes):
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((50, 50))
        colors = img.getcolors(2500)
        dominant = max(colors, key=lambda item: item[0])[1]
        r, g, b = dominant
        luminance = calculate_luminance(r, g, b)
        text_color = "#000000" if luminance > 128 else "#FFFFFF"
        return f"#{r:02x}{g:02x}{b:02x}", text_color
    except:
        return "#444444", "#FFFFFF"

def scrape_product(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
    data = {"title": "Unknown Product", "image_url": "", "price": 0.0, "bg_color": "#444444", "text_color": "#FFFFFF"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Title
            og_title = soup.find('meta', property='og:title')
            data["title"] = og_title['content'] if og_title else soup.title.string if soup.title else "Scraped Product"
            
            # Image
            og_image = soup.find('meta', property='og:image')
            if og_image:
                data["image_url"] = og_image['content']
                img_resp = requests.get(data["image_url"], headers=headers, timeout=5)
                if img_resp.status_code == 200:
                    data["bg_color"], data["text_color"] = get_dominant_color(img_resp.content)
            
            # Price
            og_price = soup.find('meta', property='og:price:amount')
            if og_price:
                data["price"] = float(og_price['content'])
            else:
                price_match = re.search(r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', resp.text)
                if price_match:
                    data["price"] = float(price_match.group(1).replace(',', ''))
    except Exception as e:
        pass # Silently fail and use defaults. E-commerce sites frequently block basic scraping.
    return data

# --- BUDGET ENGINE ---
def calculate_budget(total_cost, deposit, freq):
    if deposit <= 0: return float('inf'), "Never"
    cycles_needed = math.ceil(total_cost / deposit)
    days_multiplier = {"Weekly": 7, "Bi-Weekly": 14, "Monthly": 30}.get(freq, 7)
    target_date = datetime.now() + timedelta(days=cycles_needed * days_multiplier)
    return cycles_needed, target_date.strftime("%B %d, %Y")

# --- UI STYLING & CSS INJECTION ---
def inject_css():
    theme = st.session_state.data.get('theme', 'dark')
    app_bg = st.session_state.data.get('bg_color', '#1e1e1e')
    txt_color = "#ffffff" if theme == 'dark' else "#000000"
    
    css = f"""
    <style>
    .stApp {{ background-color: {app_bg} !important; color: {txt_color}; }}
    
    /* Squircle Borders */
    div[data-testid="stButton"] button, 
    div[data-testid="stExpander"], 
    .rounded-card {{
        border-radius: 16px !important;
    }}
    
    .rounded-card {{
        padding: 1.5rem; margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    
    /* Typography adjustments */
    h1, h2, h3, h4, h5, h6, p, span {{ color: {txt_color}; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# --- NAVIGATION CONTROLS ---
def nav_back(level):
    if level == 'home':
        st.session_state.view = 'home'
        st.session_state.current_cat = None
    elif level == 'category':
        st.session_state.view = 'category'
        st.session_state.current_sub = None
    st.session_state.carousel_idx = 0

def move_item(lst, idx, direction):
    if direction == 'up' and idx > 0:
        lst[idx], lst[idx-1] = lst[idx-1], lst[idx]
    elif direction == 'down' and idx < len(lst)-1:
        lst[idx], lst[idx+1] = lst[idx+1], lst[idx]
    save_data(st.session_state.data)

# --- RENDER VIEWS ---
def render_sidebar():
    with st.sidebar:
        st.header("Budget Engine")
        st.session_state.deposit_amt = st.number_input("Savings Deposit ($)", min_value=0.0, value=50.0, step=10.0)
        st.session_state.deposit_freq = st.selectbox("Schedule", ["Weekly", "Bi-Weekly", "Monthly"])
        
        st.divider()
        st.header("App Theme")
        is_dark = st.toggle("Dark Mode", value=(st.session_state.data.get('theme') == 'dark'))
        st.session_state.data['theme'] = 'dark' if is_dark else 'light'
        st.session_state.data['bg_color'] = st.color_picker("Global Background Color", st.session_state.data.get('bg_color', '#1e1e1e'))
        save_data(st.session_state.data)

def render_home():
    st.title("Wishlist Tracker")
    cats = st.session_state.data['categories']
    
    with st.form("add_cat"):
        col1, col2, col3 = st.columns([3, 1, 1])
        new_name = col1.text_input("New Broad Category")
        new_color = col2.color_picker("Color", "#3498db")
        submitted = col3.form_submit_button("Add")
        if submitted and new_name:
            cats.append({"id": str(uuid.uuid4()), "name": new_name, "color": new_color, "subcategories": []})
            save_data(st.session_state.data)
            st.rerun()

    for idx, cat in enumerate(cats):
        with st.container():
            st.markdown(f"""
            <div style="background-color: {cat['color']}20; border-left: 5px solid {cat['color']}; padding: 1rem; border-radius: 16px; margin-bottom: 0.5rem;">
                <h3 style="margin:0;">{cat['name']}</h3>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns([1, 1, 1, 6])
            if c1.button("View", key=f"view_{cat['id']}"):
                st.session_state.current_cat = cat
                st.session_state.view = 'category'
                st.rerun()
            if c2.button("▲ Up", key=f"up_{cat['id']}"):
                move_item(cats, idx, 'up')
                st.rerun()
            if c3.button("▼ Down", key=f"down_{cat['id']}"):
                move_item(cats, idx, 'down')
                st.rerun()
            if c4.button("Delete", key=f"del_{cat['id']}"):
                cats.pop(idx)
                save_data(st.session_state.data)
                st.rerun()

def render_category():
    cat = st.session_state.current_cat
    st.button("← Back to Categories", on_click=nav_back, args=('home',))
    st.title(f"Category: {cat['name']}")
    
    subs = cat['subcategories']
    with st.form("add_sub"):
        col1, col2 = st.columns([4, 1])
        new_sub = col1.text_input("New Sub-Category")
        submitted = col2.form_submit_button("Add")
        if submitted and new_sub:
            subs.append({"id": str(uuid.uuid4()), "name": new_sub, "items": []})
            save_data(st.session_state.data)
            st.rerun()
            
    for sub in subs:
        c1, c2 = st.columns([4, 1])
        c1.subheader(sub['name'])
        if c2.button("Open", key=f"open_{sub['id']}"):
            st.session_state.current_sub = sub
            st.session_state.view = 'subcategory'
            st.rerun()

def render_subcategory():
    sub = st.session_state.current_sub
    st.button("← Back to Sub-Categories", on_click=nav_back, args=('category',))
    
    c1, c2 = st.columns([3, 1])
    c1.title(f"Sub-Category: {sub['name']}")
    view_mode = c2.selectbox("Display Mode", ["Hybrid View", "Visual View", "Informational View"])
    
    with st.expander("Add New Item via Link"):
        with st.form("add_item"):
            url = st.text_input("Product URL")
            specs = st.text_area("Specs (Optional)")
            desc = st.text_area("Description (Optional)")
            if st.form_submit_button("Scrape & Add"):
                with st.spinner("Scraping..."):
                    scraped = scrape_product(url)
                    scraped.update({
                        "id": str(uuid.uuid4()),
                        "url": url,
                        "specs": specs,
                        "description": desc
                    })
                    sub['items'].append(scraped)
                    save_data(st.session_state.data)
                    st.rerun()

    items = sub['items']
    if not items:
        st.write("No items yet.")
        return

    if view_mode == "Visual View":
        idx = st.session_state.carousel_idx
        item = items[idx]
        st.image(item['image_url'], width=300)
        st.subheader(item['title'])
        c_prev, c_next, c_view = st.columns(3)
        if c_prev.button("◀ Prev"):
            st.session_state.carousel_idx = (idx - 1) % len(items)
            st.rerun()
        if c_next.button("Next ▶"):
            st.session_state.carousel_idx = (idx + 1) % len(items)
            st.rerun()
        if c_view.button("Open Detail"):
            st.session_state.current_item = item
            st.session_state.view = 'item'
            st.rerun()

    elif view_mode == "Informational View":
        for item in items:
            with st.expander(f"**{item['title']}** - ${item['price']:.2f}"):
                t1, t2 = st.tabs(["Specs", "Description"])
                t1.write(item['specs'] or "N/A")
                t2.write(item['description'] or "N/A")
                if st.button("View Detail", key=f"det_{item['id']}"):
                    st.session_state.current_item = item
                    st.session_state.view = 'item'
                    st.rerun()

    elif view_mode == "Hybrid View":
        for item in items:
            c_img, c_info, c_act = st.columns([1, 3, 1])
            if item['image_url']: c_img.image(item['image_url'], use_container_width=True)
            c_info.markdown(f"**{item['title']}**<br>${item['price']:.2f}", unsafe_allow_html=True)
            with c_info.expander("Details"):
                st.write(f"**Specs:** {item['specs']}")
                st.write(f"**Desc:** {item['description']}")
            if c_act.button("Open", key=f"hyb_{item['id']}"):
                st.session_state.current_item = item
                st.session_state.view = 'item'
                st.rerun()

def render_item():
    item = st.session_state.current_item
    bg = item.get('bg_color', '#333333')
    txt = item.get('text_color', '#FFFFFF')
    
    st.button("← Back to List", on_click=lambda: setattr(st.session_state, 'view', 'subcategory'))
    
    # Render customized tinted background wrapper
    st.markdown(f"""
    <div class="rounded-card" style="background-color: {bg}; color: {txt};">
        <h2 style="color: {txt};">{item['title']}</h2>
        <p style="font-size: 1.5rem; font-weight: bold;">${item.get('price', 0):.2f}</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if item.get('image_url'):
            st.image(item['image_url'], use_container_width=True)
            if st.button("🔍 Expand Image"):
                # Basic fullscreen implementation via dialog overlay
                @st.dialog("Expanded View", width="large")
                def show_large(): st.image(item['image_url'], use_container_width=True)
                show_large()
    
    with col2:
        st.subheader("Details")
        st.write(f"**Specs:** {item.get('specs', 'None')}")
        st.write(f"**Description:** {item.get('description', 'None')}")
        st.link_button("View Original Product", item['url'])
        
        st.divider()
        st.subheader("Budgeting Breakdown")
        cycles, target = calculate_budget(item.get('price', 0), st.session_state.deposit_amt, st.session_state.deposit_freq)
        st.write(f"**Deposit Schedule:** ${st.session_state.deposit_amt:.2f} {st.session_state.deposit_freq}")
        st.write(f"**Cycles Needed:** {cycles}")
        st.write(f"**Target Purchase Date:** {target}")

# --- MAIN EXECUTION ---
inject_css()
render_sidebar()

if st.session_state.view == 'home': render_home()
elif st.session_state.view == 'category': render_category()
elif st.session_state.view == 'subcategory': render_subcategory()
elif st.session_state.view == 'item': render_item()
