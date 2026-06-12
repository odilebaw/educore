from flask import Flask, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import json
import requests

from extensions import db, login_manager

load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///educore.db'

db.init_app(app)
login_manager.init_app(app)


from models import *
from gemini_client import GeminiClient
from pdf_generator import generate_test_pdf

gemini = GeminiClient()


@login_manager.user_loader
def load_user(user_id):
    return Teacher.query.get(int(user_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        center_name = request.form.get('center_name')

        existing_teacher = Teacher.query.filter_by(email=email).first()
        if existing_teacher:
            flash("Bu email allaqachon ro'yxatdan o'tgan.", 'danger')
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)
        new_teacher = Teacher(
            name=name,
            email=email,
            password_hash=password_hash,
            center_name=center_name
        )
        db.session.add(new_teacher)
        db.session.commit()

        flash("Ro'yxatdan muvaffaqiyatli o'tdingiz! Endi tizimga kiring.", 'success')
        return redirect(url_for('login'))

    return render_template('auth/register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        teacher = Teacher.query.filter_by(email=email).first()
        if teacher and check_password_hash(teacher.password_hash, password):
            login_user(teacher)
            flash('Tizimga muvaffaqiyatli kirdingiz!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Email yoki parol noto\'g\'ri.', 'danger')
            return redirect(url_for('login'))

    return render_template('auth/login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Tizimdan chiqdingiz.', 'success')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    students_count = len(current_user.students)
    tests_count = len(current_user.tests)

    # Oxirgi 5 ta test natijasi
    recent_results = TestResult.query.join(Student).filter(
        Student.teacher_id == current_user.id
    ).order_by(TestResult.completed_at.desc()).limit(5).all()

    # O'rtacha ball hisoblash
    all_results = TestResult.query.join(Student).filter(
        Student.teacher_id == current_user.id
    ).all()
    avg_score = 0
    if all_results:
        avg_score = round(sum(r.score_percent for r in all_results) / len(all_results), 1)

    invite_link = f"t.me/EduCoreBot?start=teacher_{current_user.id}"

    return render_template('dashboard/index.html',
                           students_count=students_count,
                           tests_count=tests_count,
                           avg_score=avg_score,
                           recent_results=recent_results,
                           invite_link=invite_link)


@app.route('/students')
@login_required
def students():
    student_list = current_user.students
    return render_template('dashboard/students.html', students=student_list)


@app.route('/results')
@login_required
def results():
    student_id = request.args.get('student_id', type=int)

    test_results_query = TestResult.query.join(Student).filter(
        Student.teacher_id == current_user.id
    )
    homework_results_query = HomeworkResult.query.join(Student).filter(
        Student.teacher_id == current_user.id
    )

    if student_id:
        test_results_query = test_results_query.filter(TestResult.student_id == student_id)
        homework_results_query = homework_results_query.filter(HomeworkResult.student_id == student_id)

    test_results = test_results_query.order_by(TestResult.completed_at.desc()).all()
    homework_results = homework_results_query.order_by(HomeworkResult.submitted_at.desc()).all()

    student_list = current_user.students
    selected_student_id = student_id

    return render_template('dashboard/results.html',
                           test_results=test_results,
                           homework_results=homework_results,
                           students=student_list,
                           selected_student_id=selected_student_id)


@app.route('/test/create', methods=['GET', 'POST'])
@login_required
def test_create():
    if request.method == 'POST':
        topic = request.form.get('topic')
        level = request.form.get('level')
        num_questions = request.form.get('num_questions', type=int)

        if not topic or not level or not num_questions:
            flash("Barcha maydonlarni to'ldiring.", 'danger')
            return redirect(url_for('test_create'))

        try:
            test_data = gemini.generate_test(topic, level, num_questions)
            questions_json = json.dumps(test_data['questions'])

            new_test = Test(
                teacher_id=current_user.id,
                topic=topic,
                level=level,
                questions=questions_json
            )
            db.session.add(new_test)
            db.session.commit()

            flash('Test muvaffaqiyatli yaratildi!', 'success')
            return redirect(url_for('test_preview', test_id=new_test.id))

        except Exception as e:
            flash(f'Test yaratishda xatolik yuz berdi: {str(e)}', 'danger')
            return redirect(url_for('test_create'))

    return render_template('dashboard/test_create.html')


@app.route('/test/<int:test_id>/preview')
@login_required
def test_preview(test_id):
    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id:
        flash("Sizda bu testni ko'rish huquqi yo'q.", 'danger')
        return redirect(url_for('dashboard'))

    questions = json.loads(test.questions)
    student_list = current_user.students
    return render_template('dashboard/test_preview.html',
                           test=test,
                           questions=questions,
                           students=student_list)


@app.route('/test/send', methods=['POST'])
@login_required
def test_send():
    test_id = request.form.get('test_id', type=int)
    student_ids = request.form.getlist('student_ids')

    if not test_id or not student_ids:
        flash("Test va o'quvchilarni tanlang.", 'danger')
        return redirect(url_for('test_preview', test_id=test_id))

    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id:
        flash("Sizda bu testni yuborish huquqi yo'q.", 'danger')
        return redirect(url_for('dashboard'))

    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    sent_count = 0

    for student_id in student_ids:
        student = Student.query.get(int(student_id))
        if student and student.teacher_id == current_user.id:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': student.telegram_id,
                    'text': "Yangi test tayyor! /test buyrug'ini bosing"
                }
                response = requests.post(url, json=payload)
                if response.status_code == 200:
                    sent_count += 1
            except Exception:
                continue

    flash(f"{sent_count} ta o'quvchiga test yuborildi.", 'success')
    return redirect(url_for('test_preview', test_id=test_id))


@app.route('/test/<int:test_id>/pdf')
@login_required
def test_pdf(test_id):
    test = Test.query.get_or_404(test_id)
    if test.teacher_id != current_user.id:
        flash("Sizda bu testni yuklab olish huquqi yo'q.", 'danger')
        return redirect(url_for('dashboard'))

    pdf_buffer = generate_test_pdf(test)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"test_{test.topic}_{test.level}.pdf",
        mimetype='application/pdf'
    )


