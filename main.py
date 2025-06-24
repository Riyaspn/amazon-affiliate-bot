import asyncio
import os
from datetime import datetime
from playwright.async_api import async_playwright
from telegram import Bot
from dotenv import load_dotenv
from difflib import SequenceMatcher

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CATEGORIES = {
    "Electronics": "https://www.amazon.in/gp/bestsellers/electronics/",
    "Beauty": "https://www.amazon.in/gp/bestsellers/beauty/",
    "Home & Kitchen": "https://www.amazon.in/gp/bestsellers/home/",
    "Kitchen & Dining": "https://www.amazon.in/gp/bestsellers/kitchen/"
}

HEADERS = {
    "Electronics": "📢 ELECTRONICS DEALS",
    "Beauty": "📢 BEAUTY DEALS",
    "Home & Kitchen": "📢 HOME & KITCHEN DEALS",
    "Kitchen & Dining": "🍳 KITCHEN & DINING DEALS"
}

AFFILIATE_TAG = "storesofriyas-21"
HIGH_COMM_KEYWORDS = ["cookware", "kitchen", "grinder", "fryer", "pressure cooker", "induction", "blender", "utensil"]


def get_affiliate_link(url: str) -> str:
    return url.split("/ref=")[0] + f"?tag={AFFILIATE_TAG}"


def similar_title(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > 0.8


def format_product(product, index):
    label = "🔥 Hot Deal" if index == 0 else "⭐ Top Rated"
    return f"""{label}
🛒 *{product['title']}*
💰 ₹{product['price']:,}
⭐ {product['rating']}
🔗 [View on Amazon]({product['link']})"""


def get_template_prefix():
    weekday = datetime.now().weekday()
    if weekday in [0, 2, 4]:  # Mon, Wed, Fri
        return "🗓️ *Top 5 Per Category*"
    elif weekday in [1, 3, 5]:  # Tue, Thu, Sat
        return "🚀 *Flash Deals & Top Clicked*"
    else:  # Sunday
        return "🛍️ *Weekly Top Picks & Combo Deals*"


async def send_telegram_message(bot: Bot, text: str):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown", disable_web_page_preview=True)


async def scrape_category(page, category: str, url: str):
    print(f"Scraping: {url}")
    await page.goto(url)
    await page.wait_for_timeout(2000)

    try:
        await page.wait_for_selector("div.p13n-sc-uncoverable-faceout", timeout=15000)
    except:
        print(f"[⚠️ Timeout] No product containers found for {category}")
        return []

    cards = await page.locator("div.p13n-sc-uncoverable-faceout").element_handles()
    print(f"[✓] Found {len(cards)} product containers for {category}")

    products = []
    seen_titles = []

    for card in cards:
        try:
            title_el = await card.query_selector("div[class*='line-clamp']")
            price_el = await card.query_selector("span[class*='price']")
            rating_el = await card.query_selector("span.a-icon-alt")
            link_el = await card.query_selector("a.a-link-normal")

            title = (await title_el.inner_text()).strip() if title_el else None
            price_raw = (await price_el.inner_text()).strip() if price_el else None
            rating = (await rating_el.inner_text()).strip() if rating_el else "No rating"
            href = (await link_el.get_attribute("href")).strip() if link_el else None

            if not title or not price_raw or not href:
                continue

            price = float(price_raw.replace("₹", "").replace(",", ""))
            full_link = get_affiliate_link("https://www.amazon.in" + href)

            if any(similar_title(title, t) for t in seen_titles):
                continue
            seen_titles.append(title)

            if category == "Kitchen & Dining" and not any(k in title.lower() for k in HIGH_COMM_KEYWORDS):
                continue

            products.append({
                "title": title,
                "price": price,
                "rating": rating,
                "link": full_link
            })

        except Exception as e:
            print(f"[⚠️ Skipped One] Error: {e}")

    sorted_data = sorted(products, key=lambda x: x["price"], reverse=True)
    return sorted_data[:5]


async def main():
    print("🔍 Starting Amazon Affiliate Bot...")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        intro = get_template_prefix()
        await send_telegram_message(bot, intro)

        for cat, url in CATEGORIES.items():
            print(f"Scraping: {url}")
            try:
                data = await scrape_category(page, cat, url)
            except Exception as e:
                print(f"❌ Error scraping {cat}: {e}")
                continue

            if not data:
                print(f"[ℹ️ Skipped] No data returned for {cat}")
                continue

            header = f"*{HEADERS[cat]}*"
            messages = [header] + [format_product(product, i) for i, product in enumerate(data)]
            await send_telegram_message(bot, "\n\n".join(messages))

        await browser.close()
    print("✅ Done.")


if __name__ == "__main__":
    asyncio.run(main())
