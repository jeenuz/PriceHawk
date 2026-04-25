from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="en-IN",
        timezone_id="Asia/Kolkata",
    )
    page = context.new_page()
    page.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', "
        "{get: () => undefined});"
    )

    page.goto(
        "https://www.amazon.in/s?k=dishwasher",
        wait_until="domcontentloaded",
        timeout=30000
    )
    page.wait_for_timeout(4000)

    # Save HTML
    html = page.content()
    with open("data/amazon_page.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Saved HTML — {len(html)} chars")

    # Find price elements with rupee
    js_prices = """
        () => {
            var all = document.querySelectorAll('*');
            var found = [];
            for (var i = 0; i < all.length; i++) {
                var el = all[i];
                var text = el.textContent.trim();
                if (el.children.length === 0 &&
                    text.indexOf('\u20b9') !== -1 &&
                    text.length < 20) {
                    found.push({
                        tag: el.tagName,
                        cls: el.className,
                        text: text
                    });
                }
            }
            return found.slice(0, 15);
        }
    """

    # Find title elements
    js_titles = """
        () => {
            var found = [];
            var candidates = document.querySelectorAll('h2 a, a[href*="/dp/"]');
            for (var i = 0; i < candidates.length; i++) {
                var el = candidates[i];
                var text = el.textContent.trim();
                if (text.length > 10) {
                    found.push({
                        tag: el.tagName,
                        cls: el.className,
                        text: text.substring(0, 80),
                        href: (el.getAttribute('href') || '').substring(0, 80)
                    });
                }
            }
            return found.slice(0, 5);
        }
    """

    # Find product containers
    js_containers = """
        () => {
            var found = [];
            var candidates = document.querySelectorAll(
                '[data-component-type="s-search-result"]'
            );
            for (var i = 0; i < candidates.length; i++) {
                var el = candidates[i];
                found.push({
                    tag: el.tagName,
                    cls: el.className,
                    asin: el.getAttribute('data-asin'),
                    text: el.textContent.trim().substring(0, 100)
                });
            }
            return found.slice(0, 5);
        }
    """

    result = page.evaluate(js_prices)
    print("\n=== PRICE ELEMENTS ===")
    for el in result:
        print(
            "Tag=" + el["tag"] +
            " | Class=" + el["cls"] +
            " | Text=" + el["text"]
        )

    result2 = page.evaluate(js_titles)
    print("\n=== TITLE ELEMENTS ===")
    for el in result2:
        print("Class=" + el["cls"])
        print("Text=" + el["text"])
        print("Href=" + el["href"])
        print("---")

    result3 = page.evaluate(js_containers)
    print("\n=== PRODUCT CONTAINERS ===")
    for el in result3:
        print("Tag=" + el["tag"])
        print("ASIN=" + str(el["asin"]))
        print("Class=" + el["cls"][:60])
        print("---")

    browser.close()
    print("\nDone!")