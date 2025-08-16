# main.py
import os
import random
from aiogram import Bot, Dispatcher
from aiohttp import web
import hashlib

# === Настройки из переменных среды ===
TOKEN = os.getenv("BOT_TOKEN")
FREEKASSA_SHOP_ID = os.getenv("FREEKASSA_SHOP_ID")
FREEKASSA_SECRET = os.getenv("FREEKASSA_SECRET")

# Проверка, что все переменные заданы
if not all([TOKEN, FREEKASSA_SHOP_ID, FREEKASSA_SECRET]):
    raise Exception("Не хватает переменных окружения")

# === Бот ===
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Храним оплативших (для продакшена — используй JSON или базу)
paid_users = set()

# === Обработчики команд ===
@dp.message()
async def handle_message(message):
    user_id = message.from_user.id

    if message.text == "/start":
        await message.answer("Привет! Нажми /pay, чтобы оплатить 10₽ и получить случайное число от 1 до 10.")

    elif message.text == "/pay":
        amount = 10
        sign = hashlib.md5(f"{FREEKASSA_SHOP_ID}:{amount}:{FREEKASSA_SECRET}:{user_id}".encode()).hexdigest()
        pay_url = (
            f"https://free-kassa.ru/merchant/cash.php?"
            f"m={FREEKASSA_SHOP_ID}&oa={amount}&o={user_id}&s={sign}"
        )
        await message.answer(f"[Оплатить 10₽]({pay_url})", parse_mode="Markdown")

    elif message.text == "/random":
        if user_id in paid_users:
            number = random.randint(1, 10)
            await message.answer(f"🎲 Ваше число: <b>{number}</b>", parse_mode="HTML")
        else:
            await message.answer("Сначала оплатите: /pay")

# === Обработка оплаты от Free-Kassa ===
async def freekassa_handler(request):
    data = await request.post()
    print("FreeKassa data:", dict(data))  # Логируем входящие данные
    try:
        merchant_id = data.get('MERCHANT_ID')
        amount = data.get('AMOUNT')
        order_id = data.get('MERCHANT_ORDER_ID')
        sign = data.get('SIGN')
        print(f"Received: merchant_id={merchant_id}, amount={amount}, order_id={order_id}, sign={sign}")
        check_sign = hashlib.md5(f"{merchant_id}:{amount}:{FREEKASSA_SECRET}:{order_id}".encode()).hexdigest()
        print(f"Generated sign: {check_sign}")
        if sign.lower() == check_sign.lower():
            user_id = int(order_id)
            paid_users.add(user_id)
            await bot.send_message(user_id, "✅ Оплата прошла! Теперь /random")
            return web.Response(text="OK")
        else:
            print("Signature mismatch")
            return web.Response(text="SIGN ERROR", status=400)
    except Exception as e:
        print(f"Error in freekassa_handler: {str(e)}")
        return web.Response(text=f"ERROR: {str(e)}", status=500)

# === Веб-сервер ===
async def on_startup(app):
    print("Бот запущен")

app = web.Application()
app.on_startup.append(on_startup)
app.router.add_post('/freekassa', freekassa_handler)

# Запуск
if __name__ == "__main__":
    from aiogram import Dispatcher
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    # Настройка вебхука
    webhook_path = '/webhook'
    app.router.add_post(webhook_path, SimpleRequestHandler(dispatcher=dp, bot=bot).handle)

    setup_application(app, dp, bot=bot)

    # Запуск сервера
    web.run_app(app, host='0.0.0.0', port=int(os.getenv('PORT', 8080)))
