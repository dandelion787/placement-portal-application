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

        # Create default admin if not exists
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            admin = Admin(
                username='admin',
                email='admin@placementportal.com',
                password=generate_password_hash('admin123')
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: username='admin', password='admin123'")


if __name__ == '__main__':
    init_db()
    print("Database initialised successfully.")

###########ROUTES_Defined#############
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if role == 'admin':
            user = Admin.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['role'] = 'admin'
                flash('Login successful!', 'success')
                return redirect(url_for('admin_dashboard'))  # Admin dashboard redirect
        
        elif role == 'company':
            user = Company.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                if not user.is_active:
                    flash('Your account has been deactivated.', 'danger')
                    return redirect(url_for('login'))
                if not user.is_approved:
                    flash('Your account is pending approval from admin.', 'warning')
                    return redirect(url_for('login'))
                session['user_id'] = user.id
                session['role'] = 'company'
                flash('Login successful!', 'success')
                return redirect(url_for('company_dashboard'))  # Company dashboard redirect
        
        elif role == 'student':
            user = Student.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                if not user.is_active:
                    flash('Your account has been deactivated.', 'danger')
                    return redirect(url_for('login'))
                session['user_id'] = user.id
                session['role'] = 'student'
                flash('Login successful!', 'success')
                return redirect(url_for('student_dashboard'))  # Student dashboard redirect
        
        flash('Invalid credentials!', 'danger')
    
    return render_template('login.html')

@app.route('/register/<role>', methods=['GET', 'POST'])
def register(role):
    if role not in ['student', 'company']:  # Admin has no registration
        flash('Invalid registration type!', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if role == 'student':
            existing = Student.query.filter_by(email=email).first()
            if existing:
                flash('Email already registered!', 'danger')
                return redirect(url_for('register', role='student'))
            
            student = Student(
                name=request.form.get('name'),
                email=email,
                password=generate_password_hash(password),
                student_id=request.form.get('student_id'),
                contact=request.form.get('contact')
            )
            db.session.add(student)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        
        elif role == 'company':
            existing = Company.query.filter_by(email=email).first()
            if existing:
                flash('Email already registered!', 'danger')
                return redirect(url_for('register', role='company'))
            
            company = Company(
                name=request.form.get('name'),
                email=email,
                password=generate_password_hash(password),
                industry=request.form.get('industry'),
                contact=request.form.get('contact')
            )
            db.session.add(company)
            db.session.commit()
            flash('Registration successful! Awaiting admin approval.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html', role=role)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

# Admin Routes
@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))
    
    stats = {
        'total_companies': Company.query.count(),
        'total_students': Student.query.count(),
        'total_jobs': JobPosition.query.count(),
        'total_applications': Application.query.count(),
        'pending_companies': Company.query.filter_by(is_approved=False).count(),
        'pending_jobs': JobPosition.query.filter_by(is_approved=False).count()
    }
    
    return render_template('admin_dashboard.html', stats=stats)

@app.route('/admin/companies')
def admin_companies():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    search = request.args.get('search', '')
    if search:
        companies = Company.query.filter(
            (Company.name.contains(search)) | (Company.industry.contains(search))
        ).all()
    else:
        companies = Company.query.all()
    
    return render_template('admin_companies.html', companies=companies)

@app.route('/admin/company/approve/<int:id>')
def approve_company(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    company = Company.query.get_or_404(id)
    company.is_approved = True
    db.session.commit()
    flash(f'Company {company.name} approved!', 'success')
    return redirect(url_for('admin_companies'))

@app.route('/admin/company/reject/<int:id>')
def reject_company(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    company = Company.query.get_or_404(id)
    company.is_approved = False
    db.session.commit()
    flash(f'Company {company.name} rejected!', 'warning')
    return redirect(url_for('admin_companies'))

@app.route('/admin/company/toggle/<int:id>')
def toggle_company(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    company = Company.query.get_or_404(id)
    company.is_active = not company.is_active
    db.session.commit()
    status = 'activated' if company.is_active else 'deactivated'
    flash(f'Company {company.name} {status}!', 'success')
    return redirect(url_for('admin_companies'))

@app.route('/admin/students')
def admin_students():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    search = request.args.get('search', '')
    if search:
        students = Student.query.filter(
            (Student.name.contains(search)) | 
            (Student.student_id.contains(search)) | 
            (Student.contact.contains(search))
        ).all()
    else:
        students = Student.query.all()
    
    return render_template('admin_students.html', students=students)

@app.route('/admin/student/toggle/<int:id>')
def toggle_student(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    student = Student.query.get_or_404(id)
    student.is_active = not student.is_active
    db.session.commit()
    status = 'activated' if student.is_active else 'blacklisted'
    flash(f'Student {student.name} {status}!', 'success')
    return redirect(url_for('admin_students'))

@app.route('/admin/jobs')
def admin_jobs():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    jobs = JobPosition.query.all()
    return render_template('admin_jobs.html', jobs=jobs)

@app.route('/admin/job/approve/<int:id>')
def approve_job(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    job = JobPosition.query.get_or_404(id)
    job.is_approved = True
    db.session.commit()
    flash('Job posting approved!', 'success')
    return redirect(url_for('admin_jobs'))

@app.route('/admin/job/reject/<int:id>')
def reject_job(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    job = JobPosition.query.get_or_404(id)
    job.is_approved = False
    db.session.commit()
    flash('Job posting rejected!', 'warning')
    return redirect(url_for('admin_jobs'))

@app.route('/admin/applications')
def admin_applications():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    applications = Application.query.all()
    return render_template('admin_applications.html', applications=applications)
