import logging
import random
import string
import requests
import asyncio
import json
import datetime
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import aiohttp

# Конфигурация
CRYPTOBOT_API_TOKEN = "488538:AAc0GLQZmSL0X1zahatLzJTiO6OV0EJno6F"
BOT_TOKEN = "8247906483:AAEsQo_w2juQ-nFGER9tDhZdjPJqyAIVCaA"
PURCHASE_HISTORY_FILE = "purchase_history.json"
LOGGER_BOT_TOKEN = "8404076416:AAFkYIAWdrxWiU4NUywQ9NsuSac77y_OWEc"
ADMIN_CHAT_ID = "6380771602"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
logger_bot = Bot(token=LOGGER_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Глобальное хранилище
active_invoices = {}  # invoice_id -> order_info
user_sessions = {}    # user_id -> session_data
referral_data = {}    # user_id -> referral_info

# Импорт функций для работы с крипто-платежами
from shared_data import update_crypto_payment

class CustomAmountStates(StatesGroup):
    waiting_for_amount = State()

# Функция для отправки сообщения с фото (исправленная)
async def send_message_with_photo(chat_id_or_message, photo_path, caption, reply_markup=None, delete_previous=True, parse_mode=None):
    try:
        # Если это числовой chat_id
        if isinstance(chat_id_or_message, (int, str)):
            chat_id = int(chat_id_or_message)
            
            photo = types.FSInputFile(photo_path)
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
            
        # Если это объект сообщения или callback
        else:
            if delete_previous:
                try:
                    if hasattr(chat_id_or_message, 'message'):
                        await chat_id_or_message.message.delete()
                    else:
                        await chat_id_or_message.delete()
                except:
                    pass
            
            photo = types.FSInputFile(photo_path)
            
            if hasattr(chat_id_or_message, 'message'):
                await chat_id_or_message.message.answer_photo(
                    photo=photo,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            else:
                await chat_id_or_message.answer_photo(
                    photo=photo,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
                
    except Exception as e:
        logger.error(f"Error sending photo {photo_path}: {e}")
        # Если не удалось отправить фото, отправляем просто текст
        if isinstance(chat_id_or_message, (int, str)):
            chat_id = int(chat_id_or_message)
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            if hasattr(chat_id_or_message, 'message'):
                await chat_id_or_message.message.answer(
                    caption,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            else:
                await chat_id_or_message.answer(
                    caption,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )

# Функция для отправки уведомления в логгер-бот
async def send_logger_notification(user_info, order, accounts, payment_method="CryptoBot"):
    """Отправляет уведомление о покупке в логгер-бот"""
    try:
        accounts_text = "\n".join([f"`{acc}`" for acc in accounts])
        
        log_message = (
            f"🛒 **НОВАЯ ПОКУПКА ЧЕРЕЗ {payment_method}**\n\n"
            f"👤 **Покупатель:**\n"
            f"   ID: `{user_info['id']}`\n"
            f"   Имя: {user_info.get('first_name', 'N/A')}\n"
            f"   Фамилия: {user_info.get('last_name', 'N/A')}\n"
            f"   Username: @{user_info.get('username', 'N/A')}\n\n"
            f"📦 **Заказ:**\n"
            f"   Количество: {order['count']} аккаунтов\n"
            f"   Сумма: ${order['price']}\n"
            f"   Номер сделки: #{order['deal_number']}\n"
            f"   Способ оплаты: {payment_method}\n"
            f"   Время: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"🔑 **Аккаунты:**\n{accounts_text}"
        )
        
        await logger_bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=log_message,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error sending logger notification: {e}")

# Обработка выбора своего количества
async def handle_custom_amount(callback_query: CallbackQuery, state: FSMContext):
    instruction_text = (
        "🔢 Выбор своего количества\n\n"
        "Введите количество аккаунтов которое хотите приобрести:\n\n"
        "💰 Цена за 1 аккаунт: 10$\n"
        "💵 Формула расчета: количество × 10$\n\n"
        "Примеры:\n"
        "• 7 аккаунтов = 70$\n"
        "• 15 аккаунтов = 150$\n"
        "• 25 аккаунтов = 250$\n\n"
        "📝 Введите число от 1 до 100:"
    )
    
    try:
        await callback_query.message.delete()
    except:
        pass
    
    await callback_query.message.answer(instruction_text)
    await state.set_state(CustomAmountStates.waiting_for_amount)
    await callback_query.answer()

# Обработка ввода своего количества
@dp.message(CustomAmountStates.waiting_for_amount)
async def process_custom_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        
        if amount < 1:
            await message.answer("❌ Количество должно быть не менее 1 аккаунта.")
            return
        
        if amount > 100:
            await message.answer("❌ Максимальное количество - 100 аккаунтов за один заказ.")
            return
        
        price = amount * 10
        deal_number = random.randint(1000, 9999)
        
        # Сохраняем заказ в сессии пользователя
        user_id = message.from_user.id
        user_sessions[user_id] = {
            'order': {
                'count': amount,
                'price': price,
                'deal_number': deal_number,
                'user_id': user_id
            }
        }
        
        keyboard = [
            [InlineKeyboardButton(text="💳 Оплата CryptoBot", callback_data="cryptobot_payment")],
            [InlineKeyboardButton(text="₿ Оплата на криптокошелек", callback_data="crypto_wallet_payment")],
            [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_packs")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await send_message_with_photo(
            message,
            "step2.png",
            f"Шаг 2 из 3... Оплата товара\n\n"
            f"Ты почти у цели вот твой заказ, все ли верно? ✅\n"
            f"🔹 Товар: Revolut Accounts \n"
            f"🔹 Количество: {amount} штук\n"
            f"🔹 Сумма заказа: {price}$ \n"
            f"🔹 Номер сделки: {deal_number} \n\n"
            f"Почти все готово, осталось оплатить заказ, выбери ниже способ пополнения ✔️",
            reply_markup=reply_markup,
            delete_previous=False
        )
        
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число.")
    except Exception as e:
        logger.error(f"Error processing custom amount: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз.")
        await state.clear()


# Состояния для FSM
class CryptoPaymentStates(StatesGroup):
    waiting_for_screenshot = State()

# Функции для работы с истории покупок
def load_purchase_history():
    try:
        with open(PURCHASE_HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_purchase_to_history(user_info, order, accounts):
    history = load_purchase_history()
    
    purchase_data = {
        'timestamp': datetime.datetime.now().isoformat(),
        'user_info': user_info,
        'order': order,
        'accounts': accounts
    }
    
    history.append(purchase_data)
    
    with open(PURCHASE_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# CryptoBot API функции
def create_cryptobot_invoice(amount, currency="USD"):
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_API_TOKEN,
        "Content-Type": "application/json"
    }
    
    data = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Оплата за аккаунты QUANTS SHOP",
        "hidden_message": "Спасибо за покупку!",
        "paid_btn_name": "viewItem",
        "paid_btn_url": "https://t.me/quants_shop_bot",
        "payload": str(random.randint(100000, 999999)),
        "allow_comments": False,
        "allow_anonymous": False,
        "expires_in": 3600
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        result = response.json()
        if result.get("ok"):
            return result["result"]
        else:
            logger.error(f"CryptoBot API Error: {result}")
            return None
    except Exception as e:
        logger.error(f"CryptoBot request failed: {e}")
        return None

def check_invoice_status(invoice_id):
    url = f"https://pay.crypt.bot/api/getInvoices"
    headers = {
        "Crypto-Pay-API-Token": CRYPTOBOT_API_TOKEN
    }
    
    params = {
        "invoice_ids": str(invoice_id),
        "count": 1
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        result = response.json()
        if result.get("ok") and result["result"]["items"]:
            invoice = result["result"]["items"][0]
            return invoice.get("status"), invoice.get("paid_asset"), invoice.get("paid_amount")
        return None, None, None
    except Exception as e:
        logger.error(f"CryptoBot check invoice failed: {e}")
        return None, None, None

# Генерация случайных аккаунтов
def generate_accounts(count):
    accounts = []
    for _ in range(count):
        login = ''.join(random.choices(string.ascii_uppercase + string.digits, k=11))
        password = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        accounts.append(f"{login}:{password}")
    return accounts

# Команда /start с фото и обработкой рефералов
@dp.message(F.text.startswith("/start"))
async def start_command(message: types.Message):
    # Обработка реферальной ссылки
    referral_id = None
    if len(message.text.split()) > 1:
        args = message.text.split()[1]
        if args.startswith('ref'):
            referral_id = args[3:]  # Убираем 'ref' из начала
    
    # Если есть реферал и пользователь новый
    if referral_id and str(message.from_user.id) != referral_id:
        if str(message.from_user.id) not in referral_data:
            referral_data[str(message.from_user.id)] = {
                'referrer_id': referral_id,
                'has_purchased': False
            }
            # Сохраняем что реферер привел нового пользователя
            if referral_id not in referral_data:
                referral_data[referral_id] = {'referrals': 0, 'earnings': 0}
            referral_data[referral_id]['referrals'] = referral_data.get(referral_id, {}).get('referrals', 0) + 1
    
    keyboard = [
        [InlineKeyboardButton(text="🛒 Купить аккаунты", callback_data="buy_accounts")],
        [
            InlineKeyboardButton(text="🛎️ Поддержка", callback_data="support"),
            InlineKeyboardButton(text="❓ FAQ", callback_data="faq")
        ],
        [InlineKeyboardButton(text="🎯 Удачные сделки", callback_data="successful_deals")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton(text="💼 Заработать", callback_data="earn_money")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    # Текст сообщения
    welcome_text = "Добро пожаловать в QUANTS SHOP ✨\n\nДавно хотел приобрести качественные Revolut аккаунты с балансом? Тебе определенно к нам! ⭐️\n\nНиже располагается меню, ознакамливайся 🎲"
    
    if referral_id and str(message.from_user.id) != referral_id:
        welcome_text += f"\n\n🎁 Ты был приглашен другом! При первой покупке он получит бонус!"
    
    await send_message_with_photo(
        message,
        "main.png",
        welcome_text,
        reply_markup=reply_markup,
        delete_previous=False
    )

# Команда /buy
@dp.message(F.text == "/buy")
async def buy_command(message: types.Message):
    await show_buy_options(message)

# Команда /reviews
@dp.message(F.text == "/reviews")
async def reviews_command(message: types.Message):
    reviews_text = (
        "🔍 Хочешь убедиться в нашей надежности?\n"
        "📢 Присоединяйся к нашему официальному каналу:\n"
        "👉 Отзывы & Анонсы (https://t.me/quantsreview)\n\n"
        "Здесь ты найдешь:\n"
        "✅ Реальные отзывы покупателей с пруфами\n"
        "✅ Акции и конкурсы с крутыми призами\n"
        "✅ Свежие анонсы обновлений и спецпредложений\n\n"
        "Подпишись сейчас – не упусти выгоду! 🎁\n\n"
        "P.S. Все честно – мы ценим твое доверие! 😊"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="📢 Канал", url="https://t.me/quantsreview")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await send_message_with_photo(
        message,
        "deals.png",
        reviews_text,
        reply_markup=reply_markup,
        delete_previous=False
    )

# Команда /faq
@dp.message(F.text == "/faq")
async def faq_command(message: types.Message):
    keyboard = [
        [InlineKeyboardButton(text="📚 Перейти в FAQ", url="https://t.me/quantsfaq")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await send_message_with_photo(
        message,
        "faq.png",
        "❓ Часто задаваемые вопросы собраны в нашем канале FAQ\n\n"
        "Переходи по кнопке ниже чтобы ознакомиться с ответами на популярные вопросы 👇",
        reply_markup=reply_markup,
        delete_previous=False
    )

# Обработка успешной оплаты с учетом рефералов
async def process_successful_payment(user_id, order, invoice_id=None, payment_method="CryptoBot"):
    # Генерируем аккаунты
    accounts = generate_accounts(order['count'])
    
    # Сохраняем информацию о пользователе
    user = await bot.get_chat(user_id)
    user_info = {
        'id': user.id,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'username': user.username
    }
    
    # Сохраняем в историю
    save_purchase_to_history(user_info, order, accounts)
    
    # Отправляем уведомление в логгер-бот
    await send_logger_notification(user_info, order, accounts, payment_method)
    
    accounts_text = "\n".join([f"`{acc}`" for acc in accounts])
    
    # Проверяем реферальную систему
    referral_bonus_text = ""
    user_id_str = str(user_id)
    if user_id_str in referral_data and not referral_data[user_id_str]['has_purchased']:
        referrer_id = referral_data[user_id_str]['referrer_id']
        bonus_amount = order['price'] * 0.05  # 5% от покупки
        
        # Начисляем бонус рефереру
        if referrer_id in referral_data:
            referral_data[referrer_id]['earnings'] = referral_data[referrer_id].get('earnings', 0) + bonus_amount
            referral_bonus_text = f"\n\n🎉 Твой друг получил бонус: ${bonus_amount:.2f}!"
        
        # Отмечаем что пользователь совершил покупку
        referral_data[user_id_str]['has_purchased'] = True
    
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
    
    await send_message_with_photo(
        user_id,
        "step3.png",
        step3_text,
        reply_markup=reply_markup,
        delete_previous=False
    )
    
    # 2. ПОТОМ отправляем сообщение с аккаунтами БЕЗ ФОТО
    success_text = (
        f"✅ Оплата подтверждена!\n\n"
        f"🎉 Ваши аккаунты готовы:\n\n"
        f"{accounts_text}\n\n"
        f"🔹 Номер сделки: {order['deal_number']}\n"
        f"🔹 Количество: {order['count']} аккаунтов"
        f"{referral_bonus_text}\n\n"
        f"Спасибо за покупку! 🛍️"
    )
    
    # Отправляем просто текстовое сообщение без фото
    await bot.send_message(
        chat_id=user_id,
        text=success_text,
        parse_mode="Markdown"
    )
    
    # Удаляем инвойс из активных
    if invoice_id and invoice_id in active_invoices:
        del active_invoices[invoice_id]

# Функция для обработки успешной оплаты (для использования из логгер-бота)
async def process_successful_payment_external(user_id, order):
    """Внешняя функция для обработки оплаты из логгер-бота"""
    # Генерируем аккаунты
    accounts = generate_accounts(order['count'])
    
    # Сохраняем информацию о пользователе
    try:
        user = await bot.get_chat(user_id)
        user_info = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username
        }
    except:
        user_info = {
            'id': user_id,
            'first_name': 'Unknown',
            'last_name': '',
            'username': 'unknown'
        }
    
    # Сохраняем в историю
    save_purchase_to_history(user_info, order, accounts)
    
    # Отправляем уведомление в логгер-бот
    await send_logger_notification(user_info, order, accounts, "Криптокошелек")
    
    accounts_text = "\n".join([f"`{acc}`" for acc in accounts])
    
    # Проверяем реферальную систему
    referral_bonus_text = ""
    user_id_str = str(user_id)
    if user_id_str in referral_data and not referral_data[user_id_str]['has_purchased']:
        referrer_id = referral_data[user_id_str]['referrer_id']
        bonus_amount = order['price'] * 0.05  # 5% от покупки
        
        # Начисляем бонус рефереру
        if referrer_id in referral_data:
            referral_data[referrer_id]['earnings'] = referral_data[referrer_id].get('earnings', 0) + bonus_amount
            referral_bonus_text = f"\n\n🎉 Твой друг получил бонус: ${bonus_amount:.2f}!"
        
        # Отмечаем что пользователь совершил покупку
        referral_data[user_id_str]['has_purchased'] = True
    
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
    
    await send_message_with_photo(
        user_id,
        "step3.png",
        step3_text,
        reply_markup=reply_markup,
        delete_previous=False
    )
    
    # 2. ПОТОМ отправляем сообщение с аккаунтами БЕЗ ФОТО
    success_text = (
        f"✅ Оплата подтверждена!\n\n"
        f"🎉 Ваши аккаунты готовы:\n\n"
        f"{accounts_text}\n\n"
        f"🔹 Номер сделки: {order['deal_number']}\n"
        f"🔹 Количество: {order['count']} аккаунтов"
        f"{referral_bonus_text}\n\n"
        f"Спасибо за покупку! 🛍️"
    )
    
    # Отправляем просто текстовое сообщение без фото
    await bot.send_message(
        chat_id=user_id,
        text=success_text,
        parse_mode="Markdown"
    )

# Обработка кнопки "Поддержка"
@dp.callback_query(F.data == "support")
async def support_handler(callback_query: CallbackQuery):
    # Генерируем случайные 6 цифр для номера обращения
    ticket_number = ''.join(random.choices(string.digits, k=6))
    
    support_text = (
        f"🛎️ Нужна помощь? Обращайся правильно!\n"
        f"🔹 Твой номер обращения: #{ticket_number}\n"
        f"🔹 Менеджер поддержки: @f3ckm0ney\n\n"
        f"📌 Правила обращения:\n"
        f"✅ Будь вежлив и точен – опиши проблему четко и без лишних сообщений.\n"
        f"✅ Не спрашивай о статусе чека – обработка занимает до 15 минут.\n"
        f"✅ Нет спаму! Одно подробное сообщение > 10 коротких.\n\n"
        f"🚀 Мы решим вопрос быстро, если ты следуешь этим простым правилам.\n\n"
        f"👉 Просто перешли этот номер (#{ticket_number}) менеджеру – и жди ответа!\n\n"
        f"P.S. Чем точнее опишешь проблему, тем быстрее получишь решение. 😉"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="✉️ Написать сообщение", url="https://t.me/f3ckm0ney")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await send_message_with_photo(
        callback_query,
        "support.png",
        support_text,
        reply_markup=reply_markup
    )
    await callback_query.answer()

# Обработка кнопки "Реферальная система"
@dp.callback_query(F.data == "referral")
async def referral_handler(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    
    # Получаем статистику рефералов
    referrals_count = referral_data.get(user_id, {}).get('referrals', 0)
    earnings = referral_data.get(user_id, {}).get('earnings', 0)
    
    # Создаем реферальную ссылку
    referral_link = f"https://t.me/quants_shop_bot?start=ref{user_id}"
    
    referral_text = (
        "👥 Реферальная система\n\n"
        "Приводи друзей и получай бонусы!\n\n"
        "💰 За каждого приглашенного друга: 5% от его первой покупки\n\n"
        "📊 Твоя статистика:\n"
        f"🔹 Приглашено друзей: {referrals_count}\n"
        f"🔹 Заработано: ${earnings:.2f}\n\n"
        "🔗 Твоя реферальная ссылка:\n"
        f"`{referral_link}`\n\n"
        "📤 Просто поделись этой ссылкой с друзьями!\n"
        "💸 Когда они совершат первую покупку - ты получишь бонус!"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=f"https://t.me/share/url?url={referral_link}&text=Присоединяйся%20к%20QUANTS%20SHOP!%20💎")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await send_message_with_photo(
        callback_query,
        "referral.png",
        referral_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    await callback_query.answer()

# Обработка кнопки "FAQ"
@dp.callback_query(F.data == "faq")
async def faq_handler(callback_query: CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="📚 Перейти в FAQ", url="https://t.me/quantsfaq")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await send_message_with_photo(
        callback_query,
        "faq.png",
        "❓ Часто задаваемые вопросы собраны в нашем канале FAQ\n\n"
        "Переходи по кнопке ниже чтобы ознакомиться с ответами на популярные вопросы 👇",
        reply_markup=reply_markup
    )
    await callback_query.answer()

# Обработка кнопки "Удачные сделки"
@dp.callback_query(F.data == "successful_deals")
async def successful_deals_handler(callback_query: CallbackQuery):
    deals_text = (
        "🔍 Хочешь убедиться в нашей надежности?\n"
        "📢 Присоединяйся к нашему официальному каналу:\n"
        "👉 Отзывы & Анонсы (https://t.me/quantsreview)\n\n"
        "Здесь ты найдешь:\n"
        "✅ Реальные отзывы покупателей с пруфами\n"
        "✅ Акции и конкурсы с крутыми призами\n"
        "✅ Свежие анонсы обновлений и спецпредложений\n\n"
        "Подпишись сейчас – не упусти выгоду! 🎁\n\n"
        "P.S. Все честно – мы ценим твое доверие! 😊"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="📢 Канал", url="https://t.me/quantsreview")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await send_message_with_photo(
        callback_query,
        "deals.png",
        deals_text,
        reply_markup=reply_markup
    )
    await callback_query.answer()

# Обработка кнопки "Заработать"
@dp.callback_query(F.data == "earn_money")
async def earn_money_handler(callback_query: CallbackQuery):
    earn_text = (
        "💼 Хочешь заработать с нами?\n\n"
        "Мы предлагаем различные способы сотрудничества:\n\n"
        "👥 Реферальная программа - получай 5% с покупок друзей\n"
        "🤝 Партнерство - выгодные условия для постоянных клиентов\n"
        "📈 Оптовые закупки - специальные цены при больших объемах\n\n"
        "💬 Для обсуждения условий сотрудничества пиши: @f3ckm0ney"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton(text="💬 Написать менеджеру", url="https://t.me/f3ckm0ney")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await send_message_with_photo(
        callback_query,
        "referral.png",
        earn_text,
        reply_markup=reply_markup
    )
    await callback_query.answer()

# Возврат в главное меню
@dp.callback_query(F.data == "back_to_start")
async def back_to_start(callback_query: CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="🛒 Купить аккаунты", callback_data="buy_accounts")],
        [
            InlineKeyboardButton(text="🛎️ Поддержка", callback_data="support"),
            InlineKeyboardButton(text="❓ FAQ", callback_data="faq")
        ],
        [InlineKeyboardButton(text="🎯 Удачные сделки", callback_data="successful_deals")],
        [InlineKeyboardButton(text="👥 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton(text="💼 Заработать", callback_data="earn_money")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    caption_text = (
        "Добро пожаловать в QUANTS SHOP ✨\n\n"
        "Давно хотел приобрести качественные Revolut аккаунты с балансом? Тебе определенно к нам! ⭐️\n\n"
        "Ниже располагается меню, ознакамливайся 🎲"
    )
    
    await send_message_with_photo(
        callback_query,
        "main.png",
        caption_text,
        reply_markup=reply_markup
    )
    await callback_query.answer()

# Обработка кнопки "Купить аккаунты"
@dp.callback_query(F.data == "buy_accounts")
async def show_buy_options(callback_query: CallbackQuery):
    keyboard = [
        [InlineKeyboardButton(text="💎 Lite pack - 1 аккаунт", callback_data="lite_pack")],
        [InlineKeyboardButton(text="✨ Starter pack - 3 аккаунта", callback_data="starter_pack")],
        [InlineKeyboardButton(text="🚀 Smart pack - 5 аккаунтов", callback_data="smart_pack")],
        [InlineKeyboardButton(text="🔥 Pro Pack - 10 аккаунтов", callback_data="pro_pack")],
        [InlineKeyboardButton(text="💫 Premium Pack - 20 аккаунтов", callback_data="premium_pack")],
        [InlineKeyboardButton(text="🎯 Ultimate Pack - 30 аккаунтов", callback_data="ultimate_pack")],
        [InlineKeyboardButton(text="🔢 Выбрать свое количество", callback_data="custom_amount")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_start")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    text = (
        "Шаг 1 из 3... Выбор количества для покупки\n\n"
        "Решил купить аккаунты? Ты на верном пути! ✈️\n"
        "Наши преимущества перед другими сервисами: \n\n"
        "- Мы гарантируем возврат в случаи невалидности 🔮\n"
        "- Готовы предоставить платежные системы высшего уровня 💾\n"
        "- Удобные способы оплаты 📥\n"
        "- Быстрая тех поддержка, готовая вам помочь в любой момент 📞\n\n"
        "Кхм, перейдем к количеству \n"
        "Вот прайс лист на аккаунты💎\n\n"
        "💰 Цена за 1 аккаунт: 10$\n\n"
        "📦 Готовые пакеты:\n"
        "• 1 аккаунт - 10$\n"
        "• 3 аккаунта - 30$\n"
        "• 5 аккаунтов - 50$\n"
        "• 10 аккаунтов - 100$\n"
        "• 20 аккаунтов - 200$\n"
        "• 30 аккаунтов - 300$\n\n"
        "Выбери готовый пакет или укажи свое количество"
    )
    
    await send_message_with_photo(
        callback_query,
        "packs.png",
        text,
        reply_markup=reply_markup
    )
    await callback_query.answer()

# Обработка выбора пака
@dp.callback_query(F.data.in_(["lite_pack", "starter_pack", "smart_pack", "pro_pack", "premium_pack", "ultimate_pack", "custom_amount"]))
async def process_pack_selection(callback_query: CallbackQuery, state: FSMContext):
    pack_info = {
        "lite_pack": {"count": 1, "price": 10},
        "starter_pack": {"count": 3, "price": 30},
        "smart_pack": {"count": 5, "price": 50},
        "pro_pack": {"count": 10, "price": 100},
        "premium_pack": {"count": 20, "price": 200},
        "ultimate_pack": {"count": 30, "price": 300}
    }
    
    if callback_query.data == "custom_amount":
        # Обработка выбора своего количества
        await handle_custom_amount(callback_query, state)
        return
    
    pack_data = pack_info[callback_query.data]
    deal_number = random.randint(1000, 9999)
    
    # Сохраняем заказ в сессии пользователя
    user_id = callback_query.from_user.id
    user_sessions[user_id] = {
        'order': {
            'count': pack_data['count'],
            'price': pack_data['price'],
            'deal_number': deal_number,
            'user_id': user_id
        }
    }
    
    keyboard = [
        [InlineKeyboardButton(text="💳 Оплата CryptoBot", callback_data="cryptobot_payment")],
        [InlineKeyboardButton(text="₿ Оплата на криптокошелек", callback_data="crypto_wallet_payment")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_packs")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await send_message_with_photo(
        callback_query,
        "step2.png",
        f"Шаг 2 из 3... Оплата товара\n\n"
        f"Ты почти у цели вот твой заказ, все ли верно? ✅\n"
        f"🔹 Товар: Revolut Accounts \n"
        f"🔹 Количество: {pack_data['count']} штук\n"
        f"🔹 Сумма заказа: {pack_data['price']}$ \n"
        f"🔹 Номер сделки: {deal_number} \n\n"
        f"Почти все готово, осталось оплатить заказ, выбери ниже способ пополнения ✔️",
        reply_markup=reply_markup
    )
    await callback_query.answer()

@dp.callback_query(F.data == "back_to_packs")
async def back_to_packs(callback_query: CallbackQuery):
    await show_buy_options(callback_query)

# Обработка оплаты через CryptoBot
@dp.callback_query(F.data == "cryptobot_payment")
async def process_cryptobot_payment(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    session_data = user_sessions.get(user_id, {})
    order = session_data.get('order', {})
    
    if not order:
        await callback_query.message.edit_text("❌ Ошибка: данные заказа не найдены")
        await callback_query.answer()
        return
    
    # Создание инвойса в CryptoBot
    invoice = create_cryptobot_invoice(order.get('price', 0))
    
    if not invoice:
        await callback_query.message.edit_text(
            "❌ Ошибка при создании платежа. Попробуйте позже."
        )
        await callback_query.answer()
        return
    
    # Сохраняем информацию об инвойсе
    invoice_id = invoice['invoice_id']
    active_invoices[invoice_id] = {
        'user_id': user_id,
        'order': order,
        'chat_id': callback_query.message.chat.id
    }
    
    # Обновляем сессию пользователя
    user_sessions[user_id]['invoice_id'] = invoice_id
    
    payment_url = invoice['pay_url']
    keyboard = [
        [InlineKeyboardButton(text="✅ Оплатить", url=payment_url)],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{invoice_id}")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_packs")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await send_message_with_photo(
        callback_query,
        "payment.png",
        f"💳 Оплата через CryptoBot\n\n"
        f"🔹 Сумма к оплате: {order.get('price', 0)} USDT\n"
        f"🔹 Номер сделки: {order.get('deal_number', 'N/A')}\n\n"
        f"Для оплаты нажмите кнопку 'Оплатить' ниже 👇\n"
        f"После оплаты нажмите 'Проверить оплату'\n\n"
        f"⏰ Счет действителен в течение 1 часа",
        reply_markup=reply_markup
    )
    await callback_query.answer()

# Обработка оплаты на криптокошелек
@dp.callback_query(F.data == "crypto_wallet_payment")
async def process_crypto_wallet_payment(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    session_data = user_sessions.get(user_id, {})
    order = session_data.get('order', {})
    
    if not order:
        await callback_query.message.edit_text("❌ Ошибка: данные заказа не найдены")
        await callback_query.answer()
        return
    
    # Генерируем ID платежа
    payment_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    wallet_address = "TB8r7stxCuoReuSTqyDrHxfCsqBixg7uvM"
    
    payment_text = (
        f"₿ Оплата на криптокошелек\n\n"
        f"🔹 Сумма к оплате: {order.get('price', 0)} USDT\n"
        f"🔹 Номер сделки: {order.get('deal_number', 'N/A')}\n"
        f"🔹 ID платежа: {payment_id}\n\n"
        f"💳 Адрес кошелька:\n"
        f"`{wallet_address}`\n\n"
        f"📝 Сеть: TRC20 (Tron)\n\n"
        f"После оплаты отправьте скриншот транзакции в этот чат.\n"
        f"Ожидание подтверждения: до 15 минут"
    )
    
    keyboard = [
        [InlineKeyboardButton(text="📸 Отправить скриншот", callback_data=f"send_screenshot_{payment_id}")],
        [InlineKeyboardButton(text="↩️ Вернуться назад", callback_data="back_to_packs")]
    ]
    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await send_message_with_photo(
        callback_query,
        "crypto_wallet.png",
        payment_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    # Сохраняем данные платежа в сессии пользователя
    user_sessions[user_id]['current_payment_id'] = payment_id
    
    await callback_query.answer()

# Обработка кнопки отправки скриншота
@dp.callback_query(F.data.startswith("send_screenshot_"))
async def send_screenshot_handler(callback_query: CallbackQuery, state: FSMContext):
    payment_id = callback_query.data.replace("send_screenshot_", "")
    
    # Сохраняем payment_id в сессии пользователя
    user_id = callback_query.from_user.id
    user_sessions[user_id]['current_payment_id'] = payment_id
    
    # Устанавливаем состояние ожидания скриншота
    await state.set_state(CryptoPaymentStates.waiting_for_screenshot)
    
    instruction_text = (
        "📸 Отправка скриншота\n\n"
        "Пожалуйста, отправьте скриншот подтверждения транзакции.\n\n"
        "📌 Требования к скриншоту:\n"
        "• Должен быть виден хэш транзакции\n"
        "• Должна быть видна сумма перевода\n"
        "• Должен быть виден адрес получателя\n\n"
        "После отправки скриншота ожидайте подтверждения оплаты."
    )
    
    try:
        await callback_query.message.delete()
    except:
        pass
    
    await callback_query.message.answer(instruction_text)
    await callback_query.answer()

# Обработка получения скриншота
@dp.message(CryptoPaymentStates.waiting_for_screenshot, F.photo)
async def handle_screenshot(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    session_data = user_sessions.get(user_id, {})
    payment_id = session_data.get('current_payment_id')
    order = session_data.get('order', {})
    
    if not payment_id or not order:
        await message.answer("❌ Ошибка: данные платежа не найдены")
        await state.clear()
        return
    
    # Сохраняем данные платежа в файл
    payment_data = {
        'user_id': user_id,
        'order': order,
        'status': 'waiting',
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    update_crypto_payment(payment_id, payment_data)
    
    # Отправляем подтверждение пользователю
    await message.answer(
        "✅ Скриншот успешно получен!\n\n"
        "Ожидайте подтверждения оплаты администратором.\n"
        "Обычно это занимает до 15 минут.\n\n"
        "📞 Если возникли вопросы: @f3ckm0ney"
    )
    
    # Отправляем уведомление в логгер-бот
    user_info = f"@{message.from_user.username}" if message.from_user.username else f"ID: {user_id}"
    
    log_message = (
        f"🔄 Новая оплата на криптокошелек\n\n"
        f"👤 Пользователь: {user_info}\n"
        f"💳 ID платежа: {payment_id}\n"
        f"📦 Заказ: {order['count']} аккаунтов\n"
        f"💰 Сумма: ${order['price']}\n"
        f"🔢 Номер сделки: #{order['deal_number']}\n"
        f"⏰ Время: {datetime.datetime.now().strftime('%H:%M:%S')}"
    )
    
    # Отправляем скриншот и информацию в логгер-бот
    try:
        # Получаем файл фото
        photo_file = await bot.get_file(message.photo[-1].file_id)
        photo_bytes = await bot.download_file(photo_file.file_path)
        
        # Отправляем в логгер-бот
        keyboard = [
            [
                InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_crypto_{payment_id}"),
                InlineKeyboardButton(text="❌ Отклонить оплату", callback_data=f"reject_crypto_{payment_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await logger_bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=types.BufferedInputFile(photo_bytes.read(), filename="screenshot.jpg"),
            caption=log_message,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error sending screenshot to logger: {e}")
        # Если не удалось отправить фото, отправляем текстовое уведомление с кнопками
        keyboard = [
            [
                InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"confirm_crypto_{payment_id}"),
                InlineKeyboardButton(text="❌ Отклонить оплату", callback_data=f"reject_crypto_{payment_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await logger_bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=f"{log_message}\n\n❌ Не удалось загрузить скриншот",
            reply_markup=reply_markup
        )
    
    # Очищаем состояние
    await state.clear()

# Проверка статуса платежа
@dp.callback_query(F.data.startswith("check_payment_"))
async def check_payment_status(callback_query: CallbackQuery):
    invoice_id = callback_query.data.replace("check_payment_", "")
    
    # Проверяем наличие инвойса
    if invoice_id not in active_invoices:
        # Пытаемся найти через сессию пользователя
        user_id = callback_query.from_user.id
        session_data = user_sessions.get(user_id, {})
        if session_data.get('invoice_id') == invoice_id:
            # Инвойс есть в сессии, но не в активных (уже обработан)
            await callback_query.answer("Платеж уже обработан, проверьте свои сообщения")
            return
        else:
            await callback_query.message.edit_text(
                "❌ Ошибка: заказ не найден. Возможно, время оплаты истекло. Попробуйте создать новый заказ."
            )
            await callback_query.answer()
            return
    
    status, asset, amount = check_invoice_status(invoice_id)
    
    if status == "paid":
        # Обрабатываем успешный платеж
        order_info = active_invoices[invoice_id]
        await process_successful_payment(
            order_info['user_id'], 
            order_info['order'], 
            invoice_id,
            "CryptoBot"
        )
        # Удаляем сообщение с кнопками оплаты
        try:
            await callback_query.message.delete()
        except:
            pass
    elif status == "active":
        keyboard = [
            [InlineKeyboardButton(text="🔄 Проверить снова", callback_data=f"check_payment_{invoice_id}")],
            [InlineKeyboardButton(text="↩️ Вернуться в меню", callback_data="back_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
        await callback_query.message.edit_text(
            "⏳ Платеж еще не получен\n\n"
            "Если вы уже оплатили, подождите несколько минут и проверьте снова",
            reply_markup=reply_markup
        )
    else:
        await callback_query.message.edit_text(
            "❌ Платеж не найден или отменен\n\n"
            "Попробуйте создать новый заказ"
        )
    await callback_query.answer()

# Фоновая проверка платежей
async def payment_monitor():
    while True:
        await asyncio.sleep(30)
        invoices_to_remove = []
        
        for invoice_id, order_info in list(active_invoices.items()):
            status, asset, amount = check_invoice_status(invoice_id)
            
            if status == "paid":
                try:
                    await process_successful_payment(
                        order_info['user_id'],
                        order_info['order'],
                        invoice_id,
                        "CryptoBot"
                    )
                    invoices_to_remove.append(invoice_id)
                except Exception as e:
                    logger.error(f"Failed to process payment: {e}")
            
            elif status in ["expired", "cancelled"]:
                invoices_to_remove.append(invoice_id)
        
        for invoice_id in invoices_to_remove:
            if invoice_id in active_invoices:
                del active_invoices[invoice_id]

# Запуск бота
# async def main():
#     # Запуск фонового монитора
#     asyncio.create_task(payment_monitor())
#     logger.info("Бот запущен...")
#     await dp.start_polling(bot)

# if __name__ == '__main__':
#     asyncio.run(main())

async def main():
    """Главная асинхронная функция для запуска из main.py"""
    # Запуск фонового монитора
    asyncio.create_task(payment_monitor())
    logger.info("🛒 Бот магазина запущен...")
    await dp.start_polling(bot)

# Для обратной совместимости оставь:
if __name__ == '__main__':
    asyncio.run(main())