# bot_monitor.py
import asyncio
import time
import logging
from main import shop_bot_running, log_bot_running, run_async_in_thread

logger = logging.getLogger(__name__)

async def monitor_bots():
    """Мониторит состояние ботов и перезапускает при необходимости"""
    while True:
        await asyncio.sleep(60)  # Проверка каждые 60 секунд
        
        if not shop_bot_running:
            logger.warning("⚠️ Бот магазина упал, перезапуск...")
            from main import run_shop_bot
            run_async_in_thread(run_shop_bot, "ShopBot_Recovery")
        
        if not log_bot_running:
            logger.warning("⚠️ Логгер-бот упал, перезапуск...")
            from main import run_log_bot
            run_async_in_thread(run_log_bot, "LogBot_Recovery")
        
        # Логируем статус каждые 5 минут
        if int(time.time()) % 300 == 0:
            logger.info(f"📊 Статус ботов: Магазин={'✅' if shop_bot_running else '❌'}, Логгер={'✅' if log_bot_running else '❌'}")

def start_monitor():
    """Запускает мониторинг в отдельном потоке"""
    import threading
    
    def monitor_loop():
        asyncio.run(monitor_bots())
    
    monitor_thread = threading.Thread(target=monitor_loop, daemon=True, name="BotMonitor")
    monitor_thread.start()
    return monitor_thread