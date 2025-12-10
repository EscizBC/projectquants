import asyncio
import logging
import sys
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def run_bot():
    """Запуск основного бота магазина"""
    try:
        from bot import main as bot_main
        logger.info("🛒 Запуск бота магазина...")
        await bot_main()
    except Exception as e:
        logger.error(f"❌ Ошибка бота магазина: {e}")

async def run_log_bot():
    """Запуск логгер-бота"""
    try:
        from log import main as log_main
        logger.info("📊 Запуск логгер-бота...")
        await log_main()
    except Exception as e:
        logger.error(f"❌ Ошибка логгер-бота: {e}")

async def main():
    """Запуск обоих ботов одновременно"""
    logger.info("🚀 Запуск системы ботов QUANTS SHOP...")
    
    # Запускаем обоих ботов параллельно
    await asyncio.gather(
        run_bot(),
        run_log_bot(),
        return_exceptions=True  # Если один бот упадет, другой продолжит работу
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Остановка системы ботов...")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")