import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import ClientSession

# Настройка логов
logging.basicConfig(level=logging.INFO)

# Загрузка конфигов из переменных окружения
TOKEN = os.getenv("BOT_TOKEN")
CRYPTO_TOKEN = os.getenv("CRYPTO_PAY_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Цены и тарифы
PLANS = {
    "standard": {"name": "Standard Plan", "stars": 50, "usd": 5, "desc": "Basic features for 30 days"},
    "premium": {"name": "Premium Plan", "stars": 150, "usd": 15, "desc": "All features + Priority support"}
}

# --- CRYPTO BOT API HELPER ---
async def create_crypto_invoice(amount, plan_name):
    headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": str(amount),
        "description": f"Payment for {plan_name}",
        "paid_btn_name": "callback",
        "paid_btn_url": "https://t.me/your_bot_username"
    }
    async with ClientSession() as session:
        async with session.post("https://pay.cryptobot.net/api/createInvoice", json=payload, headers=headers) as resp:
            data = await resp.json()
            return data['result']['pay_url'] if data.get('ok') else None

# --- HANDLERS ---
@dp.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Standard - 50 Stars / $5", callback_data="buy_standard")],
        [InlineKeyboardButton(text="💎 Premium - 150 Stars / $15", callback_data="buy_premium")]
    ])
    await message.answer(
        "👋 **Welcome!**\nChoose a subscription plan to get started. We accept Telegram Stars and Crypto.",
        reply_markup=kb, parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("buy_"))
async def choose_method(callback: types.CallbackQuery):
    plan_id = callback.data.split("_")[1]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 Pay with Stars", callback_data=f"pay_stars_{plan_id}")],
        [InlineKeyboardButton(text="⚡ Pay with Crypto Bot", callback_data=f"pay_crypto_{plan_id}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="back")]
    ])
    await callback.message.edit_text(f"How would you like to pay for {PLANS[plan_id]['name']}?", reply_markup=kb)

# Оплата Звездами
@dp.callback_query(F.data.startswith("pay_stars_"))
async def stars_invoice(callback: types.CallbackQuery):
    plan = PLANS[callback.data.split("_")[2]]
    await callback.message.answer_invoice(
        title=plan['name'],
        description=plan['desc'],
        prices=[LabeledPrice(label=plan['name'], amount=plan['stars'])],
        payload=f"stars_{plan['name']}",
        currency="XTR",
        provider_token="" # Пусто для Stars
    )

# Оплата Crypto Bot
@dp.callback_query(F.data.startswith("pay_crypto_"))
async def crypto_invoice(callback: types.CallbackQuery):
    plan_id = callback.data.split("_")[2]
    plan = PLANS[plan_id]
    url = await create_crypto_invoice(plan['usd'], plan['name'])
    
    if url:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Pay USDT", url=url)]])
        await callback.message.answer(f"Click the button to pay ${plan['usd']} via @CryptoBot", reply_markup=kb)
    else:
        await callback.message.answer("Error creating invoice. Try Stars or contact admin.")

@dp.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: types.Message):
    await message.answer("🎉 Payment successful! Your plan is now active.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())