@app.route('/homework/create', methods=['GET', 'POST'])
@login_required
def homework_create():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        level = request.form.get('level')

        if not title or not description or not level:
            flash("Barcha maydonlarni to'ldiring.", 'danger')
            return redirect(url_for('homework_create'))

        new_homework = Homework(
            teacher_id=current_user.id,
            title=title,
            description=description,
            level=level
        )
        db.session.add(new_homework)
        db.session.commit()

        # O'quvchilarga Telegram orqali xabar yuborish
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        sent_count = 0

        for student in current_user.students:
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    'chat_id': student.telegram_id,
                    'text': "Yangi uy vazifasi berildi! /homework buyrug'ini bosing"
                }
                response = requests.post(url, json=payload)
                if response.status_code == 200:
                    sent_count += 1
            except Exception:
                continue

        flash(f"Uy vazifasi saqlandi! {sent_count} ta o'quvchiga xabar yuborildi.", 'success')
        return redirect(url_for('homework_results'))

    return render_template('dashboard/homework.html')


@app.route('/homework/results')
@login_required
def homework_results():
    results = HomeworkResult.query.join(Student).join(Homework).filter(
        Student.teacher_id == current_user.id
    ).order_by(HomeworkResult.submitted_at.desc()).all()

    # Barcha o'quvchilar va vazifalar ro'yxati (status uchun)
    homeworks = Homework.query.filter_by(teacher_id=current_user.id).order_by(Homework.assigned_at.desc()).all()

    return render_template('dashboard/homework_results.html',
                           results=results,
                           homeworks=homeworks)


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
