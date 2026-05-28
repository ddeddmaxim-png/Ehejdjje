import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from aiocryptopay import CryptoPay, Networks

# --- НАСТРОЙКИ ---
BOT_TOKEN = "ВАШ_ТЕЛЕГРАМ_ТОКЕН"
CRYPTO_BOT_TOKEN = "ВАШ_КРИПТОБОТ_ТОКЕН"

# Используйте Networks.MAIN_NET для реальных денег или Networks.TEST_NET для тестов
crypto = CryptoPay(token=CRYPTO_BOT_TOKEN, network=Networks.TEST_NET)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# Данные о тарифах (Цена в Stars и в USD для CryptoBot)
TARIFFS = {
    "sub_1month": {"name": "Премиум 1 месяц", "stars": 50, "usd": 1.5},
    "sub_3month": {"name": "Премиум 3 месяца", "stars": 120, "usd": 3.5}
}

# --- КЛАВИАТУРЫ ---
def get_main_keyboard():
    buttons = [
        [types.KeyboardButton(text="💎 Купить тариф")],
        [types.KeyboardButton(text="👨‍💻 Тех. поддержка"), types.KeyboardButton(text="⭐ Отзывы")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_tariffs_keyboard():
    buttons = [
        [types.InlineKeyboardButton(text="📦 1 месяц — 50 ⭐️ / 1.5$", callback_data="buy_sub_1month")],
        [types.InlineKeyboardButton(text="📦 3 месяца — 120 ⭐️ / 3.5$", callback_data="buy_sub_3month")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

def get_payment_method_keyboard(tariff_id: str):
    buttons = [
        [types.InlineKeyboardButton(text="⭐️ Оплатить Звездами (Telegram Stars)", callback_data=f"pay_stars_{tariff_id}")],
        [types.InlineKeyboardButton(text="⚡ Оплатить через CryptoBot", callback_data=f"pay_crypto_{tariff_id}")],
        [types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tariffs")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! Добро пожаловать в наш бот. Выберите интересующий раздел ниже:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "💎 Купить тариф")
async def show_tariffs(message: Message):
    await message.answer("Выберите подходящий тарифный план:", reply_markup=get_tariffs_keyboard())

@dp.message(F.text == "👨‍💻 Тех. поддержка")
async def support_info(message: Message):
    await message.answer("📌 По всем вопросам и предложениям пишите нашему менеджеру: @ваша_поддержка")

@dp.message(F.text == "⭐ Отзывы")
async def reviews_info(message: Message):
    await message.answer("💬 Почитать отзывы наших клиентов или оставить свой можно в канале: @ваш_канал_отзывов")

# Выбор способа оплаты
@dp.callback_query(F.data.startswith("buy_"))
async def select_payment_method(callback: types.CallbackQuery):
    tariff_id = callback.data.split("_")[2]
    tariff = TARIFFS.get(tariff_id)
    await callback.message.edit_text(
        f"Вы выбрали: *{tariff['name']}*.\nВыберите удобный способ оплаты:",
        parse_mode="Markdown",
        reply_markup=get_payment_method_keyboard(tariff_id)
    )

@dp.callback_query(F.data == "back_to_tariffs")
async def back_tariffs(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите подходящий тарифный план:", reply_markup=get_tariffs_keyboard())

# --- ОПЛАТА: TELEGRAM STARS ---
@dp.callback_query(F.data.startswith("pay_stars_"))
async def process_stars_payment(callback: types.CallbackQuery):
    tariff_id = callback.data.split("_")[2]
    tariff = TARIFFS.get(tariff_id)
    
    # Создаем инвойс для Telegram Stars. Валюта обязательно "XTR", провайдер-токен пустой.
    prices = [LabeledPrice(label="XTR", amount=tariff["stars"])]
    
    await callback.message.answer_invoice(
        title=tariff["name"],
        description=f"Активация подписки на {tariff['name']}",
        prices=prices,
        provider_token="",
        currency="XTR",
        payload=f"stars_{tariff_id}",
        start_parameter="pay"
    )
    await callback.answer()

# Обязательное подтверждение до списания Stars
@dp.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Успешная оплата Stars
@dp.message(F.successful_payment)
async def success_stars_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    tariff_id = payload.split("_")[1]
    # Здесь логика выдачи тарифа в БД
    await message.answer(f"🎉 Спасибо за оплату Звездами! Ваш тариф '{TARIFFS[tariff_id]['name']}' успешно активирован!")

# --- ОПЛАТА: CRYPTOBOT ---
@dp.callback_query(F.data.startswith("pay_crypto_"))
async def process_crypto_payment(callback: types.CallbackQuery):
    tariff_id = callback.data.split("_")[2]
    tariff = TARIFFS.get(tariff_id)
    
    # Создаем инвойс в CryptoBot в эквиваленте USD (клиент сможет выбрать USDT, TON, BTC и др.)
    invoice = await crypto.create_invoice(
        asset="USDT", 
        amount=str(tariff["usd"]),
        description=f"Оплата {tariff['name']}",
        payload=f"crypto_{tariff_id}_{callback.from_user.id}"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="💸 Перейти к оплате", url=invoice.bot_invoice_url)],
        [types.InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_{invoice.invoice_id}")]
    ])
    
    await callback.message.answer(
        f"Ссылка для оплаты через CryptoBot создана!\nСумма: **{tariff['usd']}$**",
        parse_mode="Markdown",
        reply_markup=kb
    )
    await callback.answer()

# Ручная проверка оплаты CryptoBot
@dp.callback_query(F.data.startswith("check_"))
async def check_crypto_payment(callback: types.CallbackQuery):
    invoice_id = int(callback.data.split("_")[1])
    invoices = await crypto.get_invoices(invoice_ids=invoice_id)
    
    if invoices and invoices.status == "paid":
        tariff_id = invoices.payload.split("_")[1]
        await callback.message.edit_text(f"🎉 Оплата подтверждена! Ваш тариф '{TARIFFS[tariff_id]['name']}' успешно активирован через CryptoBot!")
    else:
        await callback.answer("❌ Оплата еще не поступила. Попробуйте позже.", show_alert=True)

# --- ЗАПУСК ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
