from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_CHANNEL_ID
from database import update_review_status, delete_review  # Импортируем нужные функции

# Функция для отправки отзыва на модерацию
async def send_review_for_moderation(bot: Bot, review_id, username, company_name, rating, comment, date):
    # Если у пользователя нет имени (username), используем его ID
    if not username:
        username_display = f"ID: {review_id}"
    else:
        username_display = f"@{username} (ID: {review_id})"
    
    # Формируем сообщение для модерации
    moderation_message = (
        f"Новый отзыв от пользователя {username_display}\n"
        f"Компания: {company_name}\n"
        f"Рейтинг: {rating}/5\n"
        f"Комментарий: {comment}\n"
        f"Дата: {date}\n\n"
        f"Одобрить или отклонить?"
    )
    
    # Создаем кнопки для модерации с review_id
    markup = InlineKeyboardMarkup()
    approve_button = InlineKeyboardButton('Одобрить', callback_data=f'approve_{review_id}')
    decline_button = InlineKeyboardButton('Отклонить', callback_data=f'decline_{review_id}')
    markup.add(approve_button, decline_button)
    
    # Отправляем сообщение на модерацию в канал
    message = await bot.send_message(ADMIN_CHANNEL_ID, moderation_message, reply_markup=markup)
    return message.message_id  # Возвращаем ID сообщения для последующего удаления

# Обработчик для одобрения отзыва
async def approve_review(bot: Bot, review_id, user_id, message_id, callback_query):
    # Обновление статуса отзыва в базе данных
    await update_review_status(review_id, "approved")
    # Уведомляем пользователя, что его отзыв был одобрен
    await bot.send_message(user_id, "Ваш отзыв был одобрен!")
    # Удаляем сообщение из канала модерации
    await bot.delete_message(chat_id=ADMIN_CHANNEL_ID, message_id=message_id)
    # Отвечаем на callback_query, чтобы кнопки исчезли
    await callback_query.answer("Отзыв одобрен")

# Обработчик для отклонения отзыва
async def decline_review(bot: Bot, review_id, user_id, message_id, callback_query):
    # Удаление отзыва из базы данных
    await delete_review(review_id)
    # Уведомляем пользователя, что его отзыв был отклонен
    await bot.send_message(user_id, "Ваш отзыв не прошёл модерацию и был отклонён.")
    # Удаляем сообщение из канала модерации
    await bot.delete_message(chat_id=ADMIN_CHANNEL_ID, message_id=message_id)
    # Отвечаем на callback_query, чтобы кнопки исчезли
    await callback_query.answer("Отзыв отклонён")