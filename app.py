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

@app.route('/company/dashboard')
def company_dashboard():
    if session.get('role') != 'company':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))
    
    company = Company.query.get(session['user_id'])
    
    # Companies can only access dashboard when approved by admin
    if not company.is_approved:
        flash('Your account is pending approval from admin.', 'warning')
        return redirect(url_for('login'))
    if not company.is_active:
        flash('Your account has been deactivated.', 'danger')
        return redirect(url_for('login'))
    
    jobs = JobPosition.query.filter_by(company_id=company.id).all()
    total_applications = sum(len(job.applications) for job in jobs)
    
    stats = {
        'total_jobs': len(jobs),
        'active_jobs': len([j for j in jobs if j.status == 'Active' and j.is_approved]),
        'total_applications': total_applications
    }
    
    return render_template('company_dashboard.html', company=company, stats=stats)


@app.route('/company/jobs')
def company_jobs():
    if session.get('role') != 'company':
        return redirect(url_for('login'))
    
    company = Company.query.get(session['user_id'])
    jobs = JobPosition.query.filter_by(company_id=company.id).all()
    
    return render_template('company_jobs.html', jobs=jobs)


@app.route('/company/job/create', methods=['GET', 'POST'])
def create_job():
    if session.get('role') != 'company':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        job = JobPosition(
            company_id=session['user_id'],
            title=request.form.get('title'),
            description=request.form.get('description'),
            required_skills=request.form.get('required_skills'),  # Required skills
            experience=request.form.get('experience'),             # Experience
            salary_range=request.form.get('salary_range')         # Salary range
        )
        db.session.add(job)
        db.session.commit()
        flash('Job posted successfully! Awaiting admin approval.', 'success')
        return redirect(url_for('company_jobs'))
    
    return render_template('create_job.html')


@app.route('/company/job/edit/<int:id>', methods=['GET', 'POST'])
def edit_job(id):
    if session.get('role') != 'company':
        return redirect(url_for('login'))
    
    job = JobPosition.query.get_or_404(id)
    
    if job.company_id != session['user_id']:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('company_jobs'))
    
    if request.method == 'POST':
        job.title = request.form.get('title')
        job.description = request.form.get('description')
        job.required_skills = request.form.get('required_skills')
        job.experience = request.form.get('experience')
        job.salary_range = request.form.get('salary_range')
        job.status = request.form.get('status')  # Active / Closed status update
        db.session.commit()
        flash('Job updated successfully!', 'success')
        return redirect(url_for('company_jobs'))
    
    return render_template('edit_job.html', job=job)


@app.route('/company/applications/<int:job_id>')
def company_applications(job_id):
    if session.get('role') != 'company':
        return redirect(url_for('login'))
    
    job = JobPosition.query.get_or_404(job_id)
    
    if job.company_id != session['user_id']:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('company_jobs'))
    
    applications = Application.query.filter_by(job_id=job_id).all()
    
    return render_template('company_applications.html', job=job, applications=applications)


@app.route('/company/application/update/<int:id>/<status>')
def update_application(id, status):
    if session.get('role') != 'company':
        return redirect(url_for('login'))
    
    if status not in ['Shortlisted', 'Selected', 'Rejected', 'Placed']:
        flash('Invalid status!', 'danger')
        return redirect(url_for('company_dashboard'))
    
    application = Application.query.get_or_404(id)
    
    if application.job_position.company_id != session['user_id']:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('company_dashboard'))
    
    application.status = status
    application.updated_date = datetime.utcnow()
    
    # Trigger notification to student on every status change
    create_notification(application.student_id, application.id, status)
    
    if status == 'Placed':
        placement = Placement(application_id=application.id)
        db.session.add(placement)
    
    db.session.commit()
    flash(f'Application status updated to {status}!', 'success')
    return redirect(url_for('company_applications', job_id=application.job_id))


# View shortlisted student profile and resume
@app.route('/company/student/profile/<int:student_id>')
def view_student_profile(student_id):
    if session.get('role') != 'company':
        return redirect(url_for('login'))
    
    company = Company.query.get(session['user_id'])
    
    # Ensure the student has applied to at least one of this company's jobs
    # and is shortlisted — prevents unauthorized profile access
    company_job_ids = [job.id for job in company.job_positions]
    shortlisted_application = Application.query.filter(
        Application.student_id == student_id,
        Application.job_id.in_(company_job_ids),
        Application.status.in_(['Shortlisted', 'Selected', 'Placed'])
    ).first()
    
    if not shortlisted_application:
        flash('Unauthorized access or student not shortlisted!', 'danger')
        return redirect(url_for('company_dashboard'))
    
    student = Student.query.get_or_404(student_id)
    return render_template('view_student_profile.html', student=student)


