from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler,
)
from dotenv import load_dotenv
import os
import psycopg2
import json
import re
from gemini_client import GeminiClient

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Gemini AI client
gemini = GeminiClient()

# Conversation states
WAITING_NAME = 0


# ============ Database Helpers ============

def init_db():
    """Database va jadvallarni yaratish (agar mavjud bo'lmasa)"""
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            center_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            telegram_id TEXT UNIQUE NOT NULL,
            teacher_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id SERIAL PRIMARY KEY,
            teacher_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            level TEXT NOT NULL,
            questions TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL,
            test_id INTEGER NOT NULL,
            score_percent INTEGER NOT NULL,
            answers TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (test_id) REFERENCES tests(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS homeworks (
            id SERIAL PRIMARY KEY,
            teacher_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            level TEXT NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS homework_results (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL,
            homework_id INTEGER NOT NULL,
            image_path TEXT,
            ai_feedback TEXT,
            score_percent INTEGER,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (homework_id) REFERENCES homeworks(id)
        )
    """)
    conn.commit()
    conn.close()

# Database yaratish
init_db()

def get_db():
    return psycopg2.connect(os.getenv('DATABASE_URL'))


def get_teacher_by_id(teacher_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM teachers WHERE id = %s", (teacher_id,))
    teacher = cursor.fetchone()
    conn.close()
    return teacher


def get_student_by_telegram_id(telegram_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM students WHERE telegram_id = %s", (telegram_id,))
    student = cursor.fetchone()
    conn.close()
    return student


def create_student(name, telegram_id, teacher_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO students (name, telegram_id, teacher_id) VALUES (%s, %s, %s)",
        (name, telegram_id, teacher_id),
    )
    conn.commit()
    conn.close()


def get_tests_for_student(telegram_id):
    """O'quvchining teacher_id si orqali barcha testlarni olish"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT t.id, t.topic, t.level FROM tests t "
        "JOIN students s ON s.teacher_id = t.teacher_id "
        "WHERE s.telegram_id = %s", (telegram_id,))
    tests = cursor.fetchall()
    conn.close()
    return tests


def get_test_questions(test_id):
    """Test savollarini JSON sifatida olish"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT questions FROM tests WHERE id = %s", (test_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None


def save_test_result(student_id, test_id, score_percent, answers_json):
    """Test natijasini saqlash"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO test_results (student_id, test_id, score_percent, answers) VALUES (%s, %s, %s, %s)",
        (student_id, test_id, score_percent, answers_json))
    conn.commit()
    conn.close()


def get_active_homework_for_student(telegram_id):
    """O'quvchining teacher_id si orqali eng oxirgi vazifani olish"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT h.id, h.title, h.description, h.level FROM homeworks h "
        "JOIN students s ON s.teacher_id = h.teacher_id "
        "WHERE s.telegram_id = %s "
        "ORDER BY h.assigned_at DESC LIMIT 1", (telegram_id,))
    homework = cursor.fetchone()
    conn.close()
    return homework


def save_homework_result(student_id, homework_id, ai_feedback, score_percent):
    """Homework natijasini saqlash"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO homework_results (student_id, homework_id, ai_feedback, score_percent) "
        "VALUES (%s, %s, %s, %s)",
        (student_id, homework_id, ai_feedback, score_percent))
    conn.commit()
    conn.close()


# ============ Handlers ============

async def start(update, context):
    telegram_id = str(update.effective_user.id)

    # Check if user is already registered
    student = get_student_by_telegram_id(telegram_id)
    if student:
        await update.message.reply_text("Siz allaqachon ro'yxatdan o'tgansiz!")
        return ConversationHandler.END

    # Check if args contain teacher_<id>
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("teacher_"):
            try:
                teacher_id = int(arg.replace("teacher_", ""))
            except ValueError:
                await update.message.reply_text(
                    "Kechirasiz, bu o'qituvchi topilmadi."
                )
                return ConversationHandler.END

            # Check if teacher exists
            teacher = get_teacher_by_id(teacher_id)
            if not teacher:
                await update.message.reply_text(
                    "Kechirasiz, bu o'qituvchi topilmadi."
                )
                return ConversationHandler.END

            # Store teacher info in user_data for later use
            context.user_data['teacher_id'] = teacher_id
            context.user_data['teacher_name'] = teacher[1]

            await update.message.reply_text(
                "Assalomu alaykum! EduCore tizimiga xush kelibsiz!\n"
                "Iltimos, ismingizni yuboring:"
            )
            return WAITING_NAME

    # No args or invalid args - show default message
    await update.message.reply_text(
        "Salom! Men EduCore botiman. "
        "O'qituvchingiz bergan havola orqali ro'yxatdan o'ting."
    )
    return ConversationHandler.END


