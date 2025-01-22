from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from datetime import datetime

# Импортируем функции из database.py
from database import (
    init_db,
    save_user,
    save_review,
    update_user_language,
    get_user_language,
    approve_review,
    reject_review,
    get_user_id_by_review,
    get_user_reviews_count,
    get_user_reviews_paginated,
    search_approved_reviews
)

# Логика модерации
from moderation import (
    send_to_moderation,
    handle_approve,
    handle_reject,
    handle_user_reviews,
    navigate_user_reviews,
    hide_user_reviews
)

# Импорт переводов
from translations import translations

# Состояния
from states import UserState, ReviewState
from aiogram.dispatcher.filters.state import State, StatesGroup


###############################################################################
# Состояние для поиска (fuzzy)
###############################################################################
class SearchState(StatesGroup):
    employer_name = State()


###############################################################################
# Функции для создания клавиатур: язык, город, главное меню
###############################################################################
def create_language_keyboard():
    """
    Кнопки для выбора языка: Русский, Польский, Украинский.
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇵🇱 Polski", "🇺🇦 Українська")
    return kb

def create_city_keyboard(lang: str):
    """
    Создаёт клавиатуру городов на основании translations[lang]["cities"].
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    cities = translations[lang]["cities"]  # Например, ["🏙 Варшава"] или ["🏙 Warszawa"]
    for city in cities:
        kb.add(city)
    return kb

