from config import settings

BOT_NAME = "pricehawk"

SPIDER_MODULES = ["scrapers.spiders"]
NEWSPIDER_MODULE = "scrapers.spiders"

# Playwright settings
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ]
}

PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
ASYNCIO_EVENT_LOOP = "asyncio.SelectorEventLoop"

# Be polite
DOWNLOAD_DELAY = 3
RANDOMIZE_DOWNLOAD_DELAY = True

# Retry
RETRY_TIMES = settings.max_retries
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

COOKIES_ENABLED = False

# Middlewares
DOWNLOADER_MIDDLEWARES = {
    "scrapers.middlewares.useragent.RotateUserAgentMiddleware": 400,
}

# Pipeline
ITEM_PIPELINES = {
    "scrapers.pipelines.db_pipeline.PostgreSQLPipeline": 300,
}

LOG_LEVEL = "INFO"