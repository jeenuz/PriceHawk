from playwright.sync_api import sync_playwright

def test_basic():
   with sync_playwright() as p:
       browser=p.chromium.launch(headless=False)
       
       page=browser.new_page()
       page.goto("https://books.toscrape.com")
       
       title=page.title()
       print(f"page title: {title}")
       
       books=page.query_selector_all("article.product_pod")
       print(f"found {len(books)} books")
       book_list=[]
       for book in books:
           book_title=book.query_selector("h3 a").get_attribute("title")
           price=book.query_selector("p.price_color").inner_text()
           book_row={"title":book_title,"price":price}
           book_list.append(book_row)
       print(book_list)
       
       page.screenshot(path="data/screenshot.png")
       print("Screenshot saved to data/screenshot.png")
       
       browser.close()
       print("Done")
       
if __name__ == "__main__":
    test_basic()