from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func
import os

app = Flask(__name__)
app.secret_key = os.getenv('SecretKey')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement_portal.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads/resumes'
ALLOWED_RESUME_EXTENSIONS = {'pdf', 'doc', 'docx'}

db = SQLAlchemy(app)


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------

class Admin(db.Model):
    __tablename__ = 'admin'

    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<Admin {self.username}>'


class Company(db.Model):
    __tablename__ = 'company'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    email           = db.Column(db.String(120), unique=True, nullable=False)
    password        = db.Column(db.String(200), nullable=False)
    industry        = db.Column(db.String(100))
    contact         = db.Column(db.String(20))
    is_approved     = db.Column(db.Boolean, default=False)
    is_active       = db.Column(db.Boolean, default=True)
    registered_date = db.Column(db.DateTime, default=datetime.utcnow)

    job_positions = db.relationship(
        'JobPosition', backref='company',
        lazy=True, cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Company {self.name}>'


class Student(db.Model):
    __tablename__ = 'student'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    email           = db.Column(db.String(120), unique=True, nullable=False)
    password        = db.Column(db.String(200), nullable=False)
    student_id      = db.Column(db.String(50), unique=True)
    contact         = db.Column(db.String(20))
    education       = db.Column(db.Text)
    skills          = db.Column(db.Text)
    resume_path     = db.Column(db.String(200))
    is_active       = db.Column(db.Boolean, default=True)
    registered_date = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship(
        'Application', backref='student',
        lazy=True, cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Student {self.name}>'


class JobPosition(db.Model):
    __tablename__ = 'job_position'

    id              = db.Column(db.Integer, primary_key=True)
    company_id      = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    title           = db.Column(db.String(100), nullable=False)
    description     = db.Column(db.Text)
    required_skills = db.Column(db.Text)
    experience      = db.Column(db.String(50))
    salary_range    = db.Column(db.String(50))
    status          = db.Column(db.String(20), default='Active')  # Active / Closed
    is_approved     = db.Column(db.Boolean, default=False)
    posted_date     = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship(
        'Application', backref='job_position',
        lazy=True, cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<JobPosition {self.title}>'


class Application(db.Model):
    __tablename__ = 'application'

    id           = db.Column(db.Integer, primary_key=True)
    student_id   = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    job_id       = db.Column(db.Integer, db.ForeignKey('job_position.id'), nullable=False)
    status       = db.Column(db.String(20), default='Applied')  # Applied → Shortlisted → Selected / Rejected / Placed
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow)

    placement = db.relationship(
        'Placement', backref='application',
        uselist=False, cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<Application student={self.student_id} job={self.job_id} status={self.status}>'


class Placement(db.Model):
    __tablename__ = 'placement'

    id             = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    placement_date = db.Column(db.DateTime, default=datetime.utcnow)
    joining_date   = db.Column(db.Date)
    salary         = db.Column(db.String(50))

    def __repr__(self):
        return f'<Placement application={self.application_id} salary={self.salary}>'


class Notification(db.Model):
    __tablename__ = 'notification'

    id             = db.Column(db.Integer, primary_key=True)
    student_id     = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    message        = db.Column(db.Text, nullable=False)
    is_read        = db.Column(db.Boolean, default=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification {self.id}>'



def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[-1].lower() in ALLOWED_RESUME_EXTENSIONS


def _save_resume(file, student_id):
    """Save uploaded resume and return the stored filename, or None on bad input."""
    if not file or not file.filename:
        return None
    if not _allowed_file(file.filename):
        return False  # caller checks for False vs None
    filename = secure_filename(f"{student_id}_{file.filename}")
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return filename



def create_notification(student_id, application_id, status):
    """Push a status-change notification to the student's inbox."""
    appl = Application.query.get(application_id)
    messages = {
        'Shortlisted': f'You have been shortlisted for {appl.job_position.title} at {appl.job_position.company.name}!',
        'Selected':    f'Congratulations! You have been selected for {appl.job_position.title} at {appl.job_position.company.name}!',
        'Rejected':    f'Your application for {appl.job_position.title} at {appl.job_position.company.name} was not selected.',
        'Placed':      f'Congratulations! You have been placed at {appl.job_position.company.name}!',
    }
    if status not in messages:
        return
    db.session.add(Notification(
        student_id=student_id,
        application_id=application_id,
        message=messages[status],
        is_read=False,
    ))


def _require_role(*roles):
    """Return the current user's role, or None if not in the required set."""
    return session.get('role') if session.get('role') in roles else None


def init_db():
    with app.app_context():
        db.create_all()
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        if not Admin.query.filter_by(username='admin').first():
            db.session.add(Admin(
                username='admin',
                email='admin@placementportal.com',
                password=generate_password_hash('admin123'),
            ))
            db.session.commit()
            print("Default admin created — username: admin / password: admin123")





@app.context_processor
def inject_student():
    if session.get('role') == 'student':
        return dict(student=Student.query.get(session['user_id']))
    return dict(student=None)





@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')
        role     = request.form.get('role')

        if role == 'admin':
            user = Admin.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['role']    = 'admin'
                flash('Login successful!', 'success')
                return redirect(url_for('admin_dashboard'))

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
                session['role']    = 'company'
                flash('Login successful!', 'success')
                return redirect(url_for('company_dashboard'))

        elif role == 'student':
            user = Student.query.filter_by(email=email).first()
            if user and check_password_hash(user.password, password):
                if not user.is_active:
                    flash('Your account has been deactivated.', 'danger')
                    return redirect(url_for('login'))
                session['user_id'] = user.id
                session['role']    = 'student'
                flash('Login successful!', 'success')
                return redirect(url_for('student_dashboard'))

        flash('Invalid credentials!', 'danger')

    return render_template('login.html')



@app.route('/register/<role>', methods=['GET', 'POST'])
def register(role):
    """Generic registration — redirects to typed routes; keeps URL symmetry."""
    if role not in ['student', 'company']:
        flash('Invalid registration type!', 'danger')
        return redirect(url_for('index'))


    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')

        if role == 'student':
            if Student.query.filter_by(email=email).first():
                flash('Email already registered!', 'danger')
                return redirect(url_for('register', role='student'))
            db.session.add(Student(
                name=request.form.get('name'),
                email=email,
                password=generate_password_hash(password),
                student_id=request.form.get('student_id'),
                contact=request.form.get('contact'),
            ))
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))

        else:  # company
            if Company.query.filter_by(email=email).first():
                flash('Email already registered!', 'danger')
                return redirect(url_for('register', role='company'))
            db.session.add(Company(
                name=request.form.get('name'),
                email=email,
                password=generate_password_hash(password),
                industry=request.form.get('industry'),
                contact=request.form.get('contact'),
            ))
            db.session.commit()
            flash('Registration successful! Awaiting admin approval.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html', role=role)




@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        email      = request.form.get('email')
        student_id = request.form.get('student_id')

        if Student.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register_student'))

        if Student.query.filter_by(student_id=student_id).first():
            flash('Student ID already registered!', 'danger')
            return redirect(url_for('register_student'))

        student = Student(
            name=request.form.get('name'),
            email=email,
            password=generate_password_hash(request.form.get('password')),
            student_id=student_id,
            contact=request.form.get('contact'),
            education=request.form.get('education'),
            skills=request.form.get('skills'),
        )
        db.session.add(student)
        db.session.flush()  # need student.id before saving the file

        if 'resume' in request.files:
            result = _save_resume(request.files['resume'], student.id)
            if result is False:
                flash('Invalid file type! Only PDF, DOC, DOCX allowed.', 'danger')
                return redirect(url_for('register_student'))
            if result:
                student.resume_path = result

        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register_student.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))


