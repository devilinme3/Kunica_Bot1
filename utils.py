from aiogram.dispatcher import FSMContext
from aiogram import Bot


async def clear_chat(state: FSMContext, chat_id: int, bot: Bot):
    """
    Удаляет все сообщения, сохранённые в состоянии FSMContext.
    
    Параметры:
        state (FSMContext): Контекст состояния FSM.
        chat_id (int): ID чата, в котором нужно удалить сообщения.
        bot (Bot): Экземпляр бота для выполнения удаления сообщений.
    """
    if not state:
        return  # Если состояние не передано, ничего не делаем

    async with state.proxy() as data:
        if "messages" in data:
            for message_id in data["messages"]:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except Exception as e:
                    print(f"Не удалось удалить сообщение {message_id}: {e}")
            data["messages"] = []


def get_paginated_keyboard(current_page: int, total_pages: int, callback_prefix: str):
    """
    Генерирует клавиатуру для пагинации.
    
    Параметры:
        current_page (int): Текущая страница.
        total_pages (int): Общее количество страниц.
        callback_prefix (str): Префикс для callback_data.

    Возвращает:
        InlineKeyboardMarkup: Клавиатура с кнопками для навигации.
    """
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(row_width=3)
    if current_page > 0:
        keyboard.add(
            InlineKeyboardButton(
                "⬅️ Назад", callback_data=f"{callback_prefix}_{current_page - 1}"
            )
        )
    if current_page < total_pages - 1:
        keyboard.add(
            InlineKeyboardButton(
                "➡️ Вперёд", callback_data=f"{callback_prefix}_{current_page + 1}"
            )
        )
    keyboard.add(
        InlineKeyboardButton("❌ Закрыть", callback_data=f"{callback_prefix}_close")
    )
    return keyboard