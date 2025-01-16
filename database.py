import sqlite3
from config import DATABASE_FILE
from rapidfuzz import process, fuzz  # <-- Библиотека для fuzzy-поиска


def init_db():
    """
    Инициализация базы: создаёт таблицы reviews и users, если их нет.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Таблица отзывов
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

    # Таблица пользователей (если используете для хранения языка и пр.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT,
            language TEXT DEFAULT 'Русский'
        )
    """)

    conn.commit()
    conn.close()
    print("База данных и таблицы успешно инициализированы (или уже существуют).")


def save_review(data: dict) -> int:
    """
    Сохраняет отзыв в базе данных.
    data должен содержать ключи:
      user_id, user_name, employer, rating, comment, city, date, status
    Возвращает ID добавленного отзыва.
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


def save_user(user_id: int, user_name: str, language="Русский"):
    """
    Сохраняет (или игнорирует, если уже есть) пользователя в таблице users.
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


def get_user_language(user_id: int) -> str:
    """
    Возвращает язык пользователя, если есть запись,
    иначе "Русский" по умолчанию.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "SELECT language FROM users WHERE user_id=?"
    cursor.execute(query, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "Русский"


def update_user_language(user_id: int, language: str):
    """
    Обновляет язык пользователя в таблице users.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "UPDATE users SET language=? WHERE user_id=?"
    cursor.execute(query, (language, user_id))
    conn.commit()
    conn.close()


def approve_review(city: str, review_id: int):
    """
    Одобряет отзыв (меняет статус на 'approved').
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "UPDATE reviews SET status='approved' WHERE id=? AND city=?"
    cursor.execute(query, (review_id, city))
    conn.commit()
    conn.close()


def reject_review(city: str, review_id: int):
    """
    Отклоняет отзыв (удаляет запись из базы).
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "DELETE FROM reviews WHERE id=? AND city=?"
    cursor.execute(query, (review_id, city))
    conn.commit()
    conn.close()


def get_user_id_by_review(city: str, review_id: int):
    """
    Возвращает user_id по отзыву (по city и id).
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "SELECT user_id FROM reviews WHERE id=? AND city=?"
    cursor.execute(query, (review_id, city))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_user_reviews_count(user_id: int) -> int:
    """
    Возвращает количество отзывов пользователя (может использоваться модерацией).
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    query = "SELECT COUNT(*) FROM reviews WHERE user_id=?"
    cursor.execute(query, (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_user_reviews_paginated(user_id: int, page: int, limit=5) -> list:
    """
    Возвращает список отзывов пользователя (пагинация).
    Сортируем по дате убывания.
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
    rows = cursor.fetchall()
    conn.close()

    reviews = []
    for row in rows:
        reviews.append({
            "employer": row[0],
            "rating": row[1],
            "comment": row[2],
            "date": row[3],
            "status": row[4],
        })
    return reviews


def search_approved_reviews(employer_query: str, page=0, limit=5) -> dict or None:
    """
    Ищет отзывы со статусом 'approved' (одобренные) по 'fuzzy' поиску в названии работодателя.
    
    :param employer_query: Строка (латиница), которую ввёл пользователь.
    :param page: Номер страницы (0-индексация).
    :param limit: Кол-во отзывов на одной странице.
    :return: dict со структурой:
        {
          "matched_employer": str,     # работодатель (lowercase), который мы выбрали по fuzzy
          "total_reviews": int,        # общее число отзывов
          "average_rating": float,     # средний рейтинг
          "reviews": [ {...}, ... ],   # список отзывов (учитывая пагинацию)
          "total_pages": int,          # общее кол-во страниц
          "current_page": int          # текущая страница
        }
        или None, если ничего не найдено.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # 1. Получаем список всех (уникальных) работодателей (lowercase), у которых status='approved'
    cursor.execute("""
        SELECT DISTINCT LOWER(employer)
        FROM reviews
        WHERE status='approved'
    """)
    all_employers = [row[0] for row in cursor.fetchall()]

    if not all_employers:
        conn.close()
        return None  # нет ни одного одобренного отзыва

    # 2. "Fuzzy" поиск по всем employer (lowercase)
    query_lower = employer_query.lower()
    best_match = process.extractOne(
        query_lower,
        all_employers,
        scorer=fuzz.WRatio  # можно изменить стратегию
    )
    if not best_match:
        conn.close()
        return None

    matched_employer = best_match[0]  # строка (lowercase), которая лучше всего совпала
    score = best_match[1]            # оценка сходства (0..100)

    # Если хотите отсеивать слишком низкое сходство:
    # if score < 50:
    #     conn.close()
    #     return None

    # 3. Получаем все отзывы, где LOWER(employer) = matched_employer, status='approved'
    cursor.execute("""
        SELECT id, user_id, user_name, employer, rating, comment, city, date
        FROM reviews
        WHERE LOWER(employer)=? AND status='approved'
        ORDER BY date DESC
    """, (matched_employer,))
    rows = cursor.fetchall()

    if not rows:
        conn.close()
        return None

    total_reviews = len(rows)
    # Средний рейтинг
    avg_rating = sum([r[4] for r in rows]) / total_reviews  # r[4] = rating

    # Пагинация
    start = page * limit
    end = start + limit
    page_rows = rows[start:end]
    total_pages = (total_reviews + limit - 1) // limit

    # Преобразуем выбранные отзывы в список словарей
    reviews_data = []
    for row in page_rows:
        reviews_data.append({
            "id": row[0],
            "user_id": row[1],
            "user_name": row[2],
            "employer": row[3],
            "rating": row[4],
            "comment": row[5],
            "city": row[6],
            "date": row[7],
        })

    conn.close()

    return {
        "matched_employer": matched_employer,
        "total_reviews": total_reviews,
        "average_rating": avg_rating,
        "reviews": reviews_data,
        "total_pages": total_pages,
        "current_page": page
    }


# Если хотите, можете явно экспортировать функции через __all__:
# __all__ = [
#     "init_db",
#     "save_review",
#     "save_user",
#     "get_user_language",
#     "update_user_language",
#     "approve_review",
#     "reject_review",
#     "get_user_id_by_review",
#     "get_user_reviews_count",
#     "get_user_reviews_paginated",
#     "search_approved_reviews"
# ]