import sqlite3
from config import DATABASE_FILE


def init_db():
    """
    Создаёт базу данных и необходимые таблицы, если их ещё нет.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            employer TEXT,
            rating INTEGER,
            comment TEXT,
            city TEXT,
            date TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT,
            language TEXT DEFAULT 'Русский'
        )
    """)
    conn.commit()
    conn.close()
    print("База данных и таблицы успешно инициализированы.")


def save_review(data):
    """
    Сохраняет отзыв в базу данных.

    :param data: Словарь с данными отзыва.
    :return: ID добавленного отзыва.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = """
        INSERT INTO reviews (user_id, user_name, employer, rating, comment, city, date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(query, (
        data["user_id"],
        data["user_name"],
        data["employer"],
        data["rating"],
        data["comment"],
        data["city"],
        data["date"],
        data["status"]
    ))
    conn.commit()
    review_id = cursor.lastrowid
    conn.close()
    return review_id


def save_user(user_id, user_name, language="Русский"):
    """
    Сохраняет или обновляет информацию о пользователе.

    :param user_id: ID пользователя.
    :param user_name: Имя пользователя.
    :param language: Выбранный язык пользователя.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = """
        INSERT OR IGNORE INTO users (user_id, user_name, language)
        VALUES (?, ?, ?)
    """
    cursor.execute(query, (user_id, user_name, language))
    conn.commit()
    conn.close()


def get_user_reviews_count(user_id):
    """
    Возвращает количество отзывов пользователя.

    :param user_id: ID пользователя.
    :return: Количество отзывов.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "SELECT COUNT(*) FROM reviews WHERE user_id = ?"
    cursor.execute(query, (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_user_reviews_paginated(user_id, page, limit=5):
    """
    Возвращает отзывы пользователя с пагинацией.

    :param user_id: ID пользователя.
    :param page: Номер страницы.
    :param limit: Количество записей на странице.
    :return: Список отзывов.
    """
    offset = page * limit
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = """
        SELECT employer, rating, comment, date, status
        FROM reviews
        WHERE user_id = ?
        ORDER BY date DESC
        LIMIT ? OFFSET ?
    """
    cursor.execute(query, (user_id, limit, offset))
    reviews = [
        {"employer": row[0], "rating": row[1], "comment": row[2], "date": row[3], "status": row[4]}
        for row in cursor.fetchall()
    ]
    conn.close()
    return reviews


def approve_review(city, review_id):
    """
    Одобряет отзыв.

    :param city: Город, к которому привязан отзыв.
    :param review_id: ID отзыва.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "UPDATE reviews SET status = 'approved' WHERE id = ? AND city = ?"
    cursor.execute(query, (review_id, city))
    conn.commit()
    conn.close()


def reject_review(city, review_id):
    """
    Отклоняет отзыв.

    :param city: Город, к которому привязан отзыв.
    :param review_id: ID отзыва.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "DELETE FROM reviews WHERE id = ? AND city = ?"
    cursor.execute(query, (review_id, city))
    conn.commit()
    conn.close()


def get_user_id_by_review(city, review_id):
    """
    Получает ID пользователя по отзыву.

    :param city: Город, к которому привязан отзыв.
    :param review_id: ID отзыва.
    :return: ID пользователя или None.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "SELECT user_id FROM reviews WHERE id = ? AND city = ?"
    cursor.execute(query, (review_id, city))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def get_user_language(user_id):
    """
    Возвращает язык пользователя.

    :param user_id: ID пользователя.
    :return: Язык пользователя.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "SELECT language FROM users WHERE user_id = ?"
    cursor.execute(query, (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Русский"


def update_user_language(user_id, language):
    """
    Обновляет язык пользователя.

    :param user_id: ID пользователя.
    :param language: Новый язык пользователя.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "UPDATE users SET language = ? WHERE user_id = ?"
    cursor.execute(query, (language, user_id))
    conn.commit()
    conn.close()