async def receive_name(update, context):
    name = update.message.text.strip()
    telegram_id = str(update.effective_user.id)
    teacher_id = context.user_data.get('teacher_id')
    teacher_name = context.user_data.get('teacher_name')

    # Create student in database
    create_student(name, telegram_id, teacher_id)

    await update.message.reply_text(
        f"Xush kelibsiz! Siz {teacher_name} ustoz ga birikdingiz! \U0001f389"
    )

    # Clear user_data
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update, context):
    context.user_data.clear()
    await update.message.reply_text("Bekor qilindi.")
    return ConversationHandler.END


# ============ Test Runner Handlers ============

async def test_command(update, context):
    """O'quvchiga tegishli testlar ro'yxatini ko'rsatish"""
    telegram_id = str(update.effective_user.id)

    # O'quvchi ro'yxatdan o'tganligini tekshirish
    student = get_student_by_telegram_id(telegram_id)
    if not student:
        await update.message.reply_text(
            "Siz hali ro'yxatdan o'tmagansiz. /start buyrug'ini yuboring."
        )
        return

    # O'quvchiga tegishli testlarni olish
    tests = get_tests_for_student(telegram_id)

    if not tests:
        await update.message.reply_text("Hozircha sizga test berilmagan.")
        return

    # Inline keyboard yaratish
    keyboard = []
    for test in tests:
        test_id, topic, level = test
        button_text = f"{topic} ({level})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"test_{test_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Mavjud testlar ro'yxati. Birini tanlang:",
        reply_markup=reply_markup
    )


async def test_select_callback(update, context):
    """Test tanlash callback - savollarni yuklash va birinchi savolni ko'rsatish"""
    query = update.callback_query
    await query.answer()

    telegram_id = str(update.effective_user.id)

    # Test ID ni olish
    test_id = int(query.data.replace("test_", ""))

    # Savollarni olish
    questions = get_test_questions(test_id)
    if not questions:
        await query.edit_message_text("Bu testda savollar topilmadi.")
        return

    # O'quvchi ma'lumotlarini olish
    student = get_student_by_telegram_id(telegram_id)

    # Batch loading - barcha ma'lumotlarni context.user_data ga saqlash
    context.user_data['questions'] = questions
    context.user_data['current_q'] = 0
    context.user_data['correct_count'] = 0
    context.user_data['test_id'] = test_id
    context.user_data['answers'] = []
    context.user_data['student_id'] = student[0]

    # Birinchi savolni ko'rsatish
    await show_question(query, context)


