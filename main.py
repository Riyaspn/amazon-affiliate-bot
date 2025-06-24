import asyncio
import os
from playwright.async_api import async_playwright
from telegram import Bot
from dotenv import load_dotenv

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
    "Home & Kitchen": "📢 HOME_KITCHEN DEALS",
    "Kitchen & Dining": "🍳 KITCHEN & DINING DEALS"
}

AFFILIATE_TAG = "storesofriyas-21"

HIGH_COMM_KEYWORDS = ["cookware", "kitchen", "grinder", "fryer", "pressure cooker", "induction", "blender", "utensil"]


def get_affiliate_link(url: str) -> str:
    return url.split("/ref=")[0] + f"?tag={AFFILIATE_TAG}"


def format_product(product, index):
    label = "🔥 Hot Deal" if index == 0 else "⭐ Top Rated"
    return f"""{label}
🛒 *{product['title']}*
💰 ₹{product['price']:,}
⭐ {product['rating']}
🔗 [View on Amazon]({product['link']})"""


async def send_telegram_message(bot: Bot, text: str):
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown", disable_web_page_preview=True)


async def scrape_category(page, category: str, url: str):
    await page.goto(url)

    content = await page.content()
    if "no bestsellers available" in content.lower():
        print(f"[ℹ️ Skipped] No bestsellers listed for {category}.")
        return []

    try:
        await page.wait_for_selector("span[class*='price'], span.a-price-whole", timeout=15000)
    except:
        print(f"[⚠️ Timeout] Could not find prices for {category}")
        return []

    titles = await page.locator("._cDEzb_p13n-sc-css-line-clamp-3_g3dy1, .p13n-sc-truncated").all_inner_texts()
    prices = await page.locator("span[class*='price'], span.a-price-whole").all_inner_texts()
    ratings = await page.locator("span.a-icon-alt").all_inner_texts()
    links = await page.locator("a.a-link-normal").evaluate_all(
        "(elements) => elements.map(el => el.href)"
    )

    unique = {}
    for title, price, rating, link in zip(titles, prices, ratings, links):
        if not title or not price or not rating or not link:
            continue
        try:
            clean_price = float(price.replace("₹", "").replace(",", "").strip())
        except:
            continue

        # Filter high-commission keywords
        if category == "Kitchen & Dining":
            if not any(keyword in title.lower() for keyword in HIGH_COMM_KEYWORDS):
                continue

        base_link = get_affiliate_link(link)
        if title not in unique:
            unique[title] = {
                "title": title.strip(),
                "price": clean_price,
                "rating": rating,
                "link": base_link,
            }

    sorted_data = sorted(unique.values(), key=lambda x: x["price"], reverse=True)
    return sorted_data[:5]


async def main():
    print("🔍 Starting Amazon Affiliate Bot...")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

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