# Admin routes

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))


    stats = {
        
        'total_companies':   db.session.query(func.count(Company.id)).scalar(),
        'total_students':    db.session.query(func.count(Student.id)).scalar(),
        'total_jobs':        db.session.query(func.count(JobPosition.id)).scalar(),
        'total_applications':db.session.query(func.count(Application.id)).scalar(),
        'pending_companies': Company.query.filter_by(is_approved=False).count(),
        'pending_jobs':      JobPosition.query.filter_by(is_approved=False).count(),
    }
    return render_template('admin_dashboard.html', stats=stats)



@app.route('/admin/companies')
def admin_companies():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    search = request.args.get('search', '').strip()
    if search:
        
        companies = Company.query.filter(
            Company.name.contains(search) | Company.industry.contains(search)
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

    search = request.args.get('search', '').strip()
    if search:
        students = Student.query.filter(
            Student.name.contains(search) |
            Student.student_id.contains(search) |
            Student.contact.contains(search)
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


@app.route('/admin/student/<int:student_id>')
def admin_view_student(student_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))
    student = Student.query.get_or_404(student_id)
    applications = Application.query.filter_by(
        student_id=student_id
    ).order_by(Application.applied_date.desc()).all()
    return render_template('admin_view_student.html', student=student, applications=applications)


@app.route('/admin/application/<int:application_id>')
def admin_view_application(application_id):
    if session.get('role') != 'admin':
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))
    application = Application.query.get_or_404(application_id)
    return render_template('admin_view_application.html', application=application)






def _company_or_401():
    """Return the current company or None; flashes + redirects handled by caller."""
    if session.get('role') != 'company':
        return None
    return Company.query.get(session['user_id'])


