import asyncio
from playwright.async_api import async_playwright
import csv
import os
from datetime import datetime
from telegram import Bot

# Telegram bot settings
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
AFFILIATE_TAG = "storesofriyas-21"

CATEGORIES = {
    "Electronics": "https://www.amazon.in/gp/bestsellers/electronics/",
    "Beauty": "https://www.amazon.in/gp/bestsellers/beauty/",
    "Home_Kitchen": "https://www.amazon.in/gp/bestsellers/kitchen/",
}

async def scrape_category(category_name, url, page):
    await page.goto(url, timeout=60000)
    await page.wait_for_selector("div.p13n-sc-uncoverable-faceout")

    items = await page.query_selector_all("div.p13n-sc-uncoverable-faceout")
    results = []
    seen_titles = set()

    for item in items:
        title_el = await item.query_selector("._cDEzb_p13n-sc-css-line-clamp-3_g3dy1")
        price_el = await item.query_selector("._cDEzb_p13n-sc-price_3mJ9Z")
        rating_el = await item.query_selector(".a-icon-alt")
        link_el = await item.query_selector("a.a-link-normal")

        if not title_el or not link_el:
            continue

        title = (await title_el.inner_text()).strip()
        if title in seen_titles:
            continue
        seen_titles.add(title)

        price = (await price_el.inner_text()).strip() if price_el else "N/A"
        rating = (await rating_el.inner_text()).strip() if rating_el else "N/A"
        link_suffix = await link_el.get_attribute("href")
        asin = link_suffix.split("/dp/")[1].split("/")[0] if "/dp/" in link_suffix else None
        affiliate_link = f"https://www.amazon.in/dp/{asin}/?tag={AFFILIATE_TAG}" if asin else "N/A"

        results.append({
            "title": title,
            "price": price,
            "rating": rating,
            "link": affiliate_link,
        })

        if len(results) == 5:
            break

    return sorted(results, key=lambda x: float(x["price"].replace("₹", "").replace(",", "").replace(".00", "")) if x["price"] != "N/A" else 0, reverse=True)

async def send_telegram_message(bot, text):
    await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown", disable_web_page_preview=True)

async def generate_message(category, products):
    emojis = ["🔥 Hot Deal", "✅ Amazon’s Choice", "⭐ Top Rated", "🎯 Best Value"]
    message = f"📢 *{category.upper().replace('_', ' ')} DEALS*\n\n"

    for idx, product in enumerate(products, start=1):
        label = emojis[idx % len(emojis)]
        message += (
            f"{idx}. {product['title']}\n"
            f"💰 Price: {product['price']}\n"
            f"⭐ Rating: {product['rating']}\n"
            f"🔗 [View on Amazon]({product['link']})\n"
            f"{label}\n\n"
        )

    return message

async def main():
    bot = Bot(token=TELEGRAM_TOKEN)
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        for category, url in CATEGORIES.items():
            print(f"Scraping: {url}")
            products = await scrape_category(category, url, page)
            message = await generate_message(category, products)
            await send_telegram_message(bot, message)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
