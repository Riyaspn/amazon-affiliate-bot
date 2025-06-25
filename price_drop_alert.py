import asyncio
import csv
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from telegram import Bot

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
AFFILIATE_TAG = "storesofriyas-21"
PRODUCTS = [
    "B0DGHYDZR9", "B0DGJ8SYS6", "B0DGJ1BY5T", "B0DGJBN8TV", "B0DGHTBK1Q",
    "B0DGHQ717F", "B0DGJ8JQZD", "B0DGJGRDDS", "B0DGJHBX5Y", "B0DGJ58SMG",
    "B0DGJ54GQW", "B0DGJ63CXK"
]
DATA_FILE = "product_prices.csv"

async def fetch_product_data(page, asin):
    url = f"https://www.amazon.in/dp/{asin}?tag={AFFILIATE_TAG}"
    print(f"🔍 Visiting: {url}")
    try:
        await page.goto(url, timeout=30000)
        await page.wait_for_selector("#corePriceDisplay_desktop_feature_div", timeout=20000)

        # Title
        title = await page.locator("#productTitle").text_content()
        title = title.strip() if title else "Unknown Product"

        # Image
        image = await page.locator("#landingImage").get_attribute("src")

        # Price
        price_text = await page.locator("span.a-price-whole").first.text_content()
        price_text = price_text.replace(",", "").replace("₹", "").strip()
        if price_text.endswith("."):
            price_text = price_text[:-1]
        price = float(price_text)

        return {
            "asin": asin,
            "title": title,
            "price": price,
            "image": image,
            "affiliate_link": f"https://www.amazon.in/dp/{asin}?tag={AFFILIATE_TAG}"
        }

    except PlaywrightTimeout as e:
        print(f"Error extracting price/image: {e}")
    except Exception as e:
        print(f"Error extracting price/image: {e}")
    return None

def load_previous_prices():
    prices = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", newline='', encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader, None)  # Skip header
            for row in reader:
                if len(row) >= 2:
                    try:
                        prices[row[0]] = float(row[1])
                    except ValueError:
                        continue
    return prices

def save_current_prices(price_map):
    with open(DATA_FILE, "w", newline='', encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["asin", "price"])
        for asin, price in price_map.items():
            writer.writerow([asin, price])

async def send_price_drop_alert(bot, product, old_price):
    drop = old_price - product["price"]
    percent = (drop / old_price) * 100
    message = (
        f"🔻 *Price Drop Alert!*\n\n"
        f"*{product['title']}*\n"
        f"💰 *Old Price:* ₹{int(old_price)}\n"
        f"✅ *New Price:* ₹{int(product['price'])}\n"
        f"📉 *You Save:* ₹{int(drop)} ({percent:.0f}% OFF)\n\n"
        f"🔗 [View on Amazon]({product['affiliate_link']})"
    )
    try:
        await bot.send_photo(
            chat_id=TELEGRAM_CHAT_ID,
            photo=product["image"],
            caption=message,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Failed to send Telegram alert for {product['asin']}: {e}")

async def check_price_drops():
    print("📉 Starting Price Drop Alert...")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    previous_prices = load_previous_prices()
    current_prices = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        for asin in PRODUCTS:
            product = await fetch_product_data(page, asin)
            if not product:
                print(f"[⚠️ Skipped] Could not extract data from: https://www.amazon.in/dp/{asin}?tag={AFFILIATE_TAG}")
                continue

            current_prices[asin] = product["price"]

            if asin in previous_prices:
                old_price = previous_prices[asin]
                if product["price"] < old_price:
                    await send_price_drop_alert(bot, product, old_price)
                else:
                    print(f"ℹ️ No drop for {asin}. Current: ₹{product['price']} | Old: ₹{old_price}")
            else:
                print(f"ℹ️ No previous price found for {asin}, saving now.")

        await browser.close()

    save_current_prices(current_prices)
    print("✅ Done.")

if __name__ == "__main__":
    asyncio.run(check_price_drops())
