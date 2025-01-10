from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def create_language_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        KeyboardButton("🇷🇺 Русский"),
        KeyboardButton("🇵🇱 Polski"),
        KeyboardButton("🇺🇦 Українська"),
    )
    return keyboard


def create_city_keyboard(lang):
    cities = {
        "Русский": ["🏙 Варшава"],
        "Polski": ["🏙 Warszawa"],
        "Українська": ["🏙 Варшава"],
    }
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    for city in cities.get(lang, []):
        keyboard.add(KeyboardButton(city))
    return keyboard


def create_main_menu(lang):
    actions = {
        "Русский": ["✍️ Оставить отзыв", "🔍 Найти отзывы", "🌐 Сменить язык/Город"],
        "Polski": ["✍️ Zostaw recenzję", "🔍 Znajdź recenzje", "🌐 Zmień język/miasto"],
        "Українська": ["✍️ Залишити відгук", "🔍 Знайти відгуки", "🌐 Змінити мову/місто"],
    }
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    for action in actions.get(lang, []):
        keyboard.add(KeyboardButton(action))
    return keyboard