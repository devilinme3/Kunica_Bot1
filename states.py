from aiogram.dispatcher.filters.state import State, StatesGroup

# Состояния для выбора языка, города и основного меню
class UserState(StatesGroup):
    language = State()        # Состояние для выбора языка
    city = State()            # Состояние для выбора города
    main_menu = State()       # Состояние для основного меню
    old_functionality = State()  # Состояние для дополнительных действий (например, поиска отзывов)

# Состояния для заполнения отзыва
class ReviewState(StatesGroup):
    employer = State()        # Ввод названия работодателя
    rating = State()          # Ввод рейтинга (1-5)
    comment = State()         # Ввод комментария