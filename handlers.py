from aiogram import types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from database import add_review, get_reviews_by_company
from moderation import send_review_for_moderation

async def start_command_handler(message: types.Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("Українська"), KeyboardButton("Русский"), KeyboardButton("Polski"))
    await message.answer("Выберите язык:", reply_markup=markup)

async def language_selection_handler(message: types.Message):
    language = message.text
    if language in ["Українська", "Русский", "Polski"]:
        await message.answer(f"Вы выбрали {language}. Продолжим...")
        # Отправить клавиатуру с выбором действия