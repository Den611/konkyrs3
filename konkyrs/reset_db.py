import sqlite3
import os

DB_FILE = "words.db"

# Видаляємо стару базу
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
    print("Стара база видалена.")

# Створюємо нову базу
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Таблиця користувачів
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    start_date TEXT,
    last_active TEXT
)
""")

# Таблиця слів
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_words (
    user_id INTEGER,
    word TEXT,
    translation TEXT,
    language TEXT,
    usage_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, word, language)
)
""")

conn.commit()
conn.close()

print("Нова база даних створена.")
