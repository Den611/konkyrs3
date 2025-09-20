import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from deep_translator import GoogleTranslator
import random

TOKEN = "8401955026:AAFsdWHwIJl-Eee7DEj1KjJMlXCwsMGdP4w"
bot = Bot(token=TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("words.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    start_date TEXT,
    last_active TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_words (
    user_id INTEGER,
    word TEXT,
    translation TEXT,
    usage_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, word)
)
""")
conn.commit()

main_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="/add_word"), types.KeyboardButton(text="/all_words")],
        [types.KeyboardButton(text="/practice"), types.KeyboardButton(text="/delete_word")],
        [types.KeyboardButton(text="/exit")]
    ],
    resize_keyboard=True
)

class AddWord(StatesGroup):
    waiting_for_word = State()

class DeleteWord(StatesGroup):
    waiting_for_word = State()

class PracticeWord(StatesGroup):
    waiting_for_answer = State()

COMMANDS_TEXT = (
    "Доступні команди:\n"
    "/add_word – додати нове слово\n"
    "/delete_word – видалити слово\n"
    "/all_words – список усіх слів\n"
    "/practice – тренування\n"
    "/exit – вихід з режиму"
)

def add_user(user_id, username):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username, start_date, last_active) VALUES (?, ?, ?, ?)",
        (user_id, username, datetime.now().isoformat(), datetime.now().isoformat())
    )
    conn.commit()

def update_last_active(user_id):
    cursor.execute(
        "UPDATE users SET last_active=? WHERE user_id=?",
        (datetime.now().isoformat(), user_id)
    )
    conn.commit()

def add_word_to_db(user_id, word, translation):
    cursor.execute("SELECT 1 FROM user_words WHERE user_id=? AND word=?", (user_id, word))
    exists = cursor.fetchone()
    if exists:
        return False
    cursor.execute("INSERT INTO user_words (user_id, word, translation, usage_count) VALUES (?, ?, ?, 0)",
                   (user_id, word, translation))
    conn.commit()
    return True

def delete_word_from_db(user_id, word):
    cursor.execute("DELETE FROM user_words WHERE user_id=? AND word=?", (user_id, word))
    conn.commit()

def get_user_words(user_id):
    cursor.execute("SELECT word, translation FROM user_words WHERE user_id=?", (user_id,))
    return cursor.fetchall()

def increment_usage_count(user_id, word):
    cursor.execute("UPDATE user_words SET usage_count = usage_count + 1 WHERE user_id=? AND word=?", (user_id, word))
    conn.commit()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    add_user(message.from_user.id, message.from_user.username)
    update_last_active(message.from_user.id)
    await state.clear()
    await message.answer(f"Привіт\nЯ словниковий бот.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)

@dp.message(Command("exit"))
async def cmd_exit(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    await state.clear()
    await message.answer(f"Ви вийшли з режиму.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)

@dp.message(Command("add_word"))
async def cmd_add_word(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    await state.set_state(AddWord.waiting_for_word)
    await message.answer("Введіть слово (або /exit щоб вийти):", reply_markup=main_kb)

@dp.message(AddWord.waiting_for_word)
async def process_word(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    word = message.text.strip()
    user_id = message.from_user.id

    if word.startswith("/"):
        await state.clear()
        await message.answer(f"Ви вийшли з режиму.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)
        return

    try:
        translation = GoogleTranslator(source="auto", target="uk").translate(word)
        if not translation or translation.lower() == word.lower():
            translation = word
        added = add_word_to_db(user_id, word, translation)
        if not added:
            await message.answer(f"Молодець! Слово '{word}' вже є у вашому словнику.", reply_markup=main_kb)
        else:
            await message.answer(f"Додано слово!\n{word} — {translation}\n\nВведіть нове слово (або /exit).", reply_markup=main_kb)
    except Exception:
        await message.answer("Не вдалося знайти переклад. Спробуйте ще раз.", reply_markup=main_kb)

@dp.message(Command("delete_word"))
async def cmd_delete_word(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    await state.set_state(DeleteWord.waiting_for_word)
    await message.answer("Введіть слово для видалення (або /exit):", reply_markup=main_kb)

@dp.message(DeleteWord.waiting_for_word)
async def process_delete_word(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    word = message.text.strip()
    user_id = message.from_user.id

    if word.startswith("/"):
        await state.clear()
        await message.answer(f"Ви вийшли з режиму.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)
        return

    words = dict(get_user_words(user_id))
    if word in words:
        delete_word_from_db(user_id, word)
        await message.answer(f"Слово '{word}' видалено.\n\nВведіть нове слово для видалення (або /exit).", reply_markup=main_kb)
    else:
        await message.answer(f"Слова '{word}' немає в словнику.\n\nВведіть інше слово (або /exit).", reply_markup=main_kb)

@dp.message(Command("all_words"))
async def cmd_all_words(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    await state.clear()
    words = get_user_words(message.from_user.id)
    if words:
        text = "Список слів:\n"
        for w, t in words:
            text += f"{w} — {t}\n"
    else:
        text = "Словник порожній."
    await message.answer(text, reply_markup=main_kb)

@dp.message(Command("practice"))
async def cmd_practice(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    user_id = message.from_user.id
    words = get_user_words(user_id)
    if not words:
        await message.answer("Ваш словник порожній. Додайте слова через /add_word.", reply_markup=main_kb)
        return
    # Обираємо випадкове слово
    word, translation = random.choice(words)
    await state.update_data(current_word=word, current_translation=translation, previous_word=None)
    await state.set_state(PracticeWord.waiting_for_answer)
    await message.answer(f"Введіть переклад слова: {translation}", reply_markup=main_kb)

@dp.message(PracticeWord.waiting_for_answer)
async def process_practice(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    user_data = await state.get_data()
    correct_word = user_data.get("current_word")
    translation = user_data.get("current_translation")
    previous_word = user_data.get("previous_word")
    user_id = message.from_user.id
    answer = message.text.strip()

    if answer.startswith("/"):
        await state.clear()
        await message.answer(f"Ви вийшли з режиму.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)
        return

    if answer.lower() == correct_word.lower():
        increment_usage_count(user_id, correct_word)
        await message.answer(f"Правильно! {translation} = {correct_word}\nЩе одне слово?")
    else:
        await message.answer(f"Неправильно. Спробуйте інше слово.")

    # Вибір наступного слова, щоб воно не було тим самим
    words = get_user_words(user_id)
    next_word_pair = None
    available_words = [w for w in words if w[0] != correct_word]
    if available_words:
        next_word_pair = random.choice(available_words)
    elif words:
        next_word_pair = (correct_word, translation)

    if next_word_pair:
        next_word, next_translation = next_word_pair
        await state.update_data(current_word=next_word, current_translation=next_translation, previous_word=correct_word)
        await message.answer(f"Введіть переклад слова: {next_translation}", reply_markup=main_kb)
    else:
        await state.clear()
        await message.answer("Більше слів для практики немає. Додайте нові через /add_word.", reply_markup=main_kb)

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
