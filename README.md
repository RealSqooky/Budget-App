# Budget-App
Budget App based off a couple inputs and python code from gemini.
# Wishlist & Budget Savings Tracker 🛍️💸

A dynamic, single-page web application built with Python and Streamlit. This app acts as a visual wishlist organizer and a smart budgeting engine, helping users track items they want to buy and calculating exactly how long it will take to save for them.

## Core Features
* **Web Scraping:** Paste a product link, and the app automatically fetches the title, price, and product image.
* **Smart Visual Theming:** Uses Python's Pillow (PIL) library to extract the dominant color from a product's image, automatically tinting the item's background card to match.
* **Budget Engine:** Enter your recurring savings deposit (e.g., $50 Weekly) in the sidebar. The app automatically calculates how many deposit cycles are needed and provides an exact target date for when you can afford each item.
* **Organization:** Build a custom hierarchy (Broad Categories -> Sub-Categories -> Items). Includes up/down reordering and custom category color pickers.
* **Multiple Display Modes:** Toggle between Visual Image Carousels, Compact Informational views, or Hybrid lists to browse your items.

## How to Use the App
1. **Set Your Budget:** Open the sidebar menu and set your standard savings deposit amount and schedule (Weekly, Bi-Weekly, Monthly).
2. **Create Categories:** Add a broad category (like "Tech" or "Furniture") and pick a theme color for it. 
3. **Add Sub-Categories:** Inside your broad category, create specific sub-lists (like "Computer Parts" or "Living Room").
4. **Add Items:** Open a sub-category and expand the "Add New Item via Link" menu. Paste a product URL and click Scrape. The app will pull the data and calculate your saving timeline!

## Tech Stack
* **Frontend/Backend:** [Streamlit](https://streamlit.io/)
* **Scraping:** BeautifulSoup4 & Requests
* **Image Processing:** Pillow (PIL)
