from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_CHANNEL_ID
from database import update_review_status, delete_review

# Функция отправки отзыва на модерацию
async def send_review_for_moderation(bot: Bot, review_id: int, user_id: int, company_name: str, rating: int, comment: str, date: str):
    # Клавиатура для модерации
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅Одобрить", callback_data=f"approve_{review_id}"))
    markup.add(InlineKeyboardButton("⭕️Отклонить", callback_data=f"decline_{review_id}"))

    # Сообщение на модерацию с ID пользователя (Telegram ID)
    text = (
        f"Новый отзыв от пользователя ID: {user_id}\n"  # Telegram ID пользователя
        f"Компания: {company_name}\n"
        f"Рейтинг: {rating}/5\n"
        f"Комментарий: {comment}\n"
        f"Дата: {date}"
    )

    # Отправляем сообщение в канал модерации
    await bot.send_message(chat_id=ADMIN_CHANNEL_ID, text=text, reply_markup=markup)

# Функция для одобрения отзыва
async def approve_review(bot: Bot, review_id: int, user_id: int, message_id: int, callback_query):
    # Обновляем статус отзыва в базе данных
    await update_review_status(review_id, "approved")

    # Отправляем пользователю уведомление об одобрении
    try:
        await bot.send_message(user_id, "Ваш отзыв был одобрен!")
    except Exception as e:
        await bot.send_message(callback_query.from_user.id, f"Не удалось отправить сообщение пользователю: {e}")

    # Удаляем сообщение о модерации из канала
    await bot.delete_message(callback_query.message.chat.id, message_id)

# Функция для отклонения отзыва
async def decline_review(bot: Bot, review_id: int, user_id: int, message_id: int, callback_query):
    # Удаляем отзыв из базы данных
    await delete_review(review_id)

    # Отправляем пользователю уведомление об отклонении
    try:
        await bot.send_message(user_id, "Ваш отзыв был отклонён.")
    except Exception as e:
        await bot.send_message(callback_query.from_user.id, f"Не удалось отправить сообщение пользователю: {e}")

    # Удаляем сообщение о модерации из канала
    await bot.delete_message(callback_query.message.chat.id, message_id)