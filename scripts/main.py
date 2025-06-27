import os
import sys
import json
import re
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# === CONFIG ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHAT_ID")
AFFILIATE_TAG = "storesofriyas-21"
SCRIPT_DIR = os.path.dirname(__file__)
DAILY_FILE = os.path.join(SCRIPT_DIR, "daily_products.json")

CATEGORY_URLS = {
    "Electronics": "https://www.amazon.in/gp/bestsellers/electronics/",
    "Beauty": "https://www.amazon.in/gp/bestsellers/beauty/",
    "Home_Kitchen": "https://www.amazon.in/gp/bestsellers/kitchen/"
}

# === UTILS ===

def simplify_title(title):
    title = re.sub(r"\(.*?\)", "", title)
    title = re.sub(r"[^a-zA-Z0-9 ]", "", title)
    return title.lower().strip()

def add_label(product):
    labels = []
    price_text = product['price'].replace("₹", "").replace(",", "").strip()
    try:
        price = float(price_text)
        if price > 10000:
            labels.append("💸 Premium Pick")
    except:
        pass

    if product['rating'] != "N/A":
        try:
            rating = float(product['rating'].split()[0])
            if rating >= 4.5:
                labels.append("🌟 Top Rated")
        except:
            pass

    if "off" in product['price'].lower():
        labels.append("🎯 Best Value")

    return labels[0] if labels else "⭐ Top Rated"

def format_telegram_message(category, products, header_label):
    message = f"{header_label}\n📢 *{category.replace('_', ' ').upper()} DEALS*\n\n"
    for i, product in enumerate(products):
        label = add_label(product) if i > 0 else "🔥 Hot Deal"
        message += f"""{label}
🛒 *{product['title']}*
💰 {product['price']}
⭐ {product['rating']}
🔗 [View on Amazon]({product['link']})

"""
    return message.strip()

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    res = requests.post(url, data=payload)
    if res.ok:
        print("✅ Telegram message sent.")
    else:
        print("❌ Telegram Error:", res.text)

def deduplicate_variants(products):
    seen = set()
    deduped = []
    for product in products:
        key = simplify_title(product['title'])[:50]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(product)
    return deduped

# === SCRAPER ===

def scrape_top_30(category_name, url):
    print(f"🔍 Scraping: {category_name}")
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=60000)
        page.wait_for_selector("div.p13n-sc-uncoverable-faceout")

        cards = page.query_selector_all("div.p13n-sc-uncoverable-faceout")
        products = []
        seen_asins = set()

        for card in cards:
            try:
                title_elem = card.query_selector("._cDEzb_p13n-sc-css-line-clamp-4_2q2cc") or \
                             card.query_selector("._cDEzb_p13n-sc-css-line-clamp-3_g3dy1")
                if not title_elem:
                    continue

                title = title_elem.inner_text().strip()

                link_elem = card.query_selector("a")
                link = link_elem.get_attribute("href")
                asin_match = re.search(r"/dp/([A-Z0-9]{10})", link)
                if not asin_match:
                    continue
                asin = asin_match.group(1)
                if asin in seen_asins:
                    continue
                seen_asins.add(asin)

                full_link = f"https://www.amazon.in/dp/{asin}?tag={AFFILIATE_TAG}&th=1"

                price_elem = card.query_selector("._cDEzb_p13n-sc-price_3mJ9Z")
                price = price_elem.inner_text().strip() if price_elem else "N/A"

                rating_elem = card.query_selector("span.a-icon-alt")
                rating = rating_elem.inner_text().strip() if rating_elem else "N/A"

                products.append({
                    "title": title,
                    "link": full_link,
                    "price": price,
                    "rating": rating
                })

                if len(products) >= 40:
                    break

            except Exception as e:
                print(f"⚠️ Product parse error: {e}")
                continue

        browser.close()
        return products

# === RUN MODES ===

def morning_run():
    all_data = {}
    header_label = choose_message_header("morning")
    send_to_telegram(header_label)  # Send once before categories
    for category, url in CATEGORY_URLS.items():
        raw = scrape_top_30(category, url)
        clean = deduplicate_variants(raw)
        all_data[category] = clean[:10]
        top_5 = clean[:5]
        msg = format_telegram_message(category, top_5, "")
        send_to_telegram(msg)

    with open(DAILY_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=2)
    print("🗂️ Saved daily_products.json")

def evening_run():
    if not os.path.exists(DAILY_FILE):
        print("⚠️ No morning data found.")
        return
    with open(DAILY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    header_label = choose_message_header("evening")
    send_to_telegram(header_label)  # Send once before categories

    for category, products in data.items():
        next_5 = products[5:10]
        if not next_5:
            continue
        msg = format_telegram_message(category, next_5, "")
        send_to_telegram(msg)

# === HEADER MESSAGE STYLE ===

def choose_message_header(mode):
    today = datetime.utcnow().weekday()  # Monday=0 ... Sunday=6
    if mode == "morning":
        if today in [0, 2, 4]:   # Mon, Wed, Fri
            return "✅ *Top 5 Per Category*"
        elif today == 6:        # Sunday
            return "🛍️ *Weekly Combo Picks*"
    return "🚀 *Evening Picks*"

# === ENTRY POINT ===

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❗ Usage: python main.py [morning|evening]")
        sys.exit()

    mode = sys.argv[1].lower()
    if mode == "morning":
        print("🌅 Morning session started...")
        morning_run()
    elif mode == "evening":
        print("🌇 Evening session started...")
        evening_run()
    else:
        print("❗ Invalid mode. Use 'morning' or 'evening'")
