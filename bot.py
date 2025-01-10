from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from config import TOKEN
from handlers import register_handlers

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Регистрация обработчиков
register_handlers(dp, bot)

if __name__ == "__main__":
    from database import init_db

    init_db()  # Создание таблиц в базе данных, если их нет
    executor.start_polling(dp, skip_updates=True)