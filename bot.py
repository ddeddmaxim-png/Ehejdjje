import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiocryptopay import CryptoPay, Networks

# ================= НАСТРОЙКИ =================
BOT_TOKEN = "ТВОЙ_ТЕЛЕГРАМ_БОТ_ТОКЕН"
# Токен CryptoBot (получать в @CryptoBot -> Crypto Pay -> Create App)
CRYPTO_BOT_TOKEN = "ТВОЙ_КРИПТОБОТ_ТОКЕН" 
SUPPORT_LINK = "https://t.me/username_поддержки"
REVIEWS_LINK = "https://t.me/канал_с_отзывами"

# Цены тарифов (в USD для Криптобота и XTR для Звёзд)
TARIF_PRICE_USD = 5.0
TARIF_PRICE_STARS = 250  # 250 Звёзд (~$5)
# =============================================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
crypto = CryptoPay(token=CRYPTO_BOT_TOKEN, network=Networks.MAIN_NET) # Используйте TEST_NET для тестов

# --- КЛАВИАТУРЫ ---

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Купить тариф", callback_data="buy_tariff")
    builder.button(text="👨‍💻 Тех. поддержка", url=SUPPORT_LINK)
    builder.button(text="⭐ Отзывы", url=REVIEWS_LINK)
    builder.adjust(1, 2)
    return builder.as_markup()

def payment_method_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🌟 Оплатить Звездами (Telegram Stars)", callback_data="pay_stars")
    builder.button(text="⚡ Оплатить через CryptoBot", callback_data="pay_crypto")
    builder.button(text="⬅️ Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        "Добро пожаловать в наш бот. Выберите интересующий вас раздел ниже:",
        reply_markup=main_menu()
    )

@dp.callback_query(F.data == "main_menu")
async def go_to_main_menu(call: CallbackQuery):
    await call.message.edit_text("Главное меню:", reply_markup=main_menu())
    await call.answer()

@dp.callback_query(F.data == "buy_tariff")
async def select_payment_method(call: CallbackQuery):
    await call.message.edit_text(
        f"💳 **Выбор способа оплаты**\n\n"
        f"Стоимость тарифа: **{TARIF_PRICE_USD}$** или **{TARIF_PRICE_STARS} ⭐**\n"
        f"Выберите удобный способ оплаты:",
        reply_markup=payment_method_menu(),
        parse_mode="Markdown"
    )
    await call.answer()

# --- ОПЛАТА ЗВЕЗДАМИ (TELEGRAM STARS) ---

@dp.callback_query(F.data == "pay_stars")
async def process_stars_pay(call: CallbackQuery):
    await call.message.delete() # Удаляем старое сообщение, так как инвойс отправляется отдельным сообщением
    
    await call.message.answer_invoice(
        title="Premium Тариф",
        description="Доступ к платным функциям бота на 30 дней",
        payload="tariff_stars_payment",
        provider_token="", # Для Telegram Stars это поле ВСЕГДА пустое
        currency="XTR",   # Код валюты Telegram Stars
        prices=[LabeledPrice(label="Premium Тариф", amount=TARIF_PRICE_STARS)]
    )
    await call.answer()

# Обязательный шаг для Telegram: подтверждение, что товар готов к выдаче
@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# Хендлер успешной оплаты Звездами
@dp.message(F.successful_payment)
async def success_payment(message: Message):
    await message.answer(
        "🎉 **Оплата Звездами прошла успешно!**\n"
        "Ваш тариф активирован. Спасибо за покупку!",
        reply_markup=main_menu(),
        parse_mode="Markdown"
    )

# --- ОПЛАТА ЧЕРЕЗ CRYPTOBOT ---

@dp.callback_query(F.data == "pay_crypto")
async def process_crypto_pay(call: CallbackQuery):
    # Создаем счет в CryptoBot (в USD, система сама предложит пользователю криптовалюту по курсу)
    invoice = await crypto.create_invoice(
        asset="USDT", # Можно указать конкретную монету или фиат
        amount=TARIF_PRICE_USD,
        description="Оплата тарифа в боте"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Оплатить (CryptoBot)", url=invoice.bot_invoice_url)
    builder.button(text="✅ Проверить оплату", callback_data=f"check_crypto_{invoice.invoice_id}")
    builder.button(text="⬅️ Назад", callback_data="buy_tariff")
    builder.adjust(1)
    
    await call.message.edit_text(
        f"⚠️ **Счет за активирован!**\n\n"
        f"Сумма к оплате: `{TARIF_PRICE_USD}` USD\n"
        f"Нажмите кнопку ниже, чтобы перейти к оплате в CryptoBot. После оплаты обязательно нажмите «Проверить оплату».",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await call.answer()

@dp.callback_query(F.data.startswith("check_crypto_"))
async def check_crypto_payment(call: CallbackQuery):
    invoice_id = int(call.data.split("_")[2])
    
    # Получаем информацию о счете из CryptoBot
    invoices = await crypto.get_invoices(invoice_ids=invoice_id)
    
    if invoices and invoices.status == "paid":
        await call.message.edit_text(
            "🎉 **Оплата через CryptoBot получена!**\n"
            "Ваш тариф успешно активирован. Приятного пользования!",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )
    else:
        await call.answer("❌ Оплата еще не поступила. Попробуйте позже.", show_alert=True)

# --- ЗАПУСК БОТА ---
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
