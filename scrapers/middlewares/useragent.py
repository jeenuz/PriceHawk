from fake_useragent import UserAgent
from loguru import logger


class RotateUserAgentMiddleware:
    """Rotates user agent on every request to avoid detection."""

    def __init__(self):
        self.ua = UserAgent()

    def process_request(self, request, spider):
        user_agent = self.ua.random
        request.headers["User-Agent"] = user_agent
        logger.debug(f"Using user agent: {user_agent[:50]}...")
        return None