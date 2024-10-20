import aiosqlite

# Инициализация базы данных
async def init_db():
    async with aiosqlite.connect('reviews.db') as db:
        # Создание таблицы для отзывов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                company_name TEXT,
                rating INTEGER,
                comment TEXT,
                date TEXT,
                status TEXT DEFAULT "pending",
                language TEXT
            )
        ''')
        # Создание таблицы для пользователей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                date_joined TEXT
            )
        ''')
        await db.commit()

# Функция для добавления нового пользователя
async def add_new_user(user_id, username, first_name, last_name, date_joined):
    async with aiosqlite.connect('reviews.db') as db:
        try:
            await db.execute('''
                INSERT INTO users (user_id, username, first_name, last_name, date_joined)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, date_joined))
            await db.commit()
        except aiosqlite.IntegrityError:
            # Если такой пользователь уже существует (user_id уникален), ничего не делаем
            pass

# Функция для проверки, является ли пользователь новым
async def is_new_user(user_id):
    async with aiosqlite.connect('reviews.db') as db:
        async with db.execute('SELECT COUNT(*) FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] == 0

# Функция для добавления нового отзыва с возвратом review_id
async def add_review(user_id, username, company_name, rating, comment, date, language):
    async with aiosqlite.connect('reviews.db') as db:
        cursor = await db.execute('''
            INSERT INTO reviews (user_id, username, company_name, rating, comment, date, status, language)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, company_name, rating, comment, date, "pending", language))
        await db.commit()
        return cursor.lastrowid

# Функция для получения подтвержденных отзывов по названию компании
async def get_reviews_by_company(company_name):
    async with aiosqlite.connect('reviews.db') as db:
        async with db.execute('''
            SELECT company_name, rating, comment, date FROM reviews
            WHERE LOWER(company_name) LIKE ? AND status = "approved"
        ''', (f'%{company_name}%',)) as cursor:
            reviews = await cursor.fetchall()
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

# Функция для получения user_id по review_id
async def get_user_id_by_review_id(review_id):
    async with aiosqlite.connect('reviews.db') as db:
        async with db.execute('SELECT user_id FROM reviews WHERE id = ?', (review_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

# Функция для получения языка по review_id
async def get_language_by_review_id(review_id):
    async with aiosqlite.connect('reviews.db') as db:
        async with db.execute('SELECT language FROM reviews WHERE id = ?', (review_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "Русский"

# Функция для обновления статуса отзыва (например, "approved" или "declined")
async def update_review_status(review_id, status):
    async with aiosqlite.connect('reviews.db') as db:
        await db.execute('UPDATE reviews SET status = ? WHERE id = ?', (status, review_id))
        await db.commit()

# Функция для удаления отзыва
async def delete_review(review_id):
    async with aiosqlite.connect('reviews.db') as db:
        await db.execute('DELETE FROM reviews WHERE id = ?', (review_id,))
        await db.commit()