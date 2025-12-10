import logging
import asyncio
import json
import os
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage

# Конфигурация
LOGGER_BOT_TOKEN = "8404076416:AAFkYIAWdrxWiU4NUywQ9NsuSac77y_OWEc"
PURCHASE_HISTORY_FILE = "purchase_history.json"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=LOGGER_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Импорт функций для работы с крипто-платежами
from shared_data import get_crypto_payment, update_crypto_payment_status, delete_crypto_payment

# Загрузка истории покупок
def load_purchase_history():
    if os.path.exists(PURCHASE_HISTORY_FILE):
        try:
            with open(PURCHASE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading purchase history: {e}")
            return []
    return []

# Команда /search для поиска по разным критериям
@dp.message(F.text == "/search")
async def search_command(message: types.Message):
    help_text = (
        "🔍 **Поиск по истории покупок**\n\n"
        "Используйте команду в формате:\n"
        "• `/search номер_заказа` - поиск по номеру сделки\n"
        "• `/search @username` - поиск по имени пользователя\n"
        "• `/search логин:пароль` - поиск по аккаунту\n\n"
        "**Примеры:**\n"
        "`/search #12345` - найти заказ #12345\n"
        "`/search @username` - найти все покупки пользователя\n"
        "`/search login:password` - найти кому принадлежит аккаунт"
    )
    await message.answer(help_text, parse_mode="Markdown")

# Обработка поисковых запросов
@dp.message(F.text.startswith("/search "))
async def handle_search(message: types.Message):
    search_query = message.text.replace("/search ", "").strip()
    
    if not search_query:
        await message.answer("❌ Введите поисковый запрос после команды /search")
        return
    
    history = load_purchase_history()
    
    if not history:
        await message.answer("📭 История покупок пуста")
        return
    
    results = []
    
    # Поиск по номеру заказа
    if search_query.startswith('#') or search_query.isdigit():
        deal_number = search_query.replace('#', '').strip()
        for purchase in history:
            if purchase.get('order') and str(purchase['order'].get('deal_number', '')) == deal_number:
                results.append(purchase)
    
    # Поиск по имени пользователя
    elif search_query.startswith('@'):
        username = search_query.lower().replace('@', '')
        for purchase in history:
            user_info = purchase.get('user_info')
            if user_info:
                user_username = user_info.get('username', '')
                if user_username and username in user_username.lower():
                    results.append(purchase)
    
    # Поиск по логину:пароль
    elif ':' in search_query:
        account_search = search_query.lower()
        for purchase in history:
            accounts = purchase.get('accounts', [])
            for account in accounts:
                if account and account_search in account.lower():
                    results.append(purchase)
                    break
    
    # Поиск по имени/фамилии
    else:
        name_search = search_query.lower()
        for purchase in history:
            user_info = purchase.get('user_info')
            if user_info:
                first_name = user_info.get('first_name', '').lower()
                last_name = user_info.get('last_name', '').lower()
                username = user_info.get('username', '').lower()
                
                if (name_search in first_name or 
                    name_search in last_name or 
                    name_search in username):
                    results.append(purchase)
    
    if not results:
        await message.answer(f"❌ По запросу `{search_query}` ничего не найдено", parse_mode="Markdown")
        return
    
    # Формируем результаты
    if len(results) == 1:
        purchase = results[0]
        await send_purchase_details(message, purchase)
    else:
        await send_search_results(message, results, search_query)

# Отправка детальной информации о покупке
async def send_purchase_details(message: types.Message, purchase):
    user = purchase.get('user_info', {})
    order = purchase.get('order', {})
    time = datetime.datetime.fromisoformat(purchase.get('timestamp', '')).strftime("%Y-%m-%d %H:%M:%S")
    
    accounts = purchase.get('accounts', [])
    accounts_text = "\n".join([f"`{acc}`" for acc in accounts]) if accounts else "Нет данных"
    
    user_name = f"{user.get('first_name', 'N/A')} {user.get('last_name', '')}".strip()
    user_username = f"@{user.get('username', 'N/A')}" if user.get('username') else "N/A"
    
    details_text = (
        "🔍 **Результат поиска**\n\n"
        f"**👤 Пользователь:**\n"
        f"• Имя: {user_name}\n"
        f"• Username: {user_username}\n"
        f"• ID: `{user.get('id', 'N/A')}`\n\n"
        f"**📦 Заказ:**\n"
        f"• Номер: #{order.get('deal_number', 'N/A')}\n"
        f"• Количество: {order.get('count', 'N/A')} аккаунтов\n"
        f"• Цена: ${order.get('price', 'N/A')}\n"
        f"• Время: {time}\n\n"
        f"**🔑 Аккаунты:**\n{accounts_text}"
    )
    
    await message.answer(details_text, parse_mode="Markdown")

# Отправка списка результатов
async def send_search_results(message: types.Message, results, search_query):
    results_text = f"🔍 **Найдено {len(results)} результатов по запросу `{search_query}`:**\n\n"
    
    for i, purchase in enumerate(results, 1):
        user = purchase.get('user_info', {})
        order = purchase.get('order', {})
        time = datetime.datetime.fromisoformat(purchase.get('timestamp', '')).strftime("%m/%d %H:%M")
        
        user_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        user_username = f"@{user.get('username', 'N/A')}" if user.get('username') else "N/A"
        
        accounts = purchase.get('accounts', [])
        first_account = accounts[0] if accounts else "Нет данных"
        
        results_text += (
            f"**{i}. #{order.get('deal_number', 'N/A')}** - {time}\n"
            f"👤: {user_name} ({user_username})\n"
            f"📦: {order.get('count', 'N/A')} акк. за ${order.get('price', 'N/A')}\n"
            f"🔑: {first_account}" + ("..." if len(accounts) > 1 else "") + "\n\n"
        )
    
    # Добавляем кнопки для навигации
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")],
        [InlineKeyboardButton(text="📋 Вся история", callback_data="show_history")],
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await message.answer(results_text, reply_markup=reply_markup, parse_mode="Markdown")

# Обработка подтверждения крипто-платежа (исправленная версия с правильным порядком)
@dp.callback_query(F.data.startswith("confirm_crypto_"))
async def confirm_crypto_payment_handler(callback_query: types.CallbackQuery):
    payment_id = callback_query.data.replace("confirm_crypto_", "")
    
    try:
        # Получаем данные платежа
        payment_data = get_crypto_payment(payment_id)
        
        if not payment_data:
            await callback_query.message.answer(
                f"❌ Ошибка подтверждения\n\n"
                f"Платеж {payment_id} не найден в базе."
            )
            await callback_query.answer()
            return
        
        if payment_data.get('status') != 'waiting':
            await callback_query.message.answer(
                f"⚠️ Платеж уже обработан\n\n"
                f"Статус платежа: {payment_data.get('status', 'unknown')}"
            )
            await callback_query.answer()
            return
        
        # Обновляем статус платежа
        update_crypto_payment_status(payment_id, 'confirmed')
        
        # Импортируем основной бот и функции
        from bot import bot as main_bot, generate_accounts, save_purchase_to_history, send_message_with_photo
        
        # Генерируем аккаунты
        accounts = generate_accounts(payment_data['order']['count'])
        
        # Сохраняем информацию о пользователе
        try:
            user_chat = await main_bot.get_chat(payment_data['user_id'])
            user_info = {
                'id': user_chat.id,
                'first_name': user_chat.first_name,
                'last_name': user_chat.last_name,
                'username': user_chat.username
            }
        except:
            user_info = {
                'id': payment_data['user_id'],
                'first_name': 'Unknown',
                'last_name': '',
                'username': 'unknown'
            }
        
        # Сохраняем в историю
        save_purchase_to_history(user_info, payment_data['order'], accounts)
        
        accounts_text = "\n".join([f"`{acc}`" for acc in accounts])
        
        # 1. СНАЧАЛА отправляем шаг 3 из 3 с предложением оставить отзыв С ФОТО
        step3_text = (
            "Шаг 3 из 3... Получение товара!\n\n"
            "❤️ Спасибо большое за покупку, приятель!\n"
            "Нам будет очень приятно если вы оставите отзыв в личных сообщениях нашего менеджера"
        )
        
        keyboard = [
            [InlineKeyboardButton(text="⭐ Оставить отзыв", url="https://t.me/f3ckm0ney")],
            [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        # Используем функцию send_message_with_photo для шага 3
        await send_message_with_photo(
            payment_data['user_id'],
            "step3.png",
            step3_text,
            reply_markup=reply_markup,
            delete_previous=False
        )
        
        # 2. ПОТОМ отправляем сообщение с аккаунтами пользователю БЕЗ ФОТО
        success_text = (
            f"✅ Оплата подтверждена!\n\n"
            f"🎉 Ваши аккаунты готовы:\n\n"
            f"{accounts_text}\n\n"
            f"🔹 Номер сделки: {payment_data['order']['deal_number']}\n"
            f"🔹 Количество: {payment_data['order']['count']} аккаунтов\n\n"
            f"Спасибо за покупку! 🛍️"
        )
        
        # Отправляем просто текстовое сообщение без фото
        await main_bot.send_message(
            chat_id=payment_data['user_id'],
            text=success_text,
            parse_mode="Markdown"
        )
        
        # Удаляем платеж
        delete_crypto_payment(payment_id)
        
        # Получаем информацию о пользователе для лога
        user_info_text = f"ID: {payment_data['user_id']}"
        try:
            user_chat = await main_bot.get_chat(payment_data['user_id'])
            user_info_text = f"@{user_chat.username}" if user_chat.username else f"{user_chat.first_name}"
        except:
            pass
        
        # Отправляем подтверждение в логгер
        await callback_query.message.answer(
            f"✅ Оплата подтверждена\n\n"
            f"Платеж {payment_id} успешно подтвержден.\n"
            f"Пользователь {user_info_text} получил свои аккаунты."
        )
        # Удаляем кнопки
        await callback_query.message.edit_reply_markup(reply_markup=None)
        
    except Exception as e:
        logger.error(f"Error confirming payment {payment_id}: {e}")
        await callback_query.message.answer(f"❌ Ошибка подтверждения: {str(e)}")
    
    await callback_query.answer()

# Обработка отклонения крипто-платежа
@dp.callback_query(F.data.startswith("reject_crypto_"))
async def reject_crypto_payment_handler(callback_query: types.CallbackQuery):
    payment_id = callback_query.data.replace("reject_crypto_", "")
    
    try:
        # Получаем данные платежа
        payment_data = get_crypto_payment(payment_id)
        
        if not payment_data:
            await callback_query.message.answer(
                f"❌ Ошибка отклонения\n\n"
                f"Платеж {payment_id} не найден в базе."
            )
            await callback_query.answer()
            return
        
        if payment_data.get('status') != 'waiting':
            await callback_query.message.answer(
                f"⚠️ Платеж уже обработан\n\n"
                f"Статус платежа: {payment_data.get('status', 'unknown')}"
            )
            await callback_query.answer()
            return
        
        # Обновляем статус платежа
        update_crypto_payment_status(payment_id, 'rejected')
        
        # Импортируем основной бот
        from bot import bot as main_bot
        
        # Отправляем уведомление пользователю
        rejection_text = (
            "❌ Оплата отклонена\n\n"
            "Ваш платеж был отклонен администратором.\n"
            "Возможные причины:\n"
            "• Неверная сумма\n"
            "• Нечитаемый скриншот\n"
            "• Подозрительная активность\n\n"
            "📞 Для выяснения причин обратитесь: @f3ckm0ney"
        )
        
        await main_bot.send_message(
            chat_id=payment_data['user_id'], 
            text=rejection_text
        )
        
        # Удаляем платеж
        delete_crypto_payment(payment_id)
        
        # Получаем информацию о пользователе
        user_info = f"ID: {payment_data['user_id']}"
        try:
            user_chat = await main_bot.get_chat(payment_data['user_id'])
            user_info = f"@{user_chat.username}" if user_chat.username else f"{user_chat.first_name}"
        except:
            pass
        
        # Отправляем подтверждение отклонения
        await callback_query.message.answer(
            f"❌ Оплата отклонена\n\n"
            f"Платеж {payment_id} отклонен.\n"
            f"Пользователь {user_info} уведомлен об отклонении."
        )
        # Удаляем кнопки
        await callback_query.message.edit_reply_markup(reply_markup=None)
        
    except Exception as e:
        logger.error(f"Error rejecting payment {payment_id}: {e}")
        await callback_query.message.answer(f"❌ Ошибка отклонения: {str(e)}")
    
    await callback_query.answer()

# Команда /start для логгер-бота
@dp.message(F.text == "/start")
async def logger_start_command(message: types.Message):
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика продаж", callback_data="show_stats")],
        [InlineKeyboardButton(text="📋 История покупок", callback_data="show_history")],
        [InlineKeyboardButton(text="🔍 Поиск по заказам", callback_data="search_info")],
        [InlineKeyboardButton(text="🔄 Обновить данные", callback_data="refresh_data")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    welcome_text = (
        "📊 **Бот-логгер QUANTS SHOP**\n\n"
        "Здесь вы можете отслеживать все продажи в реальном времени:\n\n"
        "• 📊 Статистика продаж\n"
        "• 📋 Полная история покупок\n" 
        "• 🔍 Поиск по заказам и аккаунтам\n"
        "• 🔄 Актуальные данные\n\n"
        "**Новая команда:** `/search` - поиск по заказам\n\n"
        "Выберите действие:"
    )
    
    await message.answer(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# Обработка кнопки поиска
@dp.callback_query(F.data == "search_info")
async def search_info_handler(callback_query: types.CallbackQuery):
    help_text = (
        "🔍 **Поиск по истории покупок**\n\n"
        "Используйте команду:\n"
        "`/search запрос`\n\n"
        "**Поддерживаемые форматы:**\n"
        "• `/search #12345` - по номеру заказа\n"
        "• `/search @username` - по имени пользователя\n" 
        "• `/search login:pass` - по аккаунту\n"
        "• `/search Имя` - по имени/фамилии\n\n"
        "**Примеры:**\n"
        "`/search #12345`\n"
        "`/search @ivanov`\n"
        "`/search username:password`\n"
        "`/search Иван`"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="↩️ Назад в меню", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback_query.message.edit_text(help_text, reply_markup=reply_markup, parse_mode="Markdown")
    await callback_query.answer()

# Показать статистику
@dp.callback_query(F.data == "show_stats")
async def show_stats_handler(callback_query: types.CallbackQuery):
    history = load_purchase_history()
    
    if not history:
        await callback_query.message.edit_text("📊 **Статистика продаж**\n\nПока нет данных о продажах.")
        await callback_query.answer()
        return
    
    # Считаем статистику
    total_sales = len(history)
    total_revenue = sum(purchase.get('order', {}).get('price', 0) for purchase in history)
    total_accounts = sum(purchase.get('order', {}).get('count', 0) for purchase in history)
    
    # Самые популярные пакеты
    pack_counts = {}
    for purchase in history:
        count = purchase.get('order', {}).get('count', 0)
        pack_counts[count] = pack_counts.get(count, 0) + 1
    
    most_popular = max(pack_counts.items(), key=lambda x: x[1]) if pack_counts else (0, 0)
    
    # Последние 24 часа
    now = datetime.datetime.now()
    last_24h = []
    for purchase in history:
        try:
            purchase_time = datetime.datetime.fromisoformat(purchase.get('timestamp', ''))
            if (now - purchase_time).total_seconds() <= 86400:
                last_24h.append(purchase)
        except:
            continue
    
    stats_text = (
        "📊 **Статистика продаж**\n\n"
        f"📈 Всего продаж: **{total_sales}**\n"
        f"💰 Общая выручка: **${total_revenue:.2f}**\n"
        f"🔑 Всего аккаунтов: **{total_accounts}**\n"
        f"🏆 Популярный пакет: **{most_popular[0]} акк.** ({most_popular[1]} раз)\n"
        f"⏰ За 24 часа: **{len(last_24h)}** продаж\n\n"
        f"📅 Последние продажи:\n"
    )
    
    # Добавляем последние 5 продаж
    for i, purchase in enumerate(history[-5:], 1):
        user = purchase.get('user_info', {})
        order = purchase.get('order', {})
        time = datetime.datetime.fromisoformat(purchase.get('timestamp', '')).strftime("%H:%M")
        
        username = user.get('username', 'N/A')
        stats_text += (
            f"{i}. @{username} - {order.get('count', 0)} акк. - ${order.get('price', 0)} - {time}\n"
        )
    
    keyboard = [
        [InlineKeyboardButton(text="📋 Полная история", callback_data="show_history")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="show_stats")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback_query.message.edit_text(stats_text, reply_markup=reply_markup, parse_mode="Markdown")
    await callback_query.answer()

# Показать историю покупок
@dp.callback_query(F.data == "show_history")
async def show_history_handler(callback_query: types.CallbackQuery):
    history = load_purchase_history()
    
    if not history:
        await callback_query.message.edit_text("📋 **История покупок**\n\nПока нет данных о покупках.")
        await callback_query.answer()
        return
    
    # Показываем последние 10 покупок
    recent_purchases = history[-10:]
    
    history_text = "📋 **Последние 10 покупок**\n\n"
    
    for i, purchase in enumerate(reversed(recent_purchases), 1):
        user = purchase.get('user_info', {})
        order = purchase.get('order', {})
        time = datetime.datetime.fromisoformat(purchase.get('timestamp', '')).strftime("%m/%d %H:%M")
        accounts = purchase.get('accounts', [])
        accounts_preview = ", ".join(accounts[:2]) + ("..." if len(accounts) > 2 else "")
        
        history_text += (
            f"**{i}. {time}**\n"
            f"👤: {user.get('first_name', '')} {user.get('last_name', '')} "
            f"(@{user.get('username', 'N/A')})\n"
            f"📦: {order.get('count', 0)} акк. за ${order.get('price', 0)} "
            f"(#{order.get('deal_number', 'N/A')})\n"
            f"🔑: {accounts_preview}\n\n"
        )
    
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="show_history")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback_query.message.edit_text(history_text, reply_markup=reply_markup, parse_mode="Markdown")
    await callback_query.answer()

# Обновить данные
@dp.callback_query(F.data == "refresh_data")
async def refresh_data_handler(callback_query: types.CallbackQuery):
    history = load_purchase_history()
    total_sales = len(history)
    
    refresh_text = (
        f"🔄 **Данные обновлены**\n\n"
        f"📊 Всего записей в истории: **{total_sales}**\n"
        f"⏰ Последнее обновление: {datetime.datetime.now().strftime('%H:%M:%S')}\n\n"
        f"Данные автоматически обновляются при каждой новой покупке."
    )
    
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="show_stats")],
        [InlineKeyboardButton(text="📋 История", callback_data="show_history")],
        [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback_query.message.edit_text(refresh_text, reply_markup=reply_markup, parse_mode="Markdown")
    await callback_query.answer()

# Назад в главное меню
@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback_query: types.CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="📊 Статистика продаж", callback_data="show_stats")],
        [InlineKeyboardButton(text="📋 История покупок", callback_data="show_history")],
        [InlineKeyboardButton(text="🔍 Поиск по заказам", callback_data="search_info")],
        [InlineKeyboardButton(text="🔄 Обновить данные", callback_data="refresh_data")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    welcome_text = (
        "📊 **Бот-логгер QUANTS SHOP**\n\n"
        "Здесь вы можете отслеживать все продажи в реальном времени:\n\n"
        "• 📊 Статистика продаж\n"
        "• 📋 Полная история покупок\n" 
        "• 🔍 Поиск по заказам и аккаунтам\n"
        "• 🔄 Актуальные данные\n\n"
        "**Новая команда:** `/search` - поиск по заказам\n\n"
        "Выберите действие:"
    )
    
    await callback_query.message.edit_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")
    await callback_query.answer()

# Запуск логгер-бота
# async def main():
#     logger.info("Логгер-бот запущен...")
#     await dp.start_polling(bot)

# if __name__ == '__main__':
#     asyncio.run(main())

async def main():
    """Главная функция для запуска из main.py"""
    logger.info("📊 Логгер-бот запущен...")
    await dp.start_polling(bot)