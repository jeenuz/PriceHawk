from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="en-IN",
        timezone_id="Asia/Kolkata",
    )
    page = context.new_page()

    page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )

    page.goto(
        "https://www.flipkart.com/search?q=dishwasher",
        wait_until="domcontentloaded",
        timeout=30000
    )
    page.wait_for_timeout(4000)

    # Save full page HTML to file
    html = page.content()
    with open("data/flipkart_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved full HTML — {len(html)} chars")

    # JavaScript to find price elements
    js_find_prices = """
        () => {
            var all = document.querySelectorAll('*');
            var priceEls = [];
            for (var i = 0; i < all.length; i++) {
                var el = all[i];
                var text = el.textContent.trim();
                if (el.children.length === 0 &&
                    text.indexOf('\u20b9') !== -1 &&
                    text.length < 20) {
                    priceEls.push({
                        tag: el.tagName,
                        cls: el.className,
                        text: text
                    });
                }
            }
            return priceEls.slice(0, 15);
        }
    """

    # JavaScript to find title elements
    js_find_titles = """
        () => {
            var links = document.querySelectorAll('a[title]');
            var items = [];
            for (var i = 0; i < links.length; i++) {
                var el = links[i];
                var title = el.getAttribute('title');
                if (title && title.length > 10) {
                    items.push({
                        cls: el.className,
                        title: title.substring(0, 80),
                        href: el.getAttribute('href')
                    });
                }
            }
            return items.slice(0, 5);
        }
    """

    result = page.evaluate(js_find_prices)
    print("\n=== ELEMENTS WITH RUPEE SYMBOL ===")
    for el in result:
        print("Tag=" + el["tag"] + " | Class=" + el["cls"] + " | Text=" + el["text"])

    result2 = page.evaluate(js_find_titles)
    print("\n=== TITLE ELEMENTS ===")
    for el in result2:
        print("Class=" + el["cls"])
        print("Title=" + el["title"])
        print("Href=" + str(el["href"])[:80])
        print("---")

    browser.close()
    print("\nDone!")