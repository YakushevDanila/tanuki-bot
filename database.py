import aiosqlite
import psycopg2
import psycopg2.extras
import os
from config import DATABASE_URL, SQLITE_PATH


async def init_db():
    """Создание таблиц при запуске"""
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE,
            name TEXT
        );
        CREATE TABLE IF NOT EXISTS shifts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            date TEXT,
            start_time TEXT,
            end_time TEXT,
            revenue REAL DEFAULT 0,
            tips REAL DEFAULT 0,
            hours REAL DEFAULT 0,
            filled INTEGER DEFAULT 0
        );
        """)
        conn.commit()
        cur.close()
        conn.close()
    else:
        async with aiosqlite.connect(SQLITE_PATH) as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                name TEXT
            )""")
            await db.execute("""
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT,
                start_time TEXT,
                end_time TEXT,
                revenue REAL DEFAULT 0,
                tips REAL DEFAULT 0,
                hours REAL DEFAULT 0,
                filled INTEGER DEFAULT 0
            )""")
            await db.commit()


async def add_user(telegram_id, name):
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()
        cur.execute("INSERT INTO users (telegram_id, name) VALUES (%s, %s) ON CONFLICT (telegram_id) DO NOTHING",
                    (telegram_id, name))
        conn.commit()
        cur.close()
        conn.close()
    else:
        async with aiosqlite.connect(SQLITE_PATH) as db:
            await db.execute("INSERT OR IGNORE INTO users (telegram_id, name) VALUES (?, ?)", (telegram_id, name))
            await db.commit()


async def add_shift(user_id, date, start, end):
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()
        cur.execute("INSERT INTO shifts (user_id, date, start_time, end_time) VALUES (%s, %s, %s, %s)",
                    (user_id, date, start, end))
        conn.commit()
        cur.close()
        conn.close()
    else:
        async with aiosqlite.connect(SQLITE_PATH) as db:
            await db.execute("INSERT INTO shifts (user_id, date, start_time, end_time) VALUES (?, ?, ?, ?)",
                             (user_id, date, start, end))
            await db.commit()


async def get_shifts_for_date(user_id, date):
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM shifts WHERE user_id=%s AND date=%s", (user_id, date))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    else:
        async with aiosqlite.connect(SQLITE_PATH) as db:
            cursor = await db.execute("SELECT * FROM shifts WHERE user_id=? AND date=?", (user_id, date))
            return await cursor.fetchall()


async def update_shift_data(user_id, date, revenue, tips, hours):
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        cur = conn.cursor()
        cur.execute("""
            UPDATE shifts
            SET revenue=%s, tips=%s, hours=%s, filled=1
            WHERE user_id=%s AND date=%s
        """, (revenue, tips, hours, user_id, date))
        conn.commit()
        cur.close()
        conn.close()
    else:
        async with aiosqlite.connect(SQLITE_PATH) as db:
            await db.execute("""
                UPDATE shifts
                SET revenue=?, tips=?, hours=?, filled=1
                WHERE user_id=? AND date=?""", (revenue, tips, hours, user_id, date))
            await db.commit()
