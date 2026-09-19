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
import pandas as pd

# --- CONFIGURATION & DATA I/O ---
st.set_page_config(page_title="Wishlist & Budget Tracker", layout="wide", initial_sidebar_state="expanded")

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

# Initialize Session States
if 'data' not in st.session_state: st.session_state.data = load_data()
if 'view' not in st.session_state: st.session_state.view = 'home'
if 'current_cat' not in st.session_state: st.session_state.current_cat = None
if 'current_sub' not in st.session_state: st.session_state.current_sub = None
if 'current_item' not in st.session_state: st.session_state.current_item = None
if 'carousel_idx' not in st.session_state: st.session_state.carousel_idx = 0
if 'search_results' not in st.session_state: st.session_state.search_results = []

# --- UTILITY, TOTALS & SCRAPING ENGINE ---
def get_subcat_total(sub):
    return sum(item.get('price', 0.0) for item in sub.get('items', []))

def get_cat_total(cat):
    return sum(get_subcat_total(sub) for sub in cat.get('subcategories', []))

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

def search_products_online(query):
    """Searches eBay for products to avoid needing a paid API Key."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    url = f"https://www.ebay.com/sch/i.html?_nkw={query.replace(' ', '+')}"
    results = []
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.find_all('div', class_='s-item__info', limit=7)[1:] # Skip hidden meta item
        for item in items:
            title_el = item.find('div', class_='s-item__title')
            link_el = item.find('a', class_='s-item__link')
            price_el = item.find('span', class_='s-item__price')
            if title_el and link_el and price_el:
                title = title_el.text.replace("New Listing", "").strip()
                price_str = re.sub(r'[^\d.]', '', price_el.text.split(' to ')[0]) # Handle ranges
                try:
                    results.append({"title": title, "url": link_el['href'], "price": float(price_str)})
                except: continue
    except Exception as e: pass
    return results

def scrape_product(url):
    """Scrapes specific URL for detailed product info."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    data = {"title": "Unknown Product", "image_url": "", "price": 0.0, "bg_color": "#444444", "text_color": "#FFFFFF"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            og_title = soup.find('meta', property='og:title')
            data["title"] = og_title['content'] if og_title else soup.title.string if soup.title else "Scraped Product"
            og_image = soup.find('meta', property='og:image')
            if og_image:
                data["image_url"] = og_image['content']
                img_resp = requests.get(data["image_url"], headers=headers, timeout=5)
                if img_resp.status_code == 200:
                    data["bg_color"], data["text_color"] = get_dominant_color(img_resp.content)
            og_price = soup.find('meta', property='og:price:amount')
            if og_price: data["price"] = float(og_price['content'])
            else:
                price_match = re.search(r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', resp.text)
                if price_match: data["price"] = float(price_match.group(1).replace(',', ''))
    except: pass
    return data

# --- BUDGET ENGINE & CHARTS ---
def render_budget_widget(title, total_cost):
    st.divider()
    st.subheader(f"📊 Budget Forecast: {title}")
    
    deposit = st.session_state.deposit_amt
    freq = st.session_state.deposit_freq
    saved = st.session_state.current_savings
    remaining = max(0, total_cost - saved)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Cost", f"${total_cost:,.2f}")
    col2.metric("Currently Saved", f"${saved:,.2f}")
    col3.metric("Remaining Gap", f"${remaining:,.2f}")
    
    if remaining == 0 and total_cost > 0:
        st.success("🎉 Fully Funded! You have saved enough to purchase this.")
        col4.metric("Target Date", "Today")
    elif total_cost == 0:
        st.info("Add items with a price to see your budget forecast.")
    elif deposit <= 0:
        st.warning("Please set a Savings Deposit amount in the sidebar greater than $0.")
    else:
        cycles_needed = math.ceil(remaining / deposit)
        days_mult = {"Weekly": 7, "Bi-Weekly": 14, "Monthly": 30}.get(freq, 7)
        target_date = datetime.now() + timedelta(days=cycles_needed * days_mult)
        
        col4.metric("Target Date", target_date.strftime("%B %d, %Y"))
        st.caption(f"Requires {cycles_needed} more deposits of ${deposit:.2f} ({freq})")
        
        # Generate Data for the Chart
        dates = [datetime.now() + timedelta(days=i*days_mult) for i in range(cycles_needed + 1)]
        savings_progression = [min(total_cost, saved + (i * deposit)) for i in range(cycles_needed + 1)]
        
        df = pd.DataFrame({"Date": dates, "Savings Accumulation ($)": savings_progression})
        df.set_index("Date", inplace=True)
        st.area_chart(df, color="#2ecc71")

# --- UI STYLING ---
def inject_css():
    theme = st.session_state.data.get('theme', 'dark')
    app_bg = st.session_state.data.get('bg_color', '#1e1e1e')
    txt_color = "#ffffff" if theme == 'dark' else "#000000"
    st.markdown(f"""
    <style>
    .stApp {{ background-color: {app_bg} !important; color: {txt_color}; }}
    div[data-testid="stButton"] button, div[data-testid="stExpander"], .rounded-card {{ border-radius: 16px !important; }}
    .rounded-card {{ padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
    h1, h2, h3, h4, h5, h6, p, span {{ color: {txt_color}; }}
    </style>
    """, unsafe_allow_html=True)

# --- NAVIGATION ---
def nav_back(level):
    st.session_state.search_results = [] # Clear search on navigate
    if level == 'home':
        st.session_state.view = 'home'
        st.session_state.current_cat = None
    elif level == 'category':
        st.session_state.view = 'category'
        st.session_state.current_sub = None
    elif level == 'subcategory':
        st.session_state.view = 'subcategory'
        st.session_state.current_item = None
    st.session_state.carousel_idx = 0

def move_item(lst, idx, direction):
    if direction == 'up' and idx > 0: lst[idx], lst[idx-1] = lst[idx-1], lst[idx]
    elif direction == 'down' and idx < len(lst)-1: lst[idx], lst[idx+1] = lst[idx+1], lst[idx]
    save_data(st.session_state.data)

# --- VIEWS ---
def render_sidebar():
    with st.sidebar:
        st.header("⚙️ Budget Engine")
        st.session_state.deposit_amt = st.number_input("Savings Deposit ($)", min_value=0.0, value=50.0, step=10.0)
        st.session_state.deposit_freq = st.selectbox("Deposit Schedule", ["Weekly", "Bi-Weekly", "Monthly"])
        st.session_state.current_savings = st.number_input("Currently Saved Overall ($)", min_value=0.0, value=0.0, step=10.0)
        
        st.divider()
        st.header("🎨 App Theme")
        is_dark = st.toggle("Dark Mode", value=(st.session_state.data.get('theme') == 'dark'))
        st.session_state.data['theme'] = 'dark' if is_dark else 'light'
        st.session_state.data['bg_color'] = st.color_picker("Background Color", st.session_state.data.get('bg_color', '#1e1e1e'))
        save_data(st.session_state.data)

def render_home():
    st.title("🛍️ Wishlist & Budget Tracker")
    cats = st.session_state.data['categories']
    
    with st.form("add_cat"):
        col1, col2, col3 = st.columns([3, 1, 1])
        new_name = col1.text_input("New Broad Category")
        new_color = col2.color_picker("Color", "#3498db")
        if col3.form_submit_button("Add") and new_name:
            cats.append({"id": str(uuid.uuid4()), "name": new_name, "color": new_color, "subcategories": []})
            save_data(st.session_state.data)
            st.rerun()

    grand_total = sum(get_cat_total(c) for c in cats)
    
    for idx, cat in enumerate(cats):
        cat_total = get_cat_total(cat)
        with st.container():
            st.markdown(f"""
            <div style="background-color: {cat['color']}20; border-left: 5px solid {cat['color']}; padding: 1rem; border-radius: 16px; margin-bottom: 0.5rem;">
                <h3 style="margin:0;">{cat['name']}</h3>
                <span style="opacity: 0.7; font-weight: bold;">Total: ${cat_total:,.2f}</span>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, c4 = st.columns([1, 1, 1, 6])
            if c1.button("Open", key=f"view_{cat['id']}"):
                st.session_state.current_cat = cat
                st.session_state.view = 'category'
                st.rerun()
            if c2.button("▲", key=f"up_{cat['id']}"): move_item(cats, idx, 'up'); st.rerun()
            if c3.button("▼", key=f"down_{cat['id']}"): move_item(cats, idx, 'down'); st.rerun()
            if c4.button("Delete", key=f"del_{cat['id']}"): cats.pop(idx); save_data(st.session_state.data); st.rerun()
            
    render_budget_widget("All Categories Grand Total", grand_total)

def render_category():
    cat = st.session_state.current_cat
    st.button("← Back to Categories", on_click=nav_back, args=('home',))
    st.title(f"📁 {cat['name']}")
    
    subs = cat['subcategories']
    with st.form("add_sub"):
        col1, col2 = st.columns([4, 1])
        new_sub = col1.text_input("New Sub-Category")
        if col2.form_submit_button("Add") and new_sub:
            subs.append({"id": str(uuid.uuid4()), "name": new_sub, "items": []})
            save_data(st.session_state.data)
            st.rerun()
            
    for sub in subs:
        sub_total = get_subcat_total(sub)
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"### {sub['name']}<br><span style='font-size:0.9em; opacity:0.7;'>Total: ${sub_total:,.2f}</span>", unsafe_allow_html=True)
        if c2.button("Open Sub-Category", key=f"open_{sub['id']}"):
            st.session_state.current_sub = sub
            st.session_state.view = 'subcategory'
            st.rerun()
            
    render_budget_widget(f"{cat['name']} (Entire Category)", get_cat_total(cat))

def render_subcategory():
    sub = st.session_state.current_sub
    st.button("← Back to Sub-Categories", on_click=nav_back, args=('category',))
    
    c1, c2 = st.columns([3, 1])
    c1.title(f"📂 {sub['name']}")
    view_mode = c2.selectbox("Display Mode", ["Hybrid View", "Visual View", "Informational View"])
    
    with st.expander("➕ Add New Item (Search or Paste Link)"):
        tab1, tab2 = st.tabs(["🔍 Search App", "🔗 Paste Link"])
        
        with tab1:
            query = st.text_input("Search for a product (Powered by eBay)")
            if st.button("Search Web"):
                with st.spinner("Searching..."):
                    st.session_state.search_results = search_products_online(query)
            
            for res in st.session_state.search_results:
                r1, r2 = st.columns([4, 1])
                r1.write(f"**{res['title']}** - ${res['price']}")
                if r2.button("Add Item", key=res['url']):
                    with st.spinner("Importing..."):
                        scraped = scrape_product(res['url'])
                        scraped.update({"id": str(uuid.uuid4()), "url": res['url'], "title": res['title'], "price": res['price'], "specs": "", "description": "Added via in-app search."})
                        sub['items'].append(scraped)
                        save_data(st.session_state.data)
                        st.session_state.search_results = [] # Clear search after add
                        st.rerun()
                        
        with tab2:
            with st.form("add_item_link"):
                url = st.text_input("Product URL")
                specs = st.text_area("Specs (Optional)")
                if st.form_submit_button("Scrape & Add"):
                    with st.spinner("Scraping..."):
                        scraped = scrape_product(url)
                        scraped.update({"id": str(uuid.uuid4()), "url": url, "specs": specs, "description": ""})
                        sub['items'].append(scraped)
                        save_data(st.session_state.data)
                        st.rerun()

    items = sub['items']
    if not items: st.info("No items in this sub-category yet.")
    
    if view_mode == "Visual View" and items:
        idx = st.session_state.carousel_idx
        item = items[idx]
        if item.get('image_url'): st.image(item['image_url'], width=300)
        st.subheader(item['title'])
        c_prev, c_next, c_view = st.columns(3)
        if c_prev.button("◀ Prev"): st.session_state.carousel_idx = (idx - 1) % len(items); st.rerun()
        if c_next.button("Next ▶"): st.session_state.carousel_idx = (idx + 1) % len(items); st.rerun()
        if c_view.button("Open Detail"):
            st.session_state.current_item = item
            st.session_state.view = 'item'
            st.rerun()

    elif view_mode == "Informational View" and items:
        for item in items:
            with st.expander(f"**{item['title']}** - ${item['price']:.2f}"):
                st.write(item.get('specs', 'N/A'))
                if st.button("View Detail", key=f"det_{item['id']}"):
                    st.session_state.current_item = item
                    st.session_state.view = 'item'
                    st.rerun()

    elif view_mode == "Hybrid View" and items:
        for item in items:
            c_img, c_info, c_act = st.columns([1, 3, 1])
            if item.get('image_url'): c_img.image(item['image_url'], use_container_width=True)
            c_info.markdown(f"**{item['title']}**<br>${item.get('price',0):.2f}", unsafe_allow_html=True)
            if c_act.button("Open", key=f"hyb_{item['id']}"):
                st.session_state.current_item = item
                st.session_state.view = 'item'
                st.rerun()

    render_budget_widget(f"{sub['name']} (Sub-Category Total)", get_subcat_total(sub))

def render_item():
    item = st.session_state.current_item
    bg = item.get('bg_color', '#333333')
    txt = item.get('text_color', '#FFFFFF')
    
    st.button("← Back to List", on_click=nav_back, args=('subcategory',))
    
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
            if st.button("🗑️ Delete Item"):
                st.session_state.current_sub['items'] = [i for i in st.session_state.current_sub['items'] if i['id'] != item['id']]
                save_data(st.session_state.data)
                nav_back('subcategory')
                st.rerun()
    with col2:
        st.subheader("Details")
        st.write(f"**Specs:** {item.get('specs', 'None')}")
        st.link_button("View Original Product Link", item['url'])
        
    render_budget_widget(item['title'], item.get('price', 0))

# --- MAIN EXECUTION ---
inject_css()
render_sidebar()

if st.session_state.view == 'home': render_home()
elif st.session_state.view == 'category': render_category()
elif st.session_state.view == 'subcategory': render_subcategory()
elif st.session_state.view == 'item': render_item()
