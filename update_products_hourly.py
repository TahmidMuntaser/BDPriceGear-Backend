#!/usr/bin/env python
"""
Lightweight hourly product update script
Runs on Render using APScheduler - no Playwright browser needed
"""
import os
import sys
import django
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management import call_command

# Configure Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bdpricegear-backend'))
django.setup()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def update_products():
    """Run the product scraping and update Supabase"""
    try:
        logger.info("🔄 Starting hourly product update...")
        
        # Run the populate_products command with unlimited products (scrape all)
        # Setting a very high limit ensures all available products are scraped
        call_command('populate_products', limit=1500)
        
        logger.info("✅ Product update completed successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Product update failed: {str(e)}")
        return False

def start_scheduler():
    """Start the background scheduler"""
    logger.info("📅 Initializing product update scheduler...")
    
    scheduler = BackgroundScheduler()
    
    # Schedule job every hour at minute 0
    scheduler.add_job(
        update_products,
        'cron',
        hour='*',
        minute='0',
        id='hourly_update',
        name='Hourly Product Update',
        max_instances=1  # Prevent multiple concurrent runs
    )
    
    scheduler.start()
    logger.info("✅ Scheduler started - will update products hourly")
    logger.info(f"⏰ Next update scheduled for: {scheduler.get_jobs()[0].next_run_time}")
    
    return scheduler

if __name__ == '__main__':
    logger.info(f"🚀 Starting BDPriceGear Product Update Service at {datetime.now()}")
    
    try:
        scheduler = start_scheduler()
        
        # Keep the scheduler running
        import signal
        import time
        
        def signal_handler(sig, frame):
            logger.info('📛 Shutting down scheduler...')
            scheduler.shutdown()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("🔄 Service is running. Press Ctrl+C to stop.")
        
        # Keep the process alive
        while True:
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
