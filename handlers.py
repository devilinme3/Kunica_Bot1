from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from datetime import datetime

from database import (
    save_user,
    save_review,
    update_user_language,
    get_user_language,
    search_approved_reviews
)
from moderation import (
    send_to_moderation,
    handle_approve,
    handle_reject,
    handle_user_reviews,
    navigate_user_reviews,
    hide_user_reviews,
)
from translations import translations
from states import UserState, ReviewState
from keyboards import create_language_keyboard, create_city_keyboard, create_main_menu
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters.state import State, StatesGroup


def require_language_and_city(func):
    """
    Декоратор для проверки выбора языка и города.
    Если язык или город не выбран, перенаправляем на выбор.
    """
    async def wrapper(message: types.Message, *args, **kwargs):
        state: FSMContext = kwargs.get("state")
        user_id = message.from_user.id

        lang = get_user_language(user_id)
        state_data = await state.get_data()
        city = state_data.get("city")

        if not lang:
            keyboard = create_language_keyboard()
            await message.answer("🌍 Пожалуйста, выберите язык:", reply_markup=keyboard)
            await UserState.language.set()
            return

        if not city:
            keyboard = create_city_keyboard(lang)
            await message.answer(translations[lang]["choose_city"], reply_markup=keyboard)
            await UserState.city.set()
            return

        await func(message, *args, **kwargs)

    return wrapper


# Дополнительное состояние для поиска:
class SearchState(StatesGroup):
    employer_name = State()  # пользователь вводит название работодателя


