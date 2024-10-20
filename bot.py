import asyncio
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN
from database import add_review, get_reviews_by_company, init_db, get_average_rating, get_user_id_by_review_id, get_language_by_review_id, update_review_status
from database_users import add_new_user, is_new_user, init_users_db
from moderation import send_review_for_moderation
import os

# Путь к файлу лицензионного соглашения в формате HTML
LICENSE_FILE_PATH = os.path.join(os.getcwd(), "license.html")

# Словарь с переводами для разных языков
translations = {
    "Українська": {
        "choose_language": "Виберіть мову:",
        "choose_action": "Ви вибрали {language}. Тепер виберіть дію:",
        "leave_review": "✍️ Залишити відгук",
        "find_reviews": "🔍 Знайти відгуки",
        "enter_company_name": "Введіть назву роботодавця (тільки латинськими літерами):",
        "enter_rating": "Введіть оцінку від 1 до 5:",
        "enter_comment": "Введіть коментар про роботодавця:",
        "review_submitted": "Ваш відгук надіслано на модерацію. Дякуємо!",
        "review_approved": "Ваш відгук був схвалений!",
        "enter_company_for_search": "Введіть назву роботодавця для пошуку:",
        "reviews_not_found": "Відгуки про цього роботодавця не знайдено.",
        "license_sent": "Ми надіслали вам файл з ліцензійним договором у форматі HTML."
    },
    "Русский": {
        "choose_language": "Выберите язык:",
        "choose_action": "Вы выбрали {language}. Теперь выберите действие:",
        "leave_review": "✍️ Оставить отзыв",
        "find_reviews": "🔍 Найти отзывы",
        "enter_company_name": "Введите название работодателя (только латинскими буквами):",
        "enter_rating": "Введите оценку от 1 до 5:",
        "enter_comment": "Введите комментарий о работодателе:",
        "review_submitted": "Ваш отзыв отправлен на модерацию. Спасибо!",
        "review_approved": "Ваш отзыв был одобрен!",
        "enter_company_for_search": "Введите название работодателя для поиска:",
        "reviews_not_found": "Отзывы по данному работодателю не найдены.",
        "license_sent": "Мы отправили вам файл с лицензионным соглашением в формате HTML."
    },
    "Polski": {
        "choose_language": "Wybierz język:",
        "choose_action": "Wybrałeś {language}. Teraz wybери działание:",
        "leave_review": "✍️ Zostaw recenzję",
        "find_reviews": "🔍 Znajdź recenzje",
        "enter_company_name": "Wprowadź nazwę pracodawcy (только litery łacińские):",
        "enter_rating": "Wprowadź ocenę od 1 do 5:",
        "enter_comment": "Wprowadź комментарий о работодателе:",
        "review_submitted": "Twoja recenzja została przesłана до модерации. Dzięкуем!",
        "review_approved": "Twoja recenzja została затверджена!",
        "enter_company_for_search": "Wprowadź nazwę pracodawcy do wyszukiwania:",
        "reviews_not_found": "Nie znaleziono recenzji tego pracodawcy.",
        "license_sent": "Wysłaliśmy Ci plik z umową licencyjną w formacie HTML."
    }
}

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# Хранилище для временных данных пользователя (например, для отзывов и страниц)
user_data = {}

# Клавиатура для выбора языка с эмодзи
language_markup = ReplyKeyboardMarkup(resize_keyboard=True)
language_markup.add(KeyboardButton("🇺🇦 Українська"), KeyboardButton("🇷🇺 Русский"), KeyboardButton("🇵🇱 Polski"))

# Стартовая команда /start
@dp.message_handler(commands=['start'])
async def start_command_handler(message: types.Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    date_joined = datetime.datetime.now().strftime("%Y-%м-%d %H:%М:%S")

    # Проверяем, является ли пользователь новым
    if await is_new_user(user_id):
        # Добавляем нового пользователя в базу данных users.db
        await add_new_user(user_id, first_name, date_joined)

        # Отправляем файл с лицензионным соглашением
        await send_license_file(message)

    await message.answer("Выберите язык:", reply_markup=language_markup)

# Отправка файла с лицензионным соглашением (HTML)
async def send_license_file(message: types.Message):
    language = user_data.get(message.from_user.id, {}).get("language", "Русский")  # Используем русский как язык по умолчанию
    translation = translations[language]
    
    # Отправляем HTML-файл лицензионного соглашения
    with open(LICENSE_FILE_PATH, 'rb') as license_file:
        await bot.send_document(message.from_user.id, license_file, caption=translation["license_sent"])

# Обработчик команды /license для получения файла лицензионного соглашения (HTML)
@dp.message_handler(commands=['license'])
async def license_command_handler(message: types.Message):
    await send_license_file(message)

# Обработчик выбора языка с учётом эмодзи
@dp.message_handler(lambda message: message.text in ["🇺🇦 Українська", "🇷🇺 Русский", "🇵🇱 Polski"])
async def language_selection_handler(message: types.Message):
    language = message.text.split(' ')[1]  # Получаем язык без эмодзи
    user_id = message.from_user.id

    # Сохраняем выбранный язык в словаре данных пользователя
    user_data[user_id] = {"language": language}

    # Используем перевод для сообщения
    translation = translations[language]
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton(translation["leave_review"]), KeyboardButton(translation["find_reviews"]))

    await message.answer(translation["choose_action"].format(language=language), reply_markup=markup)

