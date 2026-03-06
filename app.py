from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement_portal.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads/resumes'

db = SQLAlchemy(app)


class Admin(db.Model):
    __tablename__ = 'admin'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80),  unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<Admin {self.username}>'
    

class Company(db.Model):
    __tablename__ = 'company'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    industry = db.Column(db.String(100))
    contact = db.Column(db.String(20))
    is_approved = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    registered_date = db.Column(db.DateTime, default=datetime.utcnow)

    #Relationships
    job_positions = db.relationship(
        'JobPosition', backref='company',
        lazy=True, cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Company {self.name}>'

class Student(db.Model):
    __tablename__ = 'student'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    student_id = db.Column(db.String(50),  unique=True)
    contact = db.Column(db.String(20))
    education = db.Column(db.Text)
    skills = db.Column(db.Text)
    resume_path = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    registered_date = db.Column(db.DateTime, default=datetime.utcnow)

    #Relationships
    applications = db.relationship(
        'Application', backref='student',
        lazy=True, cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Student {self.name}>'

class JobPosition(db.Model):
    __tablename__ = 'job_position'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    required_skills = db.Column(db.Text)
    experience = db.Column(db.String(50))
    salary_range = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Active') #Active or Closed
    is_approved = db.Column(db.Boolean, default=False)
    posted_date = db.Column(db.DateTime, default=datetime.utcnow)

    #Relationships
    applications = db.relationship(
        'Application', backref='job_position',
        lazy=True, cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<JobPosition {self.title}>'

class Application(db.Model):
    __tablename__ = 'application'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'),nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job_position.id'), nullable=False)
    status = db.Column(db.String(20), default='Applied')  #Applied, Shortlisted, Rejected or Hired
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow)

    #Relationships
    placement = db.relationship(
        'Placement', backref='application',
        uselist=False, cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Application student={self.student_id} job={self.job_id} status={self.status}>'

class Placement(db.Model):
    __tablename__ = 'placement'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    placement_date = db.Column(db.DateTime, default=datetime.utcnow)
    joining_date = db.Column(db.Date)
    salary = db.Column(db.String(50))

    def __repr__(self):
        return f'<Placement application={self.application_id} salary={self.salary}>'

def init_db():
    with app.app_context():
        db.create_all()

        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
if __name__ == '__main__':
    init_db()
    print("Database initialised successfully.")