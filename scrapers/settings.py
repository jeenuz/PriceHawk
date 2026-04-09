from config import settings

BOT_NAME = "pricehawk"

SPIDER_MODULES = ["scrapers.spiders"]
NEWSPIDER_MODULE = "scrapers.spiders"

# Be polite — wait between requests
DOWNLOAD_DELAY = settings.request_delay
RANDOMIZE_DOWNLOAD_DELAY = True

# Retry failed requests
RETRY_TIMES = settings.max_retries
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Disable cookies (less fingerprinting)
COOKIES_ENABLED = False

# Enable middlewares
DOWNLOADER_MIDDLEWARES = {
    "scrapers.middlewares.useragent.RotateUserAgentMiddleware": 400,
    
}

# Enable database pipeline
ITEM_PIPELINES = {
    "scrapers.pipelines.db_pipeline.PostgreSQLPipeline": 300,
}
# Output settings
#FEEDS = {
#    "data/prices_%(time)s.csv": {
#       "format": "csv",
#       "overwrite": False,
#    }
#}

LOG_LEVEL = "INFO"