@app.route('/company/dashboard')
def company_dashboard():
    company = _company_or_401()
    if not company:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('login'))

    if not company.is_approved:
        flash('Your account is pending approval from admin.', 'warning')
        return redirect(url_for('login'))
    if not company.is_active:
        flash('Your account has been deactivated.', 'danger')
        return redirect(url_for('login'))

    jobs               = company.job_positions
    total_applications = db.session.query(func.count(Application.id)).filter(
        Application.job_id.in_([j.id for j in jobs])
    ).scalar() if jobs else 0

    stats = {
        'total_jobs':        len(jobs),
        'active_jobs':       sum(1 for j in jobs if j.status == 'Active' and j.is_approved),
        'total_applications': total_applications,
    }
    return render_template('company_dashboard.html', company=company, stats=stats)


@app.route('/company/jobs')
def company_jobs():
    if session.get('role') != 'company':
        return redirect(url_for('login'))
    company = Company.query.get(session['user_id'])
    return render_template('company_jobs.html', jobs=company.job_positions)


@app.route('/company/job/create', methods=['GET', 'POST'])
def create_job():
    if session.get('role') != 'company':
        return redirect(url_for('login'))

    if request.method == 'POST':
        job = JobPosition(
            company_id=session['user_id'],
            title=request.form.get('title'),
            description=request.form.get('description'),
            required_skills=request.form.get('required_skills'),
            experience=request.form.get('experience'),
            salary_range=request.form.get('salary_range'),
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
        job.title           = request.form.get('title')
        job.description     = request.form.get('description')
        job.required_skills = request.form.get('required_skills')
        job.experience      = request.form.get('experience')
        job.salary_range    = request.form.get('salary_range')
        job.status          = request.form.get('status')
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


@app.route('/company/applications/all')
def company_all_applications():
    company = _company_or_401()
    if not company:
        return redirect(url_for('login'))

    if not company.is_approved or not company.is_active:
        flash('Your company account is not authorized.', 'danger')
        return redirect(url_for('login'))

    ALLOWED = ['Applied', 'Shortlisted', 'Interview', 'Rejected', 'Selected', 'Placed']
    status_filter  = request.args.get('status', '')
    company_job_ids = [j.id for j in company.job_positions]

    query = Application.query.filter(Application.job_id.in_(company_job_ids))
    if status_filter in ALLOWED:
        query = query.filter_by(status=status_filter)

    applications = query.order_by(Application.applied_date.desc()).all()
    return render_template(
        'company_all_applications.html',
        applications=applications,
        status_filter=status_filter,
        allowed_statuses=ALLOWED,
    )



@app.route('/company/application/update/<int:id>/<status>')
def update_application(id, status):
    if session.get('role') != 'company':
        return redirect(url_for('login'))

    company = Company.query.get(session['user_id'])
    if not company.is_approved or not company.is_active:
        flash('Your company account is not authorized.', 'danger')
        return redirect(url_for('login'))

    ALLOWED = ['Applied', 'Shortlisted', 'Interview', 'Rejected', 'Selected', 'Placed']
    if status not in ALLOWED:
        flash('Invalid status!', 'danger')
        return redirect(url_for('company_dashboard'))

    application = Application.query.get_or_404(id)
    if application.job_position.company_id != session['user_id']:
        flash('Unauthorized access!', 'danger')
        return redirect(url_for('company_dashboard'))

    application.status       = status
    application.updated_date = datetime.utcnow()
    create_notification(application.student_id, application.id, status)

    if status == 'Placed':
        if not Placement.query.filter_by(application_id=application.id).first():
            db.session.add(Placement(application_id=application.id))

    db.session.commit()
    flash(f'Application status updated to {status}!', 'success')
    return redirect(url_for('company_applications', job_id=application.job_id))


# kept for backward-compat with any existing links
@app.route('/company/student/profile/<int:student_id>')
def view_student_profile(student_id):
    return redirect(url_for('company_view_student', student_id=student_id))


@app.route('/company/student/<int:student_id>')
def company_view_student(student_id):
    company = _company_or_401()
    if not company:
        return redirect(url_for('login'))

    if not company.is_approved or not company.is_active:
        flash('Your company account is not authorized.', 'danger')
        return redirect(url_for('login'))

    company_job_ids = [j.id for j in company.job_positions]
    application = Application.query.filter(
        Application.student_id == student_id,
        Application.job_id.in_(company_job_ids),
        Application.status.in_(['Shortlisted', 'Interview', 'Selected', 'Placed']),
    ).first()

    if not application:
        flash('You can only view profiles of shortlisted or selected applicants.', 'danger')
        return redirect(url_for('company_dashboard'))

    student = Student.query.get_or_404(student_id)
    return render_template('company_view_student.html', student=student, application=application)


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
    notifications = Notification.query.filter_by(
        student_id=student.id, is_read=False
    ).order_by(Notification.created_at.desc()).all()

    # count per status in one pass
    status_counts = {}
    for a in applications:
        status_counts[a.status] = status_counts.get(a.status, 0) + 1

    stats = {
        'total_applications': len(applications),
        'shortlisted': status_counts.get('Shortlisted', 0),
        'selected':    status_counts.get('Selected', 0),
        'rejected':    status_counts.get('Rejected', 0),
        'placed':      status_counts.get('Placed', 0),
    }
    return render_template('student_dashboard.html', student=student, stats=stats, notifications=notifications)


@app.route('/student/profile', methods=['GET', 'POST'])
def student_profile():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    student = Student.query.get(session['user_id'])

    if request.method == 'POST':
        student.name      = request.form.get('name')
        student.contact   = request.form.get('contact')
        student.education = request.form.get('education')
        student.skills    = request.form.get('skills')

        if 'resume' in request.files:
            result = _save_resume(request.files['resume'], student.id)
            if result is False:
                flash('Invalid file type! Only PDF, DOC, DOCX allowed.', 'danger')
                return redirect(url_for('student_profile'))
            if result:
                student.resume_path = result

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student_profile'))

    return render_template('student_profile.html', student=student)



@app.route('/student/jobs')
def student_jobs():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    search = request.args.get('search', '').strip()

    jobs = JobPosition.query.join(Company).filter(
        JobPosition.is_approved == True,
        JobPosition.status == 'Active',
        Company.is_approved == True,
        Company.is_active == True,
    ).all()

    if search:
        q = search.lower()
        jobs = [
            j for j in jobs
            if q in j.title.lower()
            or q in j.company.name.lower()
            or q in (j.required_skills or '').lower()
        ]

    applied_job_ids = {
        a.job_id for a in Application.query.filter_by(student_id=session['user_id']).all()
    }
    return render_template('student_jobs.html', jobs=jobs, applied_job_ids=applied_job_ids)


@app.route('/student/apply/<int:job_id>')
def apply_job(job_id):
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    student = Student.query.get(session['user_id'])

    if not student.is_active:
        flash('Your account has been deactivated.', 'danger')
        return redirect(url_for('login'))

    if not student.resume_path:
        flash('Please upload your resume before applying!', 'warning')
        return redirect(url_for('student_profile'))

    job = JobPosition.query.get_or_404(job_id)

    if not job.company.is_approved or not job.company.is_active:
        flash('This placement drive is no longer available.', 'warning')
        return redirect(url_for('student_jobs'))

    if not job.is_approved or job.status != 'Active':
        flash('This job is no longer accepting applications.', 'warning')
        return redirect(url_for('student_jobs'))

    existing = Application.query.filter_by(student_id=student.id, job_id=job_id).first()
    if existing:
        flash(f'Already applied — current status: {existing.status}', 'warning')
        return redirect(url_for('student_jobs'))

    db.session.add(Application(student_id=student.id, job_id=job_id, status='Applied'))
    db.session.commit()
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('student_applications'))