async def show_question(query, context):
    """Joriy savolni inline keyboard bilan ko'rsatish"""
    questions = context.user_data['questions']
    current_q = context.user_data['current_q']
    total = len(questions)

    question_data = questions[current_q]
    question_text = question_data['question']
    options = question_data['options']

    # Savol matni formati
    text = (
        f"\U0001f4dd Savol {current_q + 1}/{total}:\n"
        f"{question_text}\n\n"
        f"A) {options['A']}\n"
        f"B) {options['B']}\n"
        f"C) {options['C']}\n"
        f"D) {options['D']}"
    )

    # Inline keyboard
    keyboard = [
        [InlineKeyboardButton("A", callback_data="answer_A"),
         InlineKeyboardButton("B", callback_data="answer_B")],
        [InlineKeyboardButton("C", callback_data="answer_C"),
         InlineKeyboardButton("D", callback_data="answer_D")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=text, reply_markup=reply_markup)


async def answer_callback(update, context):
    """Javob qayta ishlash - to'g'ri/noto'g'ri tekshirish"""
    query = update.callback_query
    await query.answer()

    # Javob ma'lumotlarini tekshirish
    if 'questions' not in context.user_data:
        await query.edit_message_text("Test topilmadi. /test buyrug'ini qaytadan yuboring.")
        return

    # Tanlangan javob
    selected = query.data.replace("answer_", "")

    questions = context.user_data['questions']
    current_q = context.user_data['current_q']
    question_data = questions[current_q]
    correct = question_data['correct']

    # Javobni saqlash
    context.user_data['answers'].append(selected)

    # To'g'ri yoki noto'g'ri
    if selected == correct:
        context.user_data['correct_count'] += 1
        result_text = "\u2705 To'g'ri!"
    else:
        explanation = question_data.get('explanation', '')
        result_text = f"\u274c Noto'g'ri! To'g'ri javob: {correct}"
        if explanation:
            result_text += f"\n{explanation}"

    # Keyingi savolga o'tish
    context.user_data['current_q'] += 1

    if context.user_data['current_q'] < len(questions):
        # Natijani ko'rsatib, keyingi savolga o'tish
        await query.edit_message_text(text=result_text)
        # Keyingi savolni yangi xabar sifatida yuborish
        total = len(questions)
        next_q = context.user_data['current_q']
        next_question = questions[next_q]
        options = next_question['options']

        text = (
            f"\U0001f4dd Savol {next_q + 1}/{total}:\n"
            f"{next_question['question']}\n\n"
            f"A) {options['A']}\n"
            f"B) {options['B']}\n"
            f"C) {options['C']}\n"
            f"D) {options['D']}"
        )

        keyboard = [
            [InlineKeyboardButton("A", callback_data="answer_A"),
             InlineKeyboardButton("B", callback_data="answer_B")],
            [InlineKeyboardButton("C", callback_data="answer_C"),
             InlineKeyboardButton("D", callback_data="answer_D")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(text=text, reply_markup=reply_markup)
    else:
        # Test tugadi - natijani hisoblash
        correct_count = context.user_data['correct_count']
        total = len(questions)
        score_percent = round((correct_count / total) * 100)

        # Natijani DB ga saqlash
        student_id = context.user_data['student_id']
        test_id = context.user_data['test_id']
        answers_json = json.dumps(context.user_data['answers'])
        save_test_result(student_id, test_id, score_percent, answers_json)

        # Natijani ko'rsatish
        final_text = (
            f"{result_text}\n\n"
            f"Test tugadi! Natija: {correct_count}/{total} ({score_percent}%)"
        )
        await query.edit_message_text(text=final_text)

        # user_data ni tozalash
        context.user_data.clear()


# ============ Homework Checker Handlers ============

async def homework_command(update, context):
    """O'quvchiga tegishli eng oxirgi vazifani ko'rsatish"""
    telegram_id = str(update.effective_user.id)

    # O'quvchi ro'yxatdan o'tganligini tekshirish
    student = get_student_by_telegram_id(telegram_id)
    if not student:
        await update.message.reply_text(
            "Siz hali ro'yxatdan o'tmagansiz. /start buyrug'ini yuboring."
        )
        return

    # O'quvchiga tegishli eng oxirgi vazifani olish
    homework = get_active_homework_for_student(telegram_id)

    if not homework:
        await update.message.reply_text("Hozircha sizga uy vazifasi berilmagan.")
        return

    homework_id, title, description, level = homework

    # active_homework_id ni saqlash
    context.user_data['active_homework_id'] = homework_id

    await update.message.reply_text(
        f"\U0001f4da Vazifa: {title}\n"
        f"\U0001f4cb Tavsif: {description}\n"
        f"\U0001f4ca Daraja: {level}\n\n"
        f"\U0001f4f7 Bajarilgan vazifangiz rasmini yuboring!"
    )


async def handle_homework_photo(update, context):
    """O'quvchi yuborgan rasmni AI orqali tekshirish"""
    telegram_id = str(update.effective_user.id)

    # O'quvchi ro'yxatdan o'tganligini tekshirish
    student = get_student_by_telegram_id(telegram_id)
    if not student:
        await update.message.reply_text(
            "Siz hali ro'yxatdan o'tmagansiz. /start buyrug'ini yuboring."
        )
        return

    # active_homework_id mavjudligini tekshirish
    homework_id = context.user_data.get('active_homework_id')
    if not homework_id:
        await update.message.reply_text(
            "Avval /homework buyrug'ini yuboring va vazifani ko'ring."
        )
        return

    # Vazifa ma'lumotlarini olish
    homework = get_active_homework_for_student(telegram_id)
    if not homework:
        await update.message.reply_text("Vazifa topilmadi.")
        return

    homework_description = homework[2]  # description

    # Tekshirilmoqda xabarini yuborish
    await update.message.reply_text("\u23f3 Tekshirilmoqda...")

    # Rasmni yuklab olish
    photo = update.message.photo[-1]
    file = await photo.get_file()
    image_bytes = await file.download_as_bytearray()

    # Gemini AI orqali tekshirish
    try:
        feedback = gemini.check_homework(homework_description, bytes(image_bytes))
    except Exception as e:
        await update.message.reply_text(
            "Kechirasiz, tekshirishda xatolik yuz berdi. Keyinroq qayta urinib ko'ring."
        )
        return

    # AI feedback ni o'quvchiga yuborish
    await update.message.reply_text(f"\U0001f4dd Natija:\n\n{feedback}")

    # Foizni ajratib olish
    match = re.search(r'(\d+)%', feedback)
    if match:
        score_percent = int(match.group(1))
    else:
        score_percent = None

    # Natijani DB ga saqlash
    student_id = student[0]
    save_homework_result(student_id, homework_id, feedback, score_percent)

    # active_homework_id ni tozalash
    context.user_data.pop('active_homework_id', None)


# ============ Main ============

def main():
    app = Application.builder().token(TOKEN).build()

    # Conversation handler for onboarding
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)

    # Test runner handlers
    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(CallbackQueryHandler(test_select_callback, pattern="^test_"))
    app.add_handler(CallbackQueryHandler(answer_callback, pattern="^answer_"))

    # Homework checker handlers
    app.add_handler(CommandHandler("homework", homework_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_homework_photo))

    # run_polling() o'zi event loop yaratadi — asyncio.run() KERAK EMAS
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
