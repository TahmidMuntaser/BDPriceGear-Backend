import asyncio
import logging
import os
from playwright.async_api import async_playwright, Browser, BrowserContext
from typing import Optional, List
import time

logger = logging.getLogger("browser_pool")

class BrowserPool:
    def __init__(self, pool_size: int = 2):
        self.pool_size = pool_size
        self.browser: Optional[Browser] = None
        self.contexts: List[BrowserContext] = []
        self.available_contexts: asyncio.Queue = asyncio.Queue()
        self.playwright = None
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize browser pool once"""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:
                return
                
            logger.info("🚀 Initializing browser pool...")
            start_time = time.time()
            
            try:
                self.playwright = await async_playwright().start()
                
                # Optimized browser args for cloud
                IS_CLOUD = os.environ.get('RENDER') or os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('HEROKU_APP_NAME')
                
                browser_args = [
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--memory-pressure-off',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding'
                ]
                
                if IS_CLOUD:
                    browser_args.extend([
                        '--single-process',  # Use single process on cloud
                        '--disable-extensions',
                        '--disable-plugins',
                        '--disable-images',  # Don't load images for faster page loads
                        '--disable-javascript',  # We're only scraping HTML
                    ])
                
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=browser_args
                )
                
                # Create pool of contexts
                for i in range(self.pool_size):
                    context = await self.browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        viewport={'width': 800, 'height': 600}
                    )
                    self.contexts.append(context)
                    await self.available_contexts.put(context)
                
                self._initialized = True
                init_time = (time.time() - start_time) * 1000
                logger.info(f"✅ Browser pool initialized in {init_time:.2f}ms with {self.pool_size} contexts")
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize browser pool: {e}")
                await self.cleanup()
                raise

    async def get_context(self) -> BrowserContext:
        """Get an available browser context"""
        if not self._initialized:
            await self.initialize()
        return await self.available_contexts.get()

    async def return_context(self, context: BrowserContext):
        """Return a context to the pool"""
        try:
            # Clear any existing pages
            for page in context.pages:
                await page.close()
            await self.available_contexts.put(context)
        except Exception as e:
            logger.warning(f"Error returning context: {e}")

    async def cleanup(self):
        """Cleanup browser pool"""
        try:
            for context in self.contexts:
                await context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            self._initialized = False
            self.contexts.clear()

# Global browser pool instance
browser_pool = BrowserPool(pool_size=2)

# Cleanup function for graceful shutdown
async def cleanup_browser_pool():
    await browser_pool.cleanup()