@app.route('/student/applications')
def student_applications():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    applications = Application.query.filter_by(
        student_id=session['user_id']
    ).order_by(Application.applied_date.desc()).all()

    status_counts = {}
    for a in applications:
        status_counts[a.status] = status_counts.get(a.status, 0) + 1

    stats = {
        'total_applications': len(applications),
        'shortlisted': status_counts.get('Shortlisted', 0),
        'selected':    status_counts.get('Selected', 0),
        'rejected':    status_counts.get('Rejected', 0),
        'placed':      status_counts.get('Placed', 0),
    }
    return render_template('student_applications.html', applications=applications, stats=stats)


@app.route('/student/applications/history')
def student_application_history():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    applications = Application.query.filter_by(
        student_id=session['user_id']
    ).order_by(Application.applied_date.desc()).all()
    history = [
        {
            'application': a,
            'job':         a.job_position,
            'company':     a.job_position.company,
            'status':      a.status,
            'applied_on':  a.applied_date,
            'updated_on':  a.updated_date,
        }
        for a in applications
    ]
    return render_template('student_application_history.html', history=history)

@app.route('/student/notifications')
def student_notifications():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    notifications = Notification.query.filter_by(
        student_id=session['user_id']
    ).order_by(Notification.created_at.desc()).all()

    unread = [n for n in notifications if not n.is_read]
    for n in unread:
        n.is_read = True
    if unread:
        db.session.commit()

    return render_template('student_notifications.html', notifications=notifications)


@app.route('/student/notifications/unread-count')
def unread_notification_count():
    if session.get('role') != 'student':
        return {'count': 0}
    count = Notification.query.filter_by(
        student_id=session['user_id'], is_read=False
    ).count()
    return {'count': count}


if __name__ == '__main__':
    init_db()
    print("Database initialised successfully.")
    app.run(debug=True)