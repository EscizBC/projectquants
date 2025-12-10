# main.py
import asyncio
import logging
import threading
import sys
import os
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot_logs.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Глобальные переменные для управления ботами
shop_bot_running = False
log_bot_running = False
shop_bot_task = None
log_bot_task = None

async def run_shop_bot():
    """Асинхронный запуск бота магазина"""
    global shop_bot_running
    
    try:
        logger.info("🛒 Запуск бота магазина QUANTS SHOP...")
        
        # Динамический импорт бота магазина
        import bot
        
        # Проверяем наличие асинхронной функции main
        if hasattr(bot, 'main'):
            shop_bot_running = True
            await bot.main()
        else:
            logger.error("❌ В bot.py не найдена функция main()")
            
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта bot.py: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка в боте магазина: {e}")
    finally:
        shop_bot_running = False
        logger.info("🛒 Бот магазина остановлен")

async def run_log_bot():
    """Асинхронный запуск логгер-бота"""
    global log_bot_running
    
    try:
        logger.info("📊 Запуск логгер-бота...")
        
        # Динамический импорт логгер-бота
        import log
        
        # Проверяем наличие асинхронной функции main
        if hasattr(log, 'main'):
            log_bot_running = True
            await log.main()
        else:
            logger.error("❌ В log.py не найдена функция main()")
            
    except ImportError as e:
        logger.error(f"❌ Ошибка импорта log.py: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка в логгер-боте: {e}")
    finally:
        log_bot_running = False
        logger.info("📊 Логгер-бот остановлен")

def run_async_in_thread(async_func, bot_name):
    """Запускает асинхронную функцию в отдельном потоке"""
    def wrapper():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(async_func())
        except KeyboardInterrupt:
            logger.info(f"⏹️ {bot_name} получил сигнал остановки")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в {bot_name}: {e}")
        finally:
            loop.close()
    
    thread = threading.Thread(target=wrapper, daemon=True, name=f"{bot_name}_thread")
    thread.start()
    return thread

def start_bots():
    """Запускает обоих ботов в отдельных потоках"""
    global shop_bot_task, log_bot_task
    
    logger.info("🚀 Запуск системы ботов...")
    
    # Запускаем бота магазина
    shop_bot_task = run_async_in_thread(run_shop_bot, "ShopBot")
    time.sleep(2)  # Небольшая задержка между запусками
    
    # Запускаем логгер-бот
    log_bot_task = run_async_in_thread(run_log_bot, "LogBot")
    
    logger.info("✅ Оба бота запущены в отдельных потоках")

# Веб-сервер для Render (обязательно)
app = Flask(__name__)

@app.route('/')
def home():
    """Главная страница для проверки работы"""
    status = {
        'shop_bot': 'running' if shop_bot_running else 'stopped',
        'log_bot': 'running' if log_bot_running else 'stopped',
        'service': 'QUANTS SHOP Bots',
        'uptime': time.time() - start_time
    }
    return f"""
    <html>
        <head>
            <title>QUANTS SHOP Bots</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .status {{ padding: 20px; border-radius: 10px; margin: 10px 0; }}
                .running {{ background: #d4edda; color: #155724; }}
                .stopped {{ background: #f8d7da; color: #721c24; }}
                .info {{ background: #d1ecf1; color: #0c5460; padding: 15px; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 QUANTS SHOP Bots Status</h1>
                <div class="info">
                    <p>Система управления ботами магазина и логгирования</p>
                    <p><strong>Uptime:</strong> {int(status['uptime'])} секунд</p>
                </div>
                <div class="status {'running' if status['shop_bot'] == 'running' else 'stopped'}">
                    <h2>🛒 Магазин-бот: {status['shop_bot'].upper()}</h2>
                    <p>Отвечает за продажи, платежи и обработку заказов</p>
                </div>
                <div class="status {'running' if status['log_bot'] == 'running' else 'stopped'}">
                    <h2>📊 Логгер-бот: {status['log_bot'].upper()}</h2>
                    <p>Отслеживает статистику, историю и управляет подтверждениями</p>
                </div>
                <div style="margin-top: 30px;">
                    <h3>📡 Endpoints:</h3>
                    <ul>
                        <li><a href="/health">/health</a> - Проверка здоровья</li>
                        <li><a href="/status">/status</a> - Детальный статус</li>
                        <li><a href="/logs">/logs</a> - Последние логи</li>
                    </ul>
                </div>
            </div>
        </body>
    </html>
    """

@app.route('/health')
def health_check():
    """Health check для Render"""
    if shop_bot_running and log_bot_running:
        return {"status": "healthy", "bots": {"shop": "running", "log": "running"}}, 200
    else:
        return {"status": "unhealthy", "bots": {"shop": shop_bot_running, "log": log_bot_running}}, 503

@app.route('/status')
def status_check():
    """Детальный статус ботов"""
    status = {
        "service": "QUANTS SHOP Bots",
        "timestamp": time.time(),
        "bots": {
            "shop_bot": {
                "status": "running" if shop_bot_running else "stopped",
                "description": "Основной бот магазина для обработки заказов"
            },
            "log_bot": {
                "status": "running" if log_bot_running else "stopped",
                "description": "Бот для логирования и администрирования"
            }
        },
        "shared_data": {
            "file": "shared_data.py",
            "purpose": "Общий доступ к данным о платежах и истории"
        }
    }
    return status

@app.route('/logs')
def show_logs():
    """Показывает последние логи"""
    try:
        with open('bot_logs.log', 'r', encoding='utf-8') as f:
            logs = f.readlines()[-100:]  # Последние 100 строк
        return "<pre>" + "".join(logs) + "</pre>"
    except:
        return "Логи пока недоступны"

# Глобальная переменная времени старта
start_time = time.time()

def start_web_server():
    """Запускает веб-сервер"""
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🌐 Запуск веб-сервера на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 ИНИЦИАЛИЗАЦИЯ QUANTS SHOP БОТОВ")
    logger.info("=" * 50)
    
    # Запускаем ботов в фоновых потоках
    start_bots()
    
    # Даем ботам время на запуск
    time.sleep(3)
    
    # Проверяем статус ботов
    if not shop_bot_running:
        logger.warning("⚠️ Бот магазина не запустился автоматически, пробуем еще раз...")
        time.sleep(2)
        shop_bot_task = run_async_in_thread(run_shop_bot, "ShopBot_Retry")
    
    if not log_bot_running:
        logger.warning("⚠️ Логгер-бот не запустился автоматически, пробуем еще раз...")
        time.sleep(2)
        log_bot_task = run_async_in_thread(run_log_bot, "LogBot_Retry")
    
    # Запускаем веб-сервер в главном потоке
    try:
        start_web_server()
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
        logger.info("Остановка системы...")
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")
    finally:
        logger.info("👋 Система остановлена")