# Обработчик кнопки "Оставить отзыв" с эмодзи
@dp.message_handler(lambda message: message.text in ["✍️ Оставить отзыв", "✍️ Залишити відгук", "✍️ Zostaw recenzję"])
async def leave_review_handler(message: types.Message):
    user_id = message.from_user.id
    language = user_data[user_id]["language"]
    translation = translations[language]
    
    await message.answer(translation["enter_company_name"])
    user_data[user_id]["step"] = "leave_review"  # Инициализируем step

# Обработчик пользовательского ввода для отзывов
@dp.message_handler(lambda message: message.from_user.id in user_data and "step" in user_data[message.from_user.id] and user_data[message.from_user.id]["step"] == "leave_review")
async def process_review_data(message: types.Message):
    user_id = message.from_user.id  # Это Telegram ID пользователя
    language = user_data[user_id]["language"]
    translation = translations[language]
    
    if "company_name" not in user_data[user_id]:  # Вводим название компании
        company_name = message.text.strip().lower()
        if not company_name.isalpha():
            await message.answer(translation["enter_company_name"])
            return
        user_data[user_id]["company_name"] = company_name
        await message.answer(translation["enter_rating"])
    elif "rating" not in user_data[user_id]:  # Вводим рейтинг
        try:
            rating = int(message.text)
            if rating < 1 or rating > 5:
                await message.answer(translation["enter_rating"])
                return
        except ValueError:
            await message.answer(translation["enter_rating"])
            return
        user_data[user_id]["rating"] = rating
        await message.answer(translation["enter_comment"])
    elif "comment" not in user_data[user_id]:  # Вводим комментарий
        comment = message.text
        user_data[user_id]["comment"] = comment

        company_name = user_data[user_id]["company_name"]
        rating = user_data[user_id]["rating"]
        comment = user_data[user_id]["comment"]
        username = message.from_user.username
        date = datetime.datetime.now().strftime("%Y-%м-%d %H:%М:%S")

        # Сохраняем отзыв в базу данных с пометкой "не подтвержден" и добавляем язык
        review_id = await add_review(user_id, username, company_name, rating, comment, date, language)

        # Отправляем отзыв на модерацию
        await send_review_for_moderation(bot, review_id, user_id, company_name, rating, comment, date)

        await message.answer(translation["review_submitted"])
        # Завершение процесса: очищаем временные данные
        del user_data[user_id]

# Обработчик кнопки "Найти отзывы" с эмодзи
@dp.message_handler(lambda message: message.text in ["🔍 Найти отзывы", "🔍 Знайти відгуки", "🔍 Znajdź recenzje"])
async def find_reviews_handler(message: types.Message):
    user_id = message.from_user.id

    # Проверяем, что данные пользователя уже сохранены
    if user_id not in user_data:
        await message.answer("Пожалуйста, выберите язык сначала, используя команду /start.")
        return

    language = user_data[user_id]["language"]
    translation = translations[language]
    
    await message.answer(translation["enter_company_for_search"])
    user_data[user_id]["step"] = "search"

# Поиск отзывов по названию компании с постраничным выводом
@dp.message_handler(lambda message: message.from_user.id in user_data and "step" in user_data[message.from_user.id] and user_data[message.from_user.id]["step"] == "search")
async def search_reviews(message: types.Message):
    company_name = message.text.strip().lower()  # Обработка названия компании
    user_id = message.from_user.id
    language = user_data[user_id]["language"]
    translation = translations[language]

    # Проверка: вызывается ли функция поиска
    await message.answer(f"Запуск поиска для компании: {company_name}")

    # Получаем отзывы и общий рейтинг компании
    reviews = await get_reviews_by_company(company_name)
    avg_rating = await get_average_rating(company_name)

    # Проверка результатов
    if not reviews:
        await message.answer(translation["reviews_not_found"])
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
    language = user_data[user_id]["language"]
    translation = translations[language]

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

    # Получаем ID сообщения из канала модерации, ID пользователя и язык отзыва
    message_id = callback_query.message.message_id
    user_id = await get_user_id_by_review_id(review_id)  # Получаем user_id из базы данных по review_id
    language = await get_language_by_review_id(review_id)  # Получаем язык по review_id
    translation = translations[language]  # Получаем переводы на нужном языке
    
    # Обновляем статус отзыва на "approved"
    await update_review_status(review_id, "approved")
    
    # Отправляем пользователю уведомление об одобрении на его языке
    try:
        await bot.send_message(user_id, translation["review_approved"])  # Используем перевод "Ваш отзыв был одобрен!"
    except Exception as e:
        await bot.send_message(callback_query.from_user.id, f"Не удалось отправить сообщение пользователю: {e}")

    # Удаляем сообщение из канала модерации после одобрения
    await bot.delete_message(callback_query.message.chat.id, message_id)

# Запуск бота
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())  # Инициализация базы данных отзывов
    loop.run_until_complete(init_users_db())  # Инициализация базы данных пользователей
    executor.start_polling(dp, skip_updates=True)