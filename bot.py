import asyncio
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN
from database import add_review, get_reviews_by_company, init_db, get_average_rating
from moderation import send_review_for_moderation, approve_review, decline_review

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Хранилище для временных данных пользователя (например, для отзывов и страниц)
user_data = {}

# Клавиатура для выбора языка
language_markup = ReplyKeyboardMarkup(resize_keyboard=True)
language_markup.add(KeyboardButton("Українська"), KeyboardButton("Русский"), KeyboardButton("Polski"))

# Стартовая команда /start
@dp.message_handler(commands=['start'])
async def start_command_handler(message: types.Message):
    await message.answer("Выберите язык:", reply_markup=language_markup)

# Обработчик выбора языка
@dp.message_handler(lambda message: message.text in ["Українська", "Русский", "Polski"])
async def language_selection_handler(message: types.Message):
    language = message.text
    # Сохранение выбранного языка и отправка следующего меню
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Оставить отзыв"), KeyboardButton("Найти отзывы"))
    await message.answer(f"Вы выбрали {language}. Теперь выберите действие:", reply_markup=markup)

# Обработчик кнопки "Оставить отзыв"
@dp.message_handler(lambda message: message.text == "Оставить отзыв")
async def leave_review_handler(message: types.Message):
    # Начало нового процесса для "Оставить отзыв"
    await message.answer("Введите название работодателя (только латинскими буквами):")
    user_data[message.from_user.id] = {"step": "leave_review"}  # Устанавливаем шаг для оставления отзыва

# Обработчик пользовательского ввода для отзывов
@dp.message_handler(lambda message: message.from_user.id in user_data and user_data[message.from_user.id]["step"] == "leave_review")
async def process_review_data(message: types.Message):
    user_id = message.from_user.id
    step = user_data[user_id].get("step")

    if "company_name" not in user_data[user_id]:  # Вводим название компании
        company_name = message.text.strip().lower()
        if not company_name.isalpha():
            await message.answer("Название работодателя должно содержать только латинские буквы. Попробуйте снова.")
            return
        user_data[user_id]["company_name"] = company_name
        await message.answer("Введите оценку от 1 до 5:")
    elif "rating" not in user_data[user_id]:  # Вводим рейтинг
        try:
            rating = int(message.text)
            if rating < 1 or rating > 5:
                await message.answer("Оценка должна быть от 1 до 5. Попробуйте снова.")
                return
        except ValueError:
            await message.answer("Оценка должна быть числом от 1 до 5. Попробуйте снова.")
            return
        user_data[user_id]["rating"] = rating
        await message.answer("Введите комментарий о работодателе:")
    elif "comment" not in user_data[user_id]:  # Вводим комментарий
        comment = message.text
        user_data[user_id]["comment"] = comment

        company_name = user_data[user_id]["company_name"]
        rating = user_data[user_id]["rating"]
        comment = user_data[user_id]["comment"]
        username = message.from_user.username
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Сохраняем отзыв в базу данных с пометкой "не подтвержден" и получаем review_id
        review_id = await add_review(user_id, username, company_name, rating, comment, date)

        # Отправляем отзыв на модерацию
        await send_review_for_moderation(bot, review_id, username, company_name, rating, comment, date)

        await message.answer("Ваш отзыв отправлен на модерацию. Спасибо!")
        # Завершение процесса: очищаем временные данные
        del user_data[user_id]

# Обработчик кнопки "Найти отзывы"
@dp.message_handler(lambda message: message.text == "Найти отзывы")
async def find_reviews_handler(message: types.Message):
    # Начало нового процесса для "Найти отзывы"
    await message.answer("Введите название работодателя (игнорируется регистр):")
    user_data[message.from_user.id] = {"step": "search"}  # Устанавливаем шаг для поиска отзывов

# Поиск отзывов по названию компании с постраничным выводом
@dp.message_handler(lambda message: message.from_user.id in user_data and user_data[message.from_user.id]["step"] == "search")
async def search_reviews(message: types.Message):
    company_name = message.text.strip().lower()  # Обработка названия компании
    user_id = message.from_user.id

    # Проверка: вызывается ли функция поиска
    await message.answer(f"Запуск поиска для компании: {company_name}")

    # Получаем отзывы и общий рейтинг компании
    reviews = await get_reviews_by_company(company_name)
    avg_rating = await get_average_rating(company_name)

    # Проверка результатов
    await message.answer(f"Найдено {len(reviews)} отзывов для компании {company_name}")

    if not reviews:
        await message.answer("Отзывы по данному работодателю не найдены.")
        return

    # Сохраняем отзывы и начальную страницу для пользователя
    user_data[user_id]["reviews"] = reviews
    user_data[user_id]["page"] = 0
    user_data[user_id]["company_name"] = company_name
    user_data[user_id]["avg_rating"] = avg_rating

    # Отображаем первую страницу отзывов
    await show_reviews_page(message, user_id)

# Функция для отображения страницы отзывов с навигацией
async def show_reviews_page(message, user_id):
    page = user_data[user_id]["page"]
    reviews = user_data[user_id]["reviews"]
    company_name = user_data[user_id]["company_name"]
    avg_rating = user_data[user_id]["avg_rating"]

    # Рассчитываем диапазон для постраничного вывода
    items_per_page = 2
    start = page * items_per_page
    end = start + items_per_page
    reviews_on_page = reviews[start:end]

    # Формируем текст для отображения
    response = f"Отзывы о компании: {company_name.capitalize()}\nСредний рейтинг: {avg_rating:.2f}\n\n"
    for review in reviews_on_page:
        response += (
            f"Рейтинг: {review[1]}/5\n"  # Доступ по индексу для rating
            f"Комментарий: {review[2]}\n"  # Доступ по индексу для comment
            f"Дата: {review[3]}\n\n"  # Доступ по индексу для date
        )

    # Кнопки для навигации между страницами
    markup = InlineKeyboardMarkup()
    if page > 0:
        markup.add(InlineKeyboardButton("⬅️ Назад", callback_data="prev_page"))
    if end < len(reviews):
        markup.add(InlineKeyboardButton("Вперёд ➡️", callback_data="next_page"))

    await message.answer(response, reply_markup=markup)

# Обработчики для навигации по страницам
@dp.callback_query_handler(lambda c: c.data in ["prev_page", "next_page"])
async def navigate_reviews(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    if callback_query.data == "prev_page":
        user_data[user_id]["page"] -= 1
    elif callback_query.data == "next_page":
        user_data[user_id]["page"] += 1

    # Обновляем отображение отзывов на новой странице
    await show_reviews_page(callback_query.message, user_id)
    await callback_query.answer()

# Обработчик для одобрения отзыва
@dp.callback_query_handler(lambda c: c.data.startswith('approve_'))
async def process_approve(callback_query: types.CallbackQuery):
    review_id = callback_query.data.split('_')[1]
    message_id = callback_query.message.message_id  # Получаем ID сообщения из канала модерации
    user_id = callback_query.from_user.id  # ID пользователя, оставившего отзыв
    await approve_review(bot, review_id, user_id, message_id, callback_query)

# Обработчик для отклонения отзыва
@dp.callback_query_handler(lambda c: c.data.startswith('decline_'))
async def process_decline(callback_query: types.CallbackQuery):
    review_id = callback_query.data.split('_')[1]
    message_id = callback_query.message.message_id  # Получаем ID сообщения из канала модерации
    user_id = callback_query.from_user.id  # ID пользователя, оставившего отзыв
    await decline_review(bot, review_id, user_id, message_id, callback_query)

# Запуск бота
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    executor.start_polling(dp, skip_updates=True)