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

# --- Створення таблиць ---
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
    language TEXT,
    usage_count INTEGER DEFAULT 0,
    PRIMARY KEY(user_id, word, language)
)
""")
conn.commit()

# --- Клавіатура головного меню ---
main_kb = types.ReplyKeyboardMarkup(
    keyboard=[
        [types.KeyboardButton(text="/add_word"), types.KeyboardButton(text="/all_words")],
        [types.KeyboardButton(text="/practice"), types.KeyboardButton(text="/delete_word")],
        [types.KeyboardButton(text="/stats"), types.KeyboardButton(text="/word_of_day")],
        [types.KeyboardButton(text="/exit")]
    ],
    resize_keyboard=True
)

# --- FSM ---
class AddWord(StatesGroup):
    waiting_for_word = State()
    waiting_for_language = State()

class DeleteWord(StatesGroup):
    waiting_for_word = State()

class PracticeWord(StatesGroup):
    waiting_for_language = State()
    waiting_for_answer = State()

class ViewWords(StatesGroup):
    waiting_for_language = State()

COMMANDS_TEXT = (
    "Доступні команди:\n"
    "/add_word – додати нове слово 📚\n"
    "/delete_word – видалити слово ❌\n"
    "/all_words – список усіх слів 📝\n"
    "/practice – тренування 🎯\n"
    "/stats – ваша статистика 📊\n"
    "/word_of_day – слово дня 🌟\n"
    "/exit – вихід з режиму 🚪"
)

SUPPORTED_LANGUAGES = ["English", "German", "French", "Polish", "Spanish", "Italian"]

# --- DB functions ---
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

def add_word_to_db(user_id, word, translation, language):
    try:
        cursor.execute("SELECT 1 FROM user_words WHERE user_id=? AND word=? AND language=?", (user_id, word, language))
        if cursor.fetchone():
            return False
        cursor.execute(
            "INSERT INTO user_words (user_id, word, translation, language, usage_count) VALUES (?, ?, ?, ?, 0)",
            (user_id, word, translation, language)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def delete_word_from_db(user_id, word):
    cursor.execute("DELETE FROM user_words WHERE user_id=? AND word=?", (user_id, word))
    conn.commit()

def get_user_words(user_id, language=None):
    if language is None:
        cursor.execute("SELECT word, translation, language, usage_count FROM user_words WHERE user_id=?", (user_id,))
    else:
        cursor.execute("SELECT word, translation, language, usage_count FROM user_words WHERE user_id=? AND language=?", (user_id, language))
    return cursor.fetchall()

def increment_usage_count(user_id, word, language=None):
    if language:
        cursor.execute("UPDATE user_words SET usage_count = usage_count + 1 WHERE user_id=? AND word=? AND language=?",
                       (user_id, word, language))
    else:
        cursor.execute("UPDATE user_words SET usage_count = usage_count + 1 WHERE user_id=? AND word=?", (user_id, word))
    conn.commit()

# --- Start/Exit ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    add_user(message.from_user.id, message.from_user.username)
    update_last_active(message.from_user.id)
    await state.clear()
    welcome_text = (
        "👋 Привіт!\nЯ ваш словниковий бот.\n\n"
        "Я допомагаю вивчати нові слова:\n"
        "- Додавай слова та їх переклад 📚\n"
        "- Видаляй слова ❌\n"
        "- Переглядай свій словник 📝\n"
        "- Практикуй переклади 🎯\n\n"
        f"{COMMANDS_TEXT}"
    )
    await message.answer(welcome_text, reply_markup=main_kb)

@dp.message(Command("exit"))
async def cmd_exit(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    await state.clear()
    await message.answer(f"🚪 Ви вийшли з режиму.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)

# --- Add Word ---
@dp.message(Command("add_word"))
async def cmd_add_word(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    await state.set_state(AddWord.waiting_for_word)
    await message.answer("✏️ Введіть слово для додавання (або /exit):", reply_markup=main_kb)

@dp.message(AddWord.waiting_for_word)
async def process_word(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    text = message.text.strip()
    user_id = message.from_user.id

    if text.startswith("/"):
        await state.clear()
        await message.answer(f"🚪 Ви вийшли або переключили команду.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)
        return

    word = text
    await state.update_data(word=word)

    keyboard = [[types.KeyboardButton(text=l)] for l in SUPPORTED_LANGUAGES]
    keyboard.append([types.KeyboardButton(text="/exit")])
    lang_kb = types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

    await state.set_state(AddWord.waiting_for_language)
    await message.answer("🌍 Оберіть мову слова:", reply_markup=lang_kb)

@dp.message(AddWord.waiting_for_language)
async def process_language(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    language = message.text.strip()
    user_id = message.from_user.id

    if language.startswith("/"):
        await state.clear()
        await message.answer(f"🚪 Ви вийшли або переключили команду.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)
        return

    if language not in SUPPORTED_LANGUAGES:
        await message.answer("❌ Невідома мова. Виберіть зі списку або /exit.")
        return

    data = await state.get_data()
    word = data.get("word")

    try:
        translator = GoogleTranslator(source=language.lower(), target="uk")
        translation = translator.translate(word)
    except Exception:
        translation = word

    added = add_word_to_db(user_id, word, translation, language)

    if not added:
        await message.answer(f"⚠️ Слово '{word}' вже є у вашому словнику ({translation}, {language}).", reply_markup=main_kb)
    else:
        await message.answer(f"✅ Додано: {word} — {translation} ({language})\nВведіть нове слово або /exit.", reply_markup=main_kb)

    await state.set_state(AddWord.waiting_for_word)

# --- Delete Word ---
@dp.message(Command("delete_word"))
async def cmd_delete_word(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    await state.set_state(DeleteWord.waiting_for_word)
    await message.answer("🗑️ Введіть слово для видалення (або /exit):", reply_markup=main_kb)

@dp.message(DeleteWord.waiting_for_word)
async def process_delete_word(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    text = message.text.strip()
    user_id = message.from_user.id

    if text.startswith("/"):
        await state.clear()
        await message.answer(f"🚪 Ви вийшли або переключили команду.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)
        return

    words = dict([(w, t) for w, t, l, u in get_user_words(user_id)])
    if text in words:
        delete_word_from_db(user_id, text)
        await message.answer(f"🗑️ Слово '{text}' видалено.", reply_markup=main_kb)
    else:
        await message.answer(f"❌ Слова '{text}' немає в словнику.", reply_markup=main_kb)

# --- View All Words ---
@dp.message(Command("all_words"))
async def cmd_all_words(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    user_id = message.from_user.id
    words = get_user_words(user_id)
    if not words:
        await message.answer("📭 Ваш словник порожній.", reply_markup=main_kb)
        return

    languages = sorted(list(set([l for _, _, l, _ in words if l is not None])))
    if not languages:
        languages = ["Unknown"]

    keyboard = [[types.KeyboardButton(text=l)] for l in languages]
    keyboard.append([types.KeyboardButton(text="Усі мови")])
    keyboard.append([types.KeyboardButton(text="/exit")])
    lang_kb = types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

    await state.set_state(ViewWords.waiting_for_language)
    await message.answer("🌐 Оберіть мову, щоб переглянути слова:", reply_markup=lang_kb)

@dp.message(ViewWords.waiting_for_language)
async def process_view_language(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang_choice = message.text.strip()

    if lang_choice.startswith("/"):
        await state.clear()
        await message.answer(f"🚪 Ви вийшли або переключили команду.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)
        return

    if lang_choice == "Усі мови":
        words = get_user_words(user_id)
    else:
        words = get_user_words(user_id, language=lang_choice)

    if not words:
        await message.answer("📭 Словник порожній для цієї мови.", reply_markup=main_kb)
    else:
        text = f"📝 Слова ({lang_choice}):\n"
        for w, t, l, u in words:
            text += f"{w} — {t} (мова: {l})\n"
        await message.answer(text, reply_markup=main_kb)

    await state.clear()

# --- Practice ---
@dp.message(Command("practice"))
async def cmd_practice(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    user_id = message.from_user.id
    words = get_user_words(user_id)
    if not words:
        await message.answer("📭 Ваш словник порожній. Додайте слова через /add_word.", reply_markup=main_kb)
        return

    languages = sorted(list(set([l for _, _, l, _ in words if l is not None])))
    keyboard = [[types.KeyboardButton(text=l)] for l in languages]
    keyboard.append([types.KeyboardButton(text="Усі мови")])
    keyboard.append([types.KeyboardButton(text="/exit")])
    lang_kb = types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

    await state.update_data(all_practice_words=words)
    await state.set_state(PracticeWord.waiting_for_language)
    await message.answer("🎯 Оберіть мову для практики (або 'Усі мови'):", reply_markup=lang_kb)

@dp.message(PracticeWord.waiting_for_language)
async def practice_choose_lang(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    text = message.text.strip()
    user_id = message.from_user.id

    if text.startswith("/"):
        await state.clear()
        await message.answer(f"🚪 Ви вийшли або переключили команду.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)
        return

    data = await state.get_data()
    all_words = data.get("all_practice_words", [])

    if text == "Усі мови":
        practice_list = [(w, t, l, u) for w, t, l, u in all_words]
    else:
        practice_list = [(w, t, l, u) for w, t, l, u in all_words if l == text]

    if not practice_list:
        await message.answer("📭 Немає слів для цієї мови.", reply_markup=main_kb)
        await state.clear()
        return

    random.shuffle(practice_list)
    await state.update_data(practice_list=practice_list, practice_index=0, practice_lang=text)
    await state.set_state(PracticeWord.waiting_for_answer)

    w, t, l, u = practice_list[0]
    await message.answer(f"✏️ Введіть слово для перекладу: {t} (мова: {l})", reply_markup=main_kb)

@dp.message(PracticeWord.waiting_for_answer)
async def process_practice(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    user_id = message.from_user.id
    data = await state.get_data()
    practice_list = data.get("practice_list", [])
    idx = data.get("practice_index", 0)
    practice_lang = data.get("practice_lang", None)

    if not practice_list:
        await state.clear()
        await message.answer("📭 Немає слів для практики.", reply_markup=main_kb)
        return

    text = message.text.strip()
    if text.startswith("/"):
        await state.clear()
        await message.answer(f"🚪 Ви вийшли або переключили команду.\n\n{COMMANDS_TEXT}", reply_markup=main_kb)
        return

    correct_word = practice_list[idx][0]
    correct_translation = practice_list[idx][1]
    correct_language = practice_list[idx][2]

    if text.lower() == correct_word.lower():
        increment_usage_count(user_id, correct_word, correct_language)
        await message.answer(f"✅ Правильно! {correct_translation} = {correct_word} 🎉", reply_markup=main_kb)
    else:
        await message.answer(f"❌ Неправильно. Правильне слово: {correct_word} 📚", reply_markup=main_kb)

    idx += 1
    if idx >= len(practice_list):
        await state.clear()
        await message.answer("🏁 Практика завершена. Додайте нові слова або оберіть інший режим.", reply_markup=main_kb)
        return
    else:
        await state.update_data(practice_index=idx)
        next_w, next_t, next_l, next_u = practice_list[idx]
        await message.answer(f"✏️ Введіть переклад слова: {next_t} (мова: {next_l})", reply_markup=main_kb)

# --- User statistics ---
@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    user_id = message.from_user.id
    words = get_user_words(user_id)
    total_words = len(words)
    total_correct = sum([u for w, t, l, u in words])
    level = total_correct // 10 + 1
    await message.answer(
        f"📊 Статистика користувача:\n"
        f"- Кількість слів у словнику: {total_words}\n"
        f"- Правильних відповідей: {total_correct}\n"
        f"- Ваш рівень: {level} 🏆",
        reply_markup=main_kb
    )

# --- Word of the day ---
@dp.message(Command("word_of_day"))
async def cmd_word_of_day(message: types.Message):
    user_id = message.from_user.id
    words = get_user_words(user_id)
    if not words:
        await message.answer("📭 Ваш словник порожній. Додайте слова через /add_word.", reply_markup=main_kb)
        return
    word, translation, language, usage = random.choice(words)
    await message.answer(
        f"🌟 Слово дня:\n{word} — {translation} ({language})\n"
        f"Спробуйте його запам’ятати та потренуватися!",
        reply_markup=main_kb
    )

# --- User level ---
def get_user_level(user_id):
    words = get_user_words(user_id)
    total_correct = sum([u for w, t, l, u in words])
    level = total_correct // 10 + 1
    return level

# --- Word of the day ---
@dp.message(Command("word_of_day"))
async def cmd_word_of_day(message: types.Message):
    user_id = message.from_user.id
    words = get_user_words(user_id)
    if not words:
        await message.answer("📭 Ваш словник порожній. Додайте слова через /add_word.", reply_markup=main_kb)
        return
    word, translation, language, usage = random.choice(words)
    await message.answer(
        f"🌟 Слово дня:\n{word} — {translation} ({language})\n"
        f"Спробуйте його запам’ятати та потренуватися!",
        reply_markup=main_kb
    )

# --- Practice with level-based count ---
@dp.message(Command("practice"))
async def cmd_practice(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    user_id = message.from_user.id
    words = get_user_words(user_id)
    if not words:
        await message.answer("📭 Ваш словник порожній. Додайте слова через /add_word.", reply_markup=main_kb)
        return

    level = get_user_level(user_id)
    practice_count = min(len(words), 5 + level)  # більше слів з вищим рівнем
    practice_list = random.sample(words, practice_count)

    await state.update_data(practice_list=practice_list, practice_index=0)
    await state.set_state(PracticeWord.waiting_for_answer)

    w, t, l, u = practice_list[0]
    await message.answer(f"🎯 Переклад слова: {t} (мова: {l})", reply_markup=main_kb)

@dp.message(PracticeWord.waiting_for_answer)
async def process_practice(message: types.Message, state: FSMContext):
    update_last_active(message.from_user.id)
    text = message.text.strip()
    user_id = message.from_user.id
    data = await state.get_data()
    practice_list = data.get("practice_list", [])
    idx = data.get("practice_index", 0)

    if not practice_list:
        await state.clear()
        await message.answer("📭 Немає слів для практики.", reply_markup=main_kb)
        return

    correct_word = practice_list[idx][0]
    correct_translation = practice_list[idx][1]
    correct_language = practice_list[idx][2]

    if text.lower() == correct_word.lower():
        increment_usage_count(user_id, correct_word, correct_language)
        await message.answer(f"✅ Правильно! {correct_translation} = {correct_word} 🎉", reply_markup=main_kb)
    else:
        await message.answer(f"❌ Неправильно. Правильне слово: {correct_word} 📚", reply_markup=main_kb)

    idx += 1
    if idx >= len(practice_list):
        await state.clear()
        await message.answer("🏁 Практика завершена. Додайте нові слова або оберіть інший режим.", reply_markup=main_kb)
    else:
        await state.update_data(practice_index=idx)
        next_w, next_t, next_l, next_u = practice_list[idx]
        await message.answer(f"🎯 Переклад слова: {next_t} (мова: {next_l})", reply_markup=main_kb)

# --- Polling ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
