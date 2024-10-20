import aiosqlite

# Инициализация базы данных для пользователей
async def init_users_db():
    async with aiosqlite.connect('users.db') as db:
        # Создание таблицы для пользователей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                first_name TEXT,
                date_joined TEXT
            )
        ''')
        await db.commit()

# Функция для добавления нового пользователя в базу данных
async def add_new_user(user_id, first_name, date_joined):
    async with aiosqlite.connect('users.db') as db:
        try:
            await db.execute('''
                INSERT INTO users (user_id, first_name, date_joined)
                VALUES (?, ?, ?)
            ''', (user_id, first_name, date_joined))
            await db.commit()
        except aiosqlite.IntegrityError:
            # Если такой пользователь уже существует (user_id уникален), ничего не делаем
            pass

# Функция для проверки, является ли пользователь новым
async def is_new_user(user_id):
    async with aiosqlite.connect('users.db') as db:
        async with db.execute('SELECT COUNT(*) FROM users WHERE user_id = ?', (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] == 0