def create_main_menu(lang: str):
    """
    Создаёт главное меню на нужном языке (3 кнопки).
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    # Можно хранить кнопки в translations, но здесь для наглядности формируем словарь
    buttons_map = {
        "Русский": ["✍️ Оставить отзыв", "🔍 Найти отзывы", "🌐 Сменить язык/Город"],
        "Polski": ["✍️ Zostaw recenzję", "🔍 Znajdź recenzje", "🌐 Zmień język/miasto"],
        "Українська": ["✍️ Залишити відгук", "🔍 Знайти відгуки", "🌐 Змінити мову/місто"]
    }
    for b in buttons_map.get(lang, buttons_map["Русский"]):
        kb.add(b)
    return kb


###############################################################################
# Декоратор: проверяем, выбран ли язык/город
###############################################################################
def require_language_and_city(func):
    async def wrapper(message: types.Message, *args, **kwargs):
        state: FSMContext = kwargs.get("state")
        user_id = message.from_user.id

        lang = get_user_language(user_id)
        data = await state.get_data()
        city = data.get("city")

        if not lang:
            # Нет языка — покажем клавиатуру языков
            kb = create_language_keyboard()
            await message.answer("🌍 Пожалуйста, выберите язык:", reply_markup=kb)
            await UserState.language.set()
            return

        if not city:
            # Нет города — покажем клавиатуру городов
            kb = create_city_keyboard(lang)
            await message.answer(translations[lang]["choose_city"], reply_markup=kb)
            await UserState.city.set()
            return

        # Всё выбрано — продолжаем
        await func(message, *args, **kwargs)
    return wrapper


###############################################################################
# Регистрация хендлеров
###############################################################################
def register_handlers(dp, bot):

    # 1. /start
    @dp.message_handler(commands=["start"], state="*")
    async def start_command(message: types.Message, state: FSMContext):
        # Сброс состояния
        await state.finish()
        # Сохраняем пользователя в БД
        save_user(message.from_user.id, message.from_user.full_name)
        # Показываем клавиатуру выбора языка
        kb = create_language_keyboard()
        await message.answer("🌍 Пожалуйста, выберите язык:", reply_markup=kb)
        await UserState.language.set()

    # 2. Обработка выбора языка
    @dp.message_handler(state=UserState.language)
    async def choose_language(message: types.Message, state: FSMContext):
        # Предполагаем, что текст вида "🇷🇺 Русский" => берём второе слово
        splitted = message.text.split(" ", 1)
        if len(splitted) > 1:
            lang = splitted[1]
        else:
            lang = "Русский"

        update_user_language(message.from_user.id, lang)
        await state.update_data(language=lang)

        # Клавиатура выбора города
        kb = create_city_keyboard(lang)
        await message.answer(translations[lang]["choose_city"], reply_markup=kb)
        await UserState.city.set()

    # 3. Обработка выбора города
    @dp.message_handler(state=UserState.city)
    async def choose_city(message: types.Message, state: FSMContext):
        data = await state.get_data()
        lang = data.get("language", "Русский")
        city = message.text

        # Сохраняем выбранный город
        await state.update_data(city=city)

        # Показываем главное меню
        kb = create_main_menu(lang)
        await message.answer(translations[lang]["main_menu"], reply_markup=kb)
        await UserState.main_menu.set()

    # 4. Смена языка/города
    @dp.message_handler(
        Text(equals=[
            "🌐 Сменить язык/Город",
            "🌐 Zmień język/miasto",
            "🌐 Змінити мову/місто"
        ]),
        state="*"
    )
    async def change_language_city(message: types.Message, state: FSMContext):
        # Сбрасываем состояние
        await state.finish()
        await state.reset_data()

        # Показываем клавиатуру языков
        kb = create_language_keyboard()
        await message.answer("🌍 Пожалуйста, выберите язык:", reply_markup=kb)
        await UserState.language.set()

    # 5. Оставить отзыв
    @dp.message_handler(Text(equals=[
        "✍️ Оставить отзыв",
        "✍️ Zostaw recenzję",
        "✍️ Залишити відгук"
    ]), state="*")
    @require_language_and_city
    async def leave_review(message: types.Message, state: FSMContext):
        data = await state.get_data()
        lang = data.get("language", "Русский")

        # Выводим перевод для "enter_employer"
        await message.answer(translations[lang]["enter_employer"])
        await ReviewState.employer.set()

    @dp.message_handler(state=ReviewState.employer)
    async def get_employer(message: types.Message, state: FSMContext):
        if not message.text.isascii():
            await message.answer("Название работодателя можно вводить только латиницей.")
            return
        await state.update_data(employer=message.text)

        data = await state.get_data()
        lang = data.get("language", "Русский")
        # Выводим перевод для "enter_rating"
        await message.answer(translations[lang]["enter_rating"])
        await ReviewState.rating.set()

    @dp.message_handler(state=ReviewState.rating)
    async def get_rating(message: types.Message, state: FSMContext):
        try:
            rating = int(message.text)
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            await message.answer("Введите корректную оценку (от 1 до 5).")
            return

        await state.update_data(rating=rating)
        data = await state.get_data()
        lang = data.get("language", "Русский")
        # Выводим перевод для "enter_comment"
        await message.answer(translations[lang]["enter_comment"])
        await ReviewState.comment.set()

    @dp.message_handler(state=ReviewState.comment)
    async def review_comment(message: types.Message, state: FSMContext):
        data = await state.get_data()
        lang = data.get("language", "Русский")

        review_data = {
            "user_id": message.from_user.id,
            "user_name": message.from_user.full_name,
            "employer": data["employer"],
            "rating": data["rating"],
            "comment": message.text,
            "city": data.get("city", "Неизвестный город"),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending",
        }
        review_id = save_review(review_data)
        review_data["id"] = review_id
        await send_to_moderation(review_data, bot)

        # Выводим перевод для "review_submitted"
        await message.answer(translations[lang]["review_submitted"])
        await state.finish()

    # 6. Найти отзывы (fuzzy)
    @dp.message_handler(Text(equals=[
        "🔍 Найти отзывы",
        "🔍 Znajdź recenzje",
        "🔍 Знайти відгуки"
    ]), state="*")
    @require_language_and_city
    async def find_reviews_start(message: types.Message, state: FSMContext):
        data = await state.get_data()
        lang = data.get("language", "Русский")

        # Выводим перевод для "fuzzy_search_prompt"
        prompt = translations[lang]["fuzzy_search_prompt"]
        await message.answer(prompt)
        await SearchState.employer_name.set()

    @dp.message_handler(state=SearchState.employer_name)
    async def process_search_name(message: types.Message, state: FSMContext):
        employer_query = message.text.strip()
        if not employer_query.isascii():
            await message.answer("Название работодателя можно вводить только латиницей.")
            return

        data = await state.get_data()
        lang = data.get("language", "Русский")

        page = 0
        limit = 5
        result = search_approved_reviews(employer_query, page=page, limit=limit)
        if not result:
            # no_results
            msg_nores = translations[lang]["no_results"].format(query=employer_query)
            await message.answer(msg_nores)
            await state.finish()
            return

        await state.update_data(
            search_query=employer_query,
            matched_employer=result["matched_employer"],
            current_page=page,
            total_pages=result["total_pages"],
            limit=limit
        )
        await send_search_results(message, result, lang)

    async def send_search_results(message: types.Message, data: dict, lang: str):
        """
        Формируем текст по шаблону search_results_header, подставляем count, avg, 
        страница и т.д.
        """
        matched_employer = data["matched_employer"]
        total_reviews = data["total_reviews"]
        avg_rating = data["average_rating"]
        reviews = data["reviews"]
        total_pages = data["total_pages"]
        current_page = data["current_page"]

        # Шаблон: search_results_header
        header_template = translations[lang]["search_results_header"]
        text_header = header_template.format(
            employer=matched_employer,
            count=total_reviews,
            avg=round(avg_rating, 2),
            page=current_page + 1,
            total=total_pages
        )

        text = text_header
        # Выводим сами отзывы
        for r in reviews:
            text += (
                f"🗓 <b>Дата:</b> {r['date']}\n"
                f"⭐ <b>Рейтинг:</b> {r['rating']}\n"
                f"💬 <b>Комментарий:</b> {r['comment']}\n"
                "————————————\n"
            )

        # Кнопки пагинации
        keyboard = InlineKeyboardMarkup(row_width=3)
        if current_page > 0:
            keyboard.insert(
                InlineKeyboardButton("⬅️ Назад", callback_data=f"search_prev_{current_page}")
            )
        if current_page < total_pages - 1:
            keyboard.insert(
                InlineKeyboardButton("➡️ Вперёд", callback_data=f"search_next_{current_page}")
            )

        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

    # Пагинация поиска
    @dp.callback_query_handler(Text(startswith="search_prev_"), state="*")
    async def search_prev_page(callback_query: types.CallbackQuery, state: FSMContext):
        old_page = int(callback_query.data.split("_")[-1])
        new_page = old_page - 1
        data = await state.get_data()
        lang = data.get("language", "Русский")

        matched_emp = data.get("matched_employer")
        limit = data.get("limit", 5)
        if not matched_emp:
            await callback_query.answer("Ошибка: нет данных для поиска.")
            return

        result = search_approved_reviews(matched_emp, page=new_page, limit=limit)
        if not result:
            await callback_query.answer("Ошибка при пагинации.", show_alert=True)
            return

        await state.update_data(current_page=new_page)
        await bot.delete_message(chat_id=callback_query.message.chat.id,
                                message_id=callback_query.message.message_id)
        await send_search_results(callback_query.message, result, lang)
        await callback_query.answer()

    @dp.callback_query_handler(Text(startswith="search_next_"), state="*")
    async def search_next_page(callback_query: types.CallbackQuery, state: FSMContext):
        old_page = int(callback_query.data.split("_")[-1])
        new_page = old_page + 1
        data = await state.get_data()
        lang = data.get("language", "Русский")

        matched_emp = data.get("matched_employer")
        limit = data.get("limit", 5)
        if not matched_emp:
            await callback_query.answer("Ошибка: нет данных для поиска.")
            return

        result = search_approved_reviews(matched_emp, page=new_page, limit=limit)
        if not result:
            await callback_query.answer("Ошибка при пагинации.", show_alert=True)
            return

        await state.update_data(current_page=new_page)
        await bot.delete_message(chat_id=callback_query.message.chat.id,
                                message_id=callback_query.message.message_id)
        await send_search_results(callback_query.message, result, lang)
        await callback_query.answer()

    #
    # CALLBACKS для модерации
    #
    @dp.callback_query_handler(Text(startswith="approve_"))
    async def cb_approve(callback_query: types.CallbackQuery):
        await handle_approve(callback_query, bot)

    @dp.callback_query_handler(Text(startswith="reject_"))
    async def cb_reject(callback_query: types.CallbackQuery):
        await handle_reject(callback_query, bot)

    @dp.callback_query_handler(Text(startswith="user_reviews_"))
    async def cb_user_reviews(callback_query: types.CallbackQuery):
        await handle_user_reviews(callback_query, bot)

    @dp.callback_query_handler(Text(startswith="navigate_"))
    async def cb_navigate(callback_query: types.CallbackQuery):
        await navigate_user_reviews(callback_query, bot)

    @dp.callback_query_handler(Text(equals="hide_reviews"))
    async def cb_hide(callback_query: types.CallbackQuery):
        await hide_user_reviews(callback_query, bot)