@app.route('/student/dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))
    
    student = Student.query.get(session['user_id'])
    
    if not student.is_active:
        flash('Your account has been deactivated.', 'danger')
        return redirect(url_for('login'))
    
    applications = Application.query.filter_by(student_id=student.id).all()
    
    # Fetch unread notifications for dashboard alert display
    notifications = Notification.query.filter_by(
        student_id=student.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).all()
    
    stats = {
        'total_applications': len(applications),
        'shortlisted': len([a for a in applications if a.status == 'Shortlisted']),
        'selected': len([a for a in applications if a.status == 'Selected']),
        'rejected': len([a for a in applications if a.status == 'Rejected']),
        'placed': len([a for a in applications if a.status == 'Placed'])
    }
    
    return render_template('student_dashboard.html', student=student, stats=stats, notifications=notifications)


@app.route('/student/profile', methods=['GET', 'POST'])
def student_profile():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    
    student = Student.query.get(session['user_id'])
    
    if request.method == 'POST':
        student.name = request.form.get('name')
        student.contact = request.form.get('contact')
        student.education = request.form.get('education')   # Education update
        student.skills = request.form.get('skills')         # Skills update
        
        # Resume upload — allowed on both registration and profile update
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename:
                allowed_extensions = {'pdf', 'doc', 'docx'}
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext not in allowed_extensions:
                    flash('Invalid file type! Only PDF, DOC, DOCX allowed.', 'danger')
                    return redirect(url_for('student_profile'))
                
                filename = secure_filename(f"{student.id}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                student.resume_path = filename
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student_profile'))
    
    return render_template('student_profile.html', student=student)


@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        existing = Student.query.filter_by(email=email).first()
        if existing:
            flash('Email already registered!', 'danger')
            return redirect(url_for('register_student'))
        
        student = Student(
            name=request.form.get('name'),
            email=email,
            password=generate_password_hash(password),
            student_id=request.form.get('student_id'),
            contact=request.form.get('contact'),
            education=request.form.get('education'),
            skills=request.form.get('skills')
        )
        db.session.add(student)
        db.session.flush()  # Get student.id before commit for resume naming
        
        # Resume upload option during registration
        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename:
                allowed_extensions = {'pdf', 'doc', 'docx'}
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext not in allowed_extensions:
                    flash('Invalid file type! Only PDF, DOC, DOCX allowed.', 'danger')
                    return redirect(url_for('register_student'))
                
                filename = secure_filename(f"{student.id}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                student.resume_path = filename
        
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register_student.html')


@app.route('/student/jobs')
def student_jobs():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    
    search = request.args.get('search', '')
    
    # Only show admin-approved and active jobs
    jobs = JobPosition.query.filter_by(is_approved=True, status='Active').all()
    
    # Search by company name, position/title, or required skills
    if search:
        jobs = [j for j in jobs if
                search.lower() in j.title.lower() or
                search.lower() in j.company.name.lower() or
                search.lower() in (j.required_skills or '').lower()]
    
    # Track which jobs the student has already applied to
    student_applications = Application.query.filter_by(student_id=session['user_id']).all()
    applied_job_ids = [app.job_id for app in student_applications]
    
    return render_template('student_jobs.html', jobs=jobs, applied_job_ids=applied_job_ids)


@app.route('/student/apply/<int:job_id>')
def apply_job(job_id):
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    
    student = Student.query.get(session['user_id'])
    
    # Block application if resume is not uploaded
    if not student.resume_path:
        flash('Please upload your resume before applying!', 'warning')
        return redirect(url_for('student_profile'))
    
    job = JobPosition.query.get_or_404(job_id)
    
    # Ensure job is still active and approved
    if not job.is_approved or job.status != 'Active':
        flash('This job is no longer accepting applications.', 'warning')
        return redirect(url_for('student_jobs'))
    
    # Prevent duplicate applications
    existing = Application.query.filter_by(
        student_id=session['user_id'],
        job_id=job_id
    ).first()
    
    if existing:
        flash('You have already applied for this job!', 'warning')
        return redirect(url_for('student_jobs'))
    
    application = Application(
        student_id=session['user_id'],
        job_id=job_id,
        status='Applied'
    )
    db.session.add(application)
    db.session.commit()
    
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student_jobs'))


@app.route('/student/applications')
def student_applications():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    
    # View all applied jobs with their current application status
    applications = Application.query.filter_by(
        student_id=session['user_id']
    ).order_by(Application.applied_date.desc()).all()
    
    return render_template('student_applications.html', applications=applications)


# Notifications — status change alerts for shortlisted/selected/rejected
@app.route('/student/notifications')
def student_notifications():
    if session.get('role') != 'student':
        return redirect(url_for('login'))
    
    notifications = Notification.query.filter_by(
        student_id=session['user_id']
    ).order_by(Notification.created_at.desc()).all()
    
    # Mark all as read when the page is opened
    for notification in notifications:
        notification.is_read = True
    db.session.commit()
    
    return render_template('student_notifications.html', notifications=notifications)


@app.route('/student/notifications/unread-count')
def unread_notification_count():
    if session.get('role') != 'student':
        return {'count': 0}
    
    count = Notification.query.filter_by(
        student_id=session['user_id'],
        is_read=False
    ).count()
    
    return {'count': count}


# Helper — called inside update_application() when company changes status
def create_notification(student_id, application_id, status):
    application = Application.query.get(application_id)
    messages = {
        'Shortlisted': f'You have been shortlisted for {application.job_position.title} at {application.job_position.company.name}!',
        'Selected':    f'Congratulations! You have been selected for {application.job_position.title} at {application.job_position.company.name}!',
        'Rejected':    f'Your application for {application.job_position.title} at {application.job_position.company.name} was not selected.',
        'Placed':      f'Congratulations! You have been placed at {application.job_position.company.name}!'
    }
    
    if status in messages:
        notification = Notification(
            student_id=student_id,
            application_id=application_id,
            message=messages[status],
            is_read=False
        )
        db.session.add(notification)


# ─────────────────────────────────────────
# APPLICATION HISTORY
# ─────────────────────────────────────────

@app.route('/student/applications/history')
def student_application_history():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    # Complete application history — all statuses, newest first
    applications = Application.query.filter_by(
        student_id=session['user_id']
    ).order_by(Application.applied_date.desc()).all()

    # Build a full timeline of status changes per application
    history = []
    for app in applications:
        history.append({
            'application': app,
            'job':         app.job_position,
            'company':     app.job_position.company,
            'status':      app.status,
            'applied_on':  app.applied_date,
            'updated_on':  app.updated_date,
        })

    return render_template('student_application_history.html', history=history)


# ─────────────────────────────────────────
# DUPLICATE APPLICATION PREVENTION
# ─────────────────────────────────────────

@app.route('/student/apply/<int:job_id>')
def apply_job(job_id):
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    student = Student.query.get(session['user_id'])

    if not student.is_active:
        flash('Your account has been deactivated.', 'danger')
        return redirect(url_for('login'))

    # Resume must be uploaded before applying
    if not student.resume_path:
        flash('Please upload your resume before applying!', 'warning')
        return redirect(url_for('student_profile'))

    job = JobPosition.query.get_or_404(job_id)

    # Only approved companies can have active placement drives
    if not job.company.is_approved or not job.company.is_active:
        flash('This placement drive is no longer available.', 'warning')
        return redirect(url_for('student_jobs'))

    # Job itself must be approved and active
    if not job.is_approved or job.status != 'Active':
        flash('This job is no longer accepting applications.', 'warning')
        return redirect(url_for('student_jobs'))

    # Strict duplicate check — one application per student per job
    existing = Application.query.filter_by(
        student_id=student.id,
        job_id=job_id
    ).first()

    if existing:
        flash(
            f'You have already applied for this position. '
            f'Current status: {existing.status}',
            'warning'
        )
        return redirect(url_for('student_jobs'))

    application = Application(
        student_id=student.id,
        job_id=job_id,
        status='Applied'     # Initial status
    )
    db.session.add(application)
    db.session.commit()

    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student_applications'))


# ─────────────────────────────────────────
# STUDENT — VIEW OWN RECORDS ONLY
# ─────────────────────────────────────────

@app.route('/student/applications')
def student_applications():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    # Students can only view their own applications
    applications = Application.query.filter_by(
        student_id=session['user_id']
    ).order_by(Application.applied_date.desc()).all()

    return render_template('student_applications.html', applications=applications)


@app.route('/student/profile', methods=['GET', 'POST'])
def student_profile():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    # Students can only view and edit their own profile
    student = Student.query.get(session['user_id'])

    if request.method == 'POST':
        student.name      = request.form.get('name')
        student.contact   = request.form.get('contact')
        student.education = request.form.get('education')
        student.skills    = request.form.get('skills')

        if 'resume' in request.files:
            file = request.files['resume']
            if file and file.filename:
                allowed = {'pdf', 'doc', 'docx'}
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext not in allowed:
                    flash('Invalid file type! Only PDF, DOC, DOCX allowed.', 'danger')
                    return redirect(url_for('student_profile'))
                filename = secure_filename(f"{student.id}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                student.resume_path = filename

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student_profile'))

    return render_template('student_profile.html', student=student)


# ─────────────────────────────────────────
# APPROVED PLACEMENT DRIVES — STUDENT VIEW
# ─────────────────────────────────────────

@app.route('/student/jobs')
def student_jobs():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    search = request.args.get('search', '')

    # Only surface jobs from approved + active companies that are
    # themselves approved and active — full chain validation
    jobs = JobPosition.query.join(Company).filter(
        JobPosition.is_approved == True,
        JobPosition.status == 'Active',
        Company.is_approved == True,
        Company.is_active == True
    ).all()

    if search:
        jobs = [j for j in jobs if
                search.lower() in j.title.lower() or
                search.lower() in j.company.name.lower() or
                search.lower() in (j.required_skills or '').lower()]

    applied_job_ids = [
        a.job_id for a in
        Application.query.filter_by(student_id=session['user_id']).all()
    ]

    return render_template('student_jobs.html', jobs=jobs, applied_job_ids=applied_job_ids)


# ─────────────────────────────────────────
# APPLICATION STATUS MANAGEMENT
# ─────────────────────────────────────────

@app.route('/company/application/update/<int:id>/<status>')
def update_application(id, status):
    if session.get('role') != 'company':
        return redirect(url_for('login'))

    company = Company.query.get(session['user_id'])

    # Only approved companies can update application statuses
    if not company.is_approved or not company.is_active:
        flash('Your company account is not authorized.', 'danger')
        return redirect(url_for('login'))

    # Full status lifecycle
    allowed_statuses = ['Applied', 'Shortlisted', 'Interview', 'Rejected', 'Selected', 'Placed']
    if status not in allowed_statuses:
        flash('Invalid status!', 'danger')
        return redirect(url_for('company_dashboard'))

    application = Application.query.get_or_404(id)

    # Company can only update applications for their own jobs
    if application.job_position.company_id != session['user_id']:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('company_dashboard'))

    application.status       = status
    application.updated_date = datetime.utcnow()

    # Trigger notification to student on every status change
    create_notification(application.student_id, application.id, status)

    if status == 'Placed':
        # Avoid duplicate placement records
        existing_placement = Placement.query.filter_by(
            application_id=application.id
        ).first()
        if not existing_placement:
            placement = Placement(application_id=application.id)
            db.session.add(placement)

    db.session.commit()
    flash(f'Application status updated to {status}!', 'success')
    return redirect(url_for('company_applications', job_id=application.job_id))


# ─────────────────────────────────────────
# ROLE-BASED PROFILE & APPLICATION ACCESS
# ─────────────────────────────────────────

# Admin — view any student profile and all their applications
@app.route('/admin/student/<int:student_id>')
def admin_view_student(student_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    student      = Student.query.get_or_404(student_id)
    applications = Application.query.filter_by(
        student_id=student_id
    ).order_by(Application.applied_date.desc()).all()

    return render_template('admin_view_student.html', student=student, applications=applications)


# Admin — view any single application in full detail
@app.route('/admin/application/<int:application_id>')
def admin_view_application(application_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    application = Application.query.get_or_404(application_id)
    return render_template('admin_view_application.html', application=application)


# Company — view shortlisted/selected student profile and resume
@app.route('/company/student/profile/<int:student_id>')
def company_view_student(student_id):
    if session.get('role') != 'company':
        return redirect(url_for('login'))

    company = Company.query.get(session['user_id'])

    if not company.is_approved or not company.is_active:
        flash('Your company account is not authorized.', 'danger')
        return redirect(url_for('login'))

    # Company can only view profiles of students who applied to their jobs
    # and have progressed past the initial Applied stage
    company_job_ids = [job.id for job in company.job_positions]
    application = Application.query.filter(
        Application.student_id == student_id,
        Application.job_id.in_(company_job_ids),
        Application.status.in_(['Shortlisted', 'Interview', 'Selected', 'Placed'])
    ).first()

    if not application:
        flash('You can only view profiles of shortlisted or selected applicants.', 'danger')
        return redirect(url_for('company_dashboard'))

    student = Student.query.get_or_404(student_id)
    return render_template('company_view_student.html', student=student, application=application)


# Company — view all applications across all their job postings
@app.route('/company/applications/all')
def company_all_applications():
    if session.get('role') != 'company':
        return redirect(url_for('login'))

    company = Company.query.get(session['user_id'])

    if not company.is_approved or not company.is_active:
        flash('Your company account is not authorized.', 'danger')
        return redirect(url_for('login'))

    # Filter by status if provided
    status_filter = request.args.get('status', '')
    allowed_statuses = ['Applied', 'Shortlisted', 'Interview', 'Rejected', 'Selected', 'Placed']

    company_job_ids = [job.id for job in company.job_positions]
    query = Application.query.filter(Application.job_id.in_(company_job_ids))

    if status_filter and status_filter in allowed_statuses:
        query = query.filter_by(status=status_filter)

    applications = query.order_by(Application.applied_date.desc()).all()

    return render_template(
        'company_all_applications.html',
        applications=applications,
        status_filter=status_filter,
        allowed_statuses=allowed_statuses
    )
