from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from datetime import datetime

# Импорт логики базы данных и модерации
from database import (
    save_user,
    save_review,
    update_user_language,
    get_user_language,
)
from moderation import (
    send_to_moderation,
    handle_approve,
    handle_reject,
    handle_user_reviews,
    navigate_user_reviews,
    hide_user_reviews,
)

# Импорт переводов, состояний и клавиатур
from translations import translations
from states import UserState, ReviewState
from keyboards import create_language_keyboard, create_city_keyboard, create_main_menu


def require_language_and_city(func):
    """
    Декоратор для проверки выбора языка и города.
    Если язык или город не выбран — перенаправляет пользователя на выбор.
    """
    async def wrapper(message: types.Message, *args, **kwargs):
        state: FSMContext = kwargs.get("state")
        user_id = message.from_user.id

        # Определяем язык пользователя из БД
        lang = get_user_language(user_id)
        # Определяем город из FSMContext
        state_data = await state.get_data()
        city = state_data.get("city")

        # Если язык ещё не выбран
        if not lang:
            keyboard = create_language_keyboard()
            await message.answer("🌍 Пожалуйста, выберите язык:", reply_markup=keyboard)
            await UserState.language.set()
            return

        # Если город ещё не выбран
        if not city:
            keyboard = create_city_keyboard(lang)
            await message.answer(translations[lang]["choose_city"], reply_markup=keyboard)
            await UserState.city.set()
            return

        # Если язык и город выбраны, вызываем исходную функцию
        await func(message, *args, **kwargs)

    return wrapper


def register_handlers(dp, bot):
    """
    Регистрирует все обработчики (команды, сообщения, колбэки) бота.
    """

    #
    # 1. /start
    #
    @dp.message_handler(commands=["start"], state="*")
    async def start_command(message: types.Message, state: FSMContext):
        """
        При /start сбрасываем текущее состояние и просим выбрать язык.
        """
        await state.finish()
        save_user(message.from_user.id, message.from_user.full_name)
        keyboard = create_language_keyboard()
        await message.answer("🌍 Пожалуйста, выберите язык:", reply_markup=keyboard)
        await UserState.language.set()

    #
    # 2. Выбор языка
    #
    @dp.message_handler(state=UserState.language)
    async def choose_language(message: types.Message, state: FSMContext):
        """
        После выбора языка просим выбрать город.
        """
        # Предполагаем, что пользователь нажал кнопку вида "🇷🇺 Русский" => берём второе слово "Русский"
        lang = message.text.split(" ")[1]
        update_user_language(message.from_user.id, lang)

        await state.update_data(language=lang)
        keyboard = create_city_keyboard(lang)
        await message.answer(translations[lang]["choose_city"], reply_markup=keyboard)
        await UserState.city.set()

    #
    # 3. Выбор города
    #
    @dp.message_handler(state=UserState.city)
    async def choose_city(message: types.Message, state: FSMContext):
        """
        После выбора города показываем главное меню на выбранном языке.
        """
        user_data = await state.get_data()
        lang = user_data.get("language", "Русский")

        await state.update_data(city=message.text)
        keyboard = create_main_menu(lang)
        await message.answer(translations[lang]["main_menu"], reply_markup=keyboard)
        await UserState.main_menu.set()

    #
    # 4. Смена языка/города (учитываем все языки)
    #
    @dp.message_handler(
        Text(equals=[
            "🌐 Сменить язык/Город",
            "🌐 Zmień język/miasto",
            "🌐 Змінити мову/місто"
        ]),
        state="*"
    )
    async def change_language_city(message: types.Message, state: FSMContext):
        """
        Сбрасывает текущее состояние и данные, просит выбрать язык заново.
        """
        await state.finish()
        await state.reset_data()

        keyboard = create_language_keyboard()
        await message.answer("🌍 Пожалуйста, выберите язык:", reply_markup=keyboard)
        await UserState.language.set()

    #
    # 5. Оставить отзыв (учитываем все языки)
    #
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
        """
        Начинаем процесс ввода отзыва: работодатель -> рейтинг -> комментарий.
        """
        user_data = await state.get_data()
        lang = user_data.get("language", "Русский")
        await message.answer(translations[lang]["enter_employer"])
        await ReviewState.employer.set()

    #
    # 6. Ввод названия работодателя (латиницей)
    #
    @dp.message_handler(state=ReviewState.employer)
    async def get_employer(message: types.Message, state: FSMContext):
        if not message.text.isascii():
            await message.answer("Название работодателя можно вводить только латиницей.")
            return
        await state.update_data(employer=message.text)
        await message.answer("Введите оценку от 1 до 5.")
        await ReviewState.rating.set()

    #
    # 7. Ввод рейтинга (1–5)
    #
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

    #
    # 8. Ввод комментария и отправка на модерацию
    #
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

        # Отправляем в группу модерации
        await send_to_moderation(review_data, bot)

        await message.answer("Ваш отзыв отправлен на модерацию!")
        await state.finish()

    #
    # 9. Найти отзывы (учитываем все языки)
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
    async def find_reviews(message: types.Message, state: FSMContext):
        """
        Обработчик кнопки для поиска отзывов.
        """
        user_data = await state.get_data()
        lang = user_data.get("language", "Русский")
        await message.answer("🔍 Введите название работодателя для поиска:")
        # Здесь может быть реализация поиска отзывов (не реализована)

    #
    # 10. Callback-хендлеры для модерации
    #
    @dp.callback_query_handler(Text(startswith="approve_"))
    async def cb_approve(callback_query: types.CallbackQuery):
        """
        Одобрение отзыва из группы модерации (удаляет сообщение из чата).
        """
        await handle_approve(callback_query, bot)

    @dp.callback_query_handler(Text(startswith="reject_"))
    async def cb_reject(callback_query: types.CallbackQuery):
        """
        Отклонение отзыва из группы модерации (удаляет сообщение из чата).
        """
        await handle_reject(callback_query, bot)

    @dp.callback_query_handler(Text(startswith="user_reviews_"))
    async def cb_user_reviews(callback_query: types.CallbackQuery):
        """
        Показ отзывов конкретного пользователя модератору.
        """
        await handle_user_reviews(callback_query, bot)

    @dp.callback_query_handler(Text(startswith="navigate_"))
    async def cb_navigate(callback_query: types.CallbackQuery):
        """
        Пагинация при просмотре отзывов пользователя (модератором).
        """
        await navigate_user_reviews(callback_query, bot)

    @dp.callback_query_handler(Text(equals="hide_reviews"))
    async def cb_hide(callback_query: types.CallbackQuery):
        """
        Скрыть (удалить) сообщения с отзывами пользователя из чата.
        """
        await hide_user_reviews(callback_query, bot)