def register_handlers(dp, bot):
    @dp.message_handler(commands=["start"], state="*")
    async def start_command(message: types.Message, state: FSMContext):
        await state.finish()
        save_user(message.from_user.id, message.from_user.full_name)
        keyboard = create_language_keyboard()
        await message.answer("🌍 Пожалуйста, выберите язык:", reply_markup=keyboard)
        await UserState.language.set()

    @dp.message_handler(state=UserState.language)
    async def choose_language(message: types.Message, state: FSMContext):
        lang = message.text.split(" ")[1]
        update_user_language(message.from_user.id, lang)
        await state.update_data(language=lang)
        keyboard = create_city_keyboard(lang)
        await message.answer(translations[lang]["choose_city"], reply_markup=keyboard)
        await UserState.city.set()

    @dp.message_handler(state=UserState.city)
    async def choose_city(message: types.Message, state: FSMContext):
        user_data = await state.get_data()
        lang = user_data.get("language", "Русский")
        await state.update_data(city=message.text)
        keyboard = create_main_menu(lang)
        await message.answer(translations[lang]["main_menu"], reply_markup=keyboard)
        await UserState.main_menu.set()

    @dp.message_handler(
        Text(equals=[
            "🌐 Сменить язык/Город",
            "🌐 Zmień język/miasto",
            "🌐 Змінити мову/місто"
        ]),
        state="*"
    )
    async def change_language_city(message: types.Message, state: FSMContext):
        await state.finish()
        await state.reset_data()
        keyboard = create_language_keyboard()
        await message.answer("🌍 Пожалуйста, выберите язык:", reply_markup=keyboard)
        await UserState.language.set()

    @dp.message_handler(
        Text(equals=[
            "✍️ Оставить отзыв",
            "✍️ Zostaw recenzję",
            "✍️ Залишити відгук"
        ]),
        state="*"
    )
    @require_language_and_city
    async def leave_review(message: types.Message, state: FSMContext):
        user_data = await state.get_data()
        lang = user_data.get("language", "Русский")
        await message.answer(translations[lang]["enter_employer"])
        await ReviewState.employer.set()

    @dp.message_handler(state=ReviewState.employer)
    async def get_employer(message: types.Message, state: FSMContext):
        if not message.text.isascii():
            await message.answer("Название работодателя можно вводить только латиницей.")
            return
        await state.update_data(employer=message.text)
        await message.answer("Введите оценку от 1 до 5.")
        await ReviewState.rating.set()

    @dp.message_handler(state=ReviewState.rating)
    async def get_rating(message: types.Message, state: FSMContext):
        try:
            rating = int(message.text)
            if not (1 <= rating <= 5):
                raise ValueError
        except ValueError:
            await message.answer("Введите корректную оценку (от 1 до 5).")
            return
        await state.update_data(rating=rating)
        await message.answer("Оставьте свой комментарий.")
        await ReviewState.comment.set()

    @dp.message_handler(state=ReviewState.comment)
    async def review_comment(message: types.Message, state: FSMContext):
        user_data = await state.get_data()
        review_data = {
            "user_id": message.from_user.id,
            "user_name": message.from_user.full_name,
            "employer": user_data["employer"],
            "rating": user_data["rating"],
            "comment": message.text,
            "city": user_data.get("city", "Неизвестный город"),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending",
        }
        review_id = save_review(review_data)
        review_data["id"] = review_id
        await send_to_moderation(review_data, bot)
        await message.answer("Ваш отзыв отправлен на модерацию!")
        await state.finish()

    #
    # --- ЛОГИКА ПОИСКА ---
    #
    @dp.message_handler(
        Text(equals=[
            "🔍 Найти отзывы",
            "🔍 Znajdź recenzje",
            "🔍 Знайти відгуки"
        ]),
        state="*"
    )
    @require_language_and_city
    async def find_reviews_start(message: types.Message, state: FSMContext):
        """
        Пользователь хочет найти отзывы, просим ввести название работодателя (латиницей).
        """
        await message.answer("Введите название работодателя (только латинские буквы):")
        await SearchState.employer_name.set()

    @dp.message_handler(state=SearchState.employer_name)
    async def process_search_name(message: types.Message, state: FSMContext):
        """
        Пользователь ввёл строку, делаем fuzzy-поиск по одобренным отзывам.
        """
        employer_query = message.text.strip()
        if not employer_query.isascii():
            await message.answer("Название работодателя можно вводить только латиницей. Попробуйте снова:")
            return

        page = 0
        limit = 5
        result = search_approved_reviews(employer_query, page=page, limit=limit)
        if not result:
            await message.answer(f"По запросу «{employer_query}» ничего не найдено.")
            await state.finish()
            return

        # Сохраняем matched_employer, чтобы потом листать страницы
        await state.update_data(
            search_query=employer_query,
            matched_employer=result["matched_employer"],  # из нижнего регистра
            current_page=page,
            total_pages=result["total_pages"],
            limit=limit
        )

        await send_search_results(message, result)
        # оставляем state=SearchState.employer_name или finish
        # решите, нужно ли вам хранить эти данные дольше

    async def send_search_results(message: types.Message, data: dict):
        """
        Формирует и отправляет текст результатов поиска.
        """
        matched_employer = data["matched_employer"]
        total_reviews = data["total_reviews"]
        avg_rating = data["average_rating"]
        reviews = data["reviews"]
        total_pages = data["total_pages"]
        current_page = data["current_page"]

        text = (
            f"По запросу <b>{matched_employer}</b> найдено <b>{total_reviews}</b> отзывов.\n"
            f"Средний рейтинг: <b>{round(avg_rating,2)}</b>\n\n"
            f"Страница {current_page+1} из {total_pages}.\n\n"
        )

        for r in reviews:
            text += (
                f"<b>Дата:</b> {r['date']}\n"
                f"<b>Рейтинг:</b> {r['rating']}\n"
                f"<b>Комментарий:</b> {r['comment']}\n"
                "----------------------\n"
            )

        keyboard = InlineKeyboardMarkup(row_width=3)
        # Кнопки "назад/вперёд"
        if current_page > 0:
            keyboard.insert(
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data=f"search_prev_{current_page}"
                )
            )
        if current_page < total_pages - 1:
            keyboard.insert(
                InlineKeyboardButton(
                    "➡️ Вперёд",
                    callback_data=f"search_next_{current_page}"
                )
            )
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

    @dp.callback_query_handler(Text(startswith="search_prev_"), state="*")
    async def search_prev_page(callback_query: types.CallbackQuery, state: FSMContext):
        old_page = int(callback_query.data.split("_")[-1])
        new_page = old_page - 1
        user_data = await state.get_data()

        employer_query = user_data.get("search_query")
        matched_emp = user_data.get("matched_employer")
        limit = user_data.get("limit", 5)
        if not employer_query or not matched_emp:
            await callback_query.answer("Ошибка: нет данных для поиска.")
            return

        # делаем новый запрос (fuzzy) — но чтобы уже не искать заново, можно сделать отдельную функцию
        # Для упрощения используем ту же search_approved_reviews
        result = search_approved_reviews(matched_emp, page=new_page, limit=limit)
        if not result:
            await callback_query.answer("Ошибка при пагинации.", show_alert=True)
            return

        # обновляем current_page
        await state.update_data(current_page=new_page)

        # удаляем старое сообщение
        await bot.delete_message(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id
        )

        # отправляем новое
        await send_search_results(callback_query.message, result)
        await callback_query.answer()

    @dp.callback_query_handler(Text(startswith="search_next_"), state="*")
    async def search_next_page(callback_query: types.CallbackQuery, state: FSMContext):
        old_page = int(callback_query.data.split("_")[-1])
        new_page = old_page + 1
        user_data = await state.get_data()

        matched_emp = user_data.get("matched_employer")
        limit = user_data.get("limit", 5)
        if not matched_emp:
            await callback_query.answer("Ошибка: нет данных для поиска.")
            return

        result = search_approved_reviews(matched_emp, page=new_page, limit=limit)
        if not result:
            await callback_query.answer("Ошибка при пагинации.", show_alert=True)
            return

        await state.update_data(current_page=new_page)

        await bot.delete_message(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id
        )
        await send_search_results(callback_query.message, result)
        await callback_query.answer()

    #
    # --- CALLBACK для модерации (уже были) ---
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