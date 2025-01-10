from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import (
    approve_review,
    reject_review,
    get_user_id_by_review,
    get_user_reviews_paginated,
    get_user_reviews_count
)


async def send_to_moderation(data, bot):
    """
    Отправляет новый отзыв в админ-группу/канал на модерацию.
    """
    try:
        # Кнопки: одобрить, отклонить, отзывы пользователя
        keyboard = InlineKeyboardMarkup(row_width=2)
        approve_btn = InlineKeyboardButton(
            text="✅ Одобрить",
            callback_data=f"approve_{data['city']}_{data['id']}"
        )
        reject_btn = InlineKeyboardButton(
            text="❌ Отклонить",
            callback_data=f"reject_{data['city']}_{data['id']}"
        )
        user_reviews_btn = InlineKeyboardButton(
            text="📋 Отзывы пользователя",
            callback_data=f"user_reviews_{data['user_id']}"
        )
        keyboard.add(approve_btn, reject_btn)
        keyboard.add(user_reviews_btn)

        # Формируем текст сообщения
        message_text = (
            f"🆕 <b>Новый отзыв!</b>\n"
            f"👤 <b>ID:</b> {data['user_id']}\n"
            f"👥 <b>Имя:</b> {data['user_name']}\n"
            f"🏢 <b>Работодатель:</b> {data['employer']}\n"
            f"⭐ <b>Рейтинг:</b> {data['rating']}\n"
            f"💬 <b>Комментарий:</b> {data['comment']}\n"
            f"🌆 <b>Город:</b> {data['city']}\n"
            f"📅 <b>Дата:</b> {data['date']}"
        )

        # Отправляем в группу/канал модерации
        await bot.send_message(
            chat_id="-1002498880033",  # Или используйте ADMIN_GROUP_ID из config.py
            text=message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка в send_to_moderation: {e}")


async def handle_approve(callback_query: types.CallbackQuery, bot):
    """
    Обрабатывает нажатие на кнопку "Одобрить":
      1. Меняет статус в БД на 'approved'.
      2. Отправляет пользователю уведомление об одобрении.
      3. Удаляет сообщение из чата модерации.
    """
    try:
        _, city, review_id = callback_query.data.split("_")
        review_id = int(review_id)

        # Одобряем отзыв
        approve_review(city, review_id)

        # Уведомляем пользователя
        user_id = get_user_id_by_review(city, review_id)
        if user_id:
            await bot.send_message(user_id, "✅ Ваш отзыв успешно прошёл модерацию!")

        # Удаляем сообщение из чата модерации
        await bot.delete_message(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id
        )

        # Уведомляем модератора (alert). Можно отключить show_alert, если не нужно всплывающее окно
        await callback_query.answer("Отзыв одобрен.", show_alert=False)

    except Exception as e:
        print(f"Ошибка в handle_approve: {e}")
        await callback_query.answer("Ошибка обработки.", show_alert=True)


async def handle_reject(callback_query: types.CallbackQuery, bot):
    """
    Обрабатывает нажатие на кнопку "Отклонить":
      1. Сначала получаем user_id из БД (пока отзыв ещё там).
      2. Удаляем отзыв из БД.
      3. Отправляем пользователю уведомление об отклонении.
      4. Удаляем сообщение из чата модерации.
    """
    try:
        _, city, review_id = callback_query.data.split("_")
        review_id = int(review_id)

        # ВАЖНО: сначала получаем user_id, пока отзыв ещё не удалён
        user_id = get_user_id_by_review(city, review_id)

        # Удаляем отзыв
        reject_review(city, review_id)

        # Уведомляем пользователя
        if user_id:
            await bot.send_message(user_id, "❌ Ваш отзыв не прошёл модерацию.")

        # Удаляем сообщение из чата модерации
        await bot.delete_message(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id
        )

        # Короткий ответ модератору
        await callback_query.answer("Отзыв отклонён.", show_alert=False)

    except Exception as e:
        print(f"Ошибка в handle_reject: {e}")
        await callback_query.answer("Ошибка обработки.", show_alert=True)


async def handle_user_reviews(callback_query: types.CallbackQuery, bot):
    """
    Показывает список отзывов конкретного пользователя (для модератора).
    """
    try:
        _, user_id = callback_query.data.split("_")
        user_id = int(user_id)

        total_count = get_user_reviews_count(user_id)
        if total_count == 0:
            await bot.send_message(
                callback_query.message.chat.id,
                "❌ У пользователя нет отзывов."
            )
            await callback_query.answer()
            return

        # Получаем первые 5 отзывов (страница 0)
        reviews = get_user_reviews_paginated(user_id, page=0)
        await send_user_reviews(
            chat_id=callback_query.message.chat.id,
            reviews=reviews,
            user_id=user_id,
            bot=bot,
            page=0
        )
        await callback_query.answer()

    except Exception as e:
        print(f"Ошибка в handle_user_reviews: {e}")
        await callback_query.answer("Ошибка при показе отзывов.", show_alert=True)


async def navigate_user_reviews(callback_query: types.CallbackQuery, bot):
    """
    Листает (Назад/Вперёд) отзывы одного пользователя (для модератора).
    """
    try:
        _, user_id, page = callback_query.data.split("_")
        user_id = int(user_id)
        page = int(page)

        reviews = get_user_reviews_paginated(user_id, page=page)
        if not reviews:
            await callback_query.answer("Больше отзывов нет.", show_alert=True)
            return

        await send_user_reviews(
            chat_id=callback_query.message.chat.id,
            reviews=reviews,
            user_id=user_id,
            bot=bot,
            page=page
        )
        await callback_query.answer()
    except Exception as e:
        print(f"Ошибка в navigate_user_reviews: {e}")
        await callback_query.answer("Ошибка пагинации.", show_alert=True)


async def hide_user_reviews(callback_query: types.CallbackQuery, bot):
    """
    Скрывает (удаляет) сообщение со списком отзывов пользователя (у модератора).
    """
    try:
        await bot.delete_message(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id
        )
        await callback_query.answer()
    except Exception as e:
        print(f"Ошибка в hide_user_reviews: {e}")
        await callback_query.answer("Ошибка удаления сообщений.", show_alert=True)


async def send_user_reviews(chat_id, reviews, user_id, bot, page):
    """
    Отправляет список отзывов пользователя модератору с кнопками пагинации.
    """
    try:
        text = f"Отзывы пользователя <b>{user_id}</b> (страница {page + 1}):\n\n"
        for review in reviews:
            text += (
                f"— <b>Работодатель:</b> {review['employer']}\n"
                f"— <b>Рейтинг:</b> {review['rating']}\n"
                f"— <b>Комментарий:</b> {review['comment']}\n"
                f"— <b>Дата:</b> {review['date']}\n"
                f"— <b>Статус:</b> {review['status']}\n\n"
            )

        # Проверяем, есть ли следующая страница
        next_page_reviews = get_user_reviews_paginated(user_id, page=page + 1)

        # Клавиатура с кнопками
        keyboard = InlineKeyboardMarkup(row_width=3)

        if page > 0:
            keyboard.insert(
                InlineKeyboardButton(
                    "⬅️ Назад",
                    callback_data=f"navigate_{user_id}_{page - 1}"
                )
            )

        if len(next_page_reviews) > 0:
            keyboard.insert(
                InlineKeyboardButton(
                    "➡️ Вперёд",
                    callback_data=f"navigate_{user_id}_{page + 1}"
                )
            )

        # Кнопка «Скрыть»
        keyboard.add(InlineKeyboardButton("❌ Скрыть", callback_data="hide_reviews"))

        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка в send_user_reviews: {e}")


__all__ = [
    "send_to_moderation",
    "handle_approve",
    "handle_reject",
    "handle_user_reviews",
    "navigate_user_reviews",
    "hide_user_reviews",
]