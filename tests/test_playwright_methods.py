from playwright.sync_api import sync_playwright

def test_playwright_methods():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=False)
        page=browser.new_page()
        
        page.goto("https://books.toscrape.com")
        
        next_button=page.query_selector("li.next a")
        if next_button:
            next_button.click()
            page.wait_for_load_state("networkidle")
            print(f"Clicked next! Now on: {page.url}")

        
if __name__ == "__main__":
    test_playwright_methods()