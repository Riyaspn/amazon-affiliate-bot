import asyncio
from playwright.async_api import async_playwright

URL = "https://www.amazon.in/gp/bestsellers/electronics/"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(URL)
        await page.wait_for_timeout(5000)

        containers = await page.query_selector_all("div.p13n-sc-uncoverable-faceout")
        print(f"Found {len(containers)} containers")

        if containers:
            html = await containers[0].inner_html()
            print("\n===== FIRST PRODUCT CARD HTML =====\n")
            print(html)
            print("\n====================================\n")

        await browser.close()

asyncio.run(main())
