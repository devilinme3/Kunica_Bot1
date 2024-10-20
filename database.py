import aiosqlite

# Функция для инициализации базы данных
async def init_db():
    async with aiosqlite.connect('reviews.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                company_name TEXT,
                rating INTEGER,
                comment TEXT,
                date TEXT,
                status TEXT DEFAULT "pending"
            )
        ''')
        await db.commit()

# Функция для добавления нового отзыва с возвратом review_id
async def add_review(user_id, username, company_name, rating, comment, date):
    async with aiosqlite.connect('reviews.db') as db:
        cursor = await db.execute('''
            INSERT INTO reviews (user_id, username, company_name, rating, comment, date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, company_name, rating, comment, date, "pending"))
        await db.commit()
        return cursor.lastrowid

# Функция для получения подтвержденных отзывов по названию компании, игнорируя регистр
async def get_reviews_by_company(company_name):
    async with aiosqlite.connect('reviews.db') as db:
        async with db.execute('''
            SELECT company_name, rating, comment, date FROM reviews
            WHERE LOWER(company_name) LIKE ? AND status = "approved"
        ''', (f'%{company_name}%',)) as cursor:
            reviews = await cursor.fetchall()
            print(f"Найдено {len(reviews)} отзывов для компании {company_name}")  # Отладочный вывод
            return reviews

# Функция для получения среднего рейтинга компании
async def get_average_rating(company_name):
    async with aiosqlite.connect('reviews.db') as db:
        async with db.execute('''
            SELECT AVG(rating) FROM reviews
            WHERE LOWER(company_name) LIKE ? AND status = "approved"
        ''', (f'%{company_name}%',)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row[0] is not None else 0

# Функция для обновления статуса отзыва (например, "approved" или "declined")
async def update_review_status(review_id, status):
    async with aiosqlite.connect('reviews.db') as db:
        await db.execute('''
            UPDATE reviews SET status = ? WHERE id = ?
        ''', (status, review_id))
        await db.commit()

# Функция для удаления отзыва
async def delete_review(review_id):
    async with aiosqlite.connect('reviews.db') as db:
        cursor = await db.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
        await db.commit()

        # Отладочный вывод: проверяем, сколько строк было удалено
        rows_affected = cursor.rowcount
        print(f"Удалено строк: {rows_affected} для review_id: {review_id}")