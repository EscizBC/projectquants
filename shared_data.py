import json
import os

CRYPTO_PAYMENTS_FILE = "crypto_payments.json"

def load_crypto_payments():
    """Загрузить крипто-платежи из файла"""
    if os.path.exists(CRYPTO_PAYMENTS_FILE):
        try:
            with open(CRYPTO_PAYMENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_crypto_payments(payments):
    """Сохранить крипто-платежи в файл"""
    with open(CRYPTO_PAYMENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(payments, f, ensure_ascii=False, indent=2)

def get_crypto_payment(payment_id):
    """Получить данные крипто-платежа"""
    payments = load_crypto_payments()
    return payments.get(payment_id)

def update_crypto_payment(payment_id, payment_data):
    """Обновить или создать крипто-платеж"""
    payments = load_crypto_payments()
    payments[payment_id] = payment_data
    save_crypto_payments(payments)

def delete_crypto_payment(payment_id):
    """Удалить крипто-платеж"""
    payments = load_crypto_payments()
    if payment_id in payments:
        del payments[payment_id]
        save_crypto_payments(payments)
        return True
    return False

def update_crypto_payment_status(payment_id, status):
    """Обновить статус крипто-платежа"""
    payments = load_crypto_payments()
    if payment_id in payments:
        payments[payment_id]['status'] = status
        save_crypto_payments(payments)
        return True
    return False