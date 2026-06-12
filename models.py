from app import db
from flask_login import UserMixin
from datetime import datetime


class Teacher(UserMixin, db.Model):
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text, unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    center_name = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    students = db.relationship('Student', backref='teacher', lazy=True)
    tests = db.relationship('Test', backref='teacher', lazy=True)
    homeworks = db.relationship('Homework', backref='teacher', lazy=True)


class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    telegram_id = db.Column(db.Integer, unique=True, nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    test_results = db.relationship('TestResult', backref='student', lazy=True)
    homework_results = db.relationship('HomeworkResult', backref='student', lazy=True)


class Test(db.Model):
    __tablename__ = 'tests'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    topic = db.Column(db.Text, nullable=False)
    level = db.Column(db.Text, nullable=False)
    questions = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    results = db.relationship('TestResult', backref='test', lazy=True)


class TestResult(db.Model):
    __tablename__ = 'test_results'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), nullable=False)
    score_percent = db.Column(db.Integer, nullable=False)
    answers = db.Column(db.Text)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)


class Homework(db.Model):
    __tablename__ = 'homeworks'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    title = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)
    level = db.Column(db.Text, nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    results = db.relationship('HomeworkResult', backref='homework', lazy=True)


class HomeworkResult(db.Model):
    __tablename__ = 'homework_results'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    homework_id = db.Column(db.Integer, db.ForeignKey('homeworks.id'), nullable=False)
    image_path = db.Column(db.Text)
    ai_feedback = db.Column(db.Text)
    score_percent = db.Column(db.Integer)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
