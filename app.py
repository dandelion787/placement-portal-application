from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func
import logging
import os

app = Flask(__name__)
app.secret_key = os.getenv('SecretKey')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///placement_portal.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads/resumes'

# placement cell said max 3MB for resumes, keeping 5 to be safe
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# per TPO circular - only shortlisted/above can have profile viewed by recruiter
PROFILE_VIEW_ELIGIBLE = ['Shortlisted', 'Interview', 'Selected', 'Placed']

RESUME_EXTS = {'pdf', 'doc', 'docx'}

# these are the only status transitions we track for NAAC reporting
NOTIF_STATUSES = ['Shortlisted', 'Selected', 'Rejected', 'Placed']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

db = SQLAlchemy(app)


# ---------- models ----------

class Admin(db.Model):
    __tablename__ = 'admin'
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<Admin {self.username}>'


# recruiter/company side - needs admin approval before they can post drives
class Company(db.Model):
    __tablename__ = 'company'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    email       = db.Column(db.String(120), unique=True, nullable=False)
    password    = db.Column(db.String(200), nullable=False)
    industry    = db.Column(db.String(100))
    contact     = db.Column(db.String(20))
    is_approved = db.Column(db.Boolean, default=False)
    is_active   = db.Column(db.Boolean, default=True)
    reg_date    = db.Column(db.DateTime, default=datetime.utcnow)

    job_positions = db.relationship('JobPosition', backref='company',
                                    lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Company {self.name}>'


class Student(db.Model):
    __tablename__ = 'student'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    stud_id    = db.Column(db.String(50), unique=True)     # enrolment no., e.g. 22CSE045
    contact    = db.Column(db.String(20))
    education  = db.Column(db.Text)   # branch, year, CGPA - freetext for now, TODO: normalise
    skills     = db.Column(db.Text)
    resume_path = db.Column(db.String(200))
    is_active  = db.Column(db.Boolean, default=True)
    reg_date   = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship('Application', backref='student',
                                   lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Student {self.stud_id} - {self.name}>'


class JobPosition(db.Model):
    # "drive" in TPO lingo, "job" in code - kept as JobPosition to avoid
    # confusion with the Drive model we might add for on-campus drives later
    __tablename__ = 'job_position'
    id             = db.Column(db.Integer, primary_key=True)
    company_id     = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    title          = db.Column(db.String(100), nullable=False)
    description    = db.Column(db.Text)
    required_skills = db.Column(db.Text)
    experience     = db.Column(db.String(50))    # e.g. "0-1 yr", "fresher"
    salary_range   = db.Column(db.String(50))    # LPA, stored as plain text
    status         = db.Column(db.String(20), default='Active')   # Active | Closed
    is_approved    = db.Column(db.Boolean, default=False)
    posted_date    = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship('Application', backref='job_position',
                                   lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Drive: {self.title} [{self.status}]>'


class Application(db.Model):
    __tablename__ = 'application'
    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    job_id     = db.Column(db.Integer, db.ForeignKey('job_position.id'), nullable=False)
    # pipeline: Applied -> Shortlisted -> Interview -> Selected/Rejected -> Placed
    # "Interview" stage added after companies complained about missing it - batch 2024 onwards
    status       = db.Column(db.String(20), default='Applied')
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow)

    placement = db.relationship('Placement', backref='application',
                                uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Appl#{self.id} stud={self.student_id} drive={self.job_id} [{self.status}]>'


class Placement(db.Model):
    # one-to-one with application; only created when status hits "Placed"
    # used by placement cell for annual report & NAAC data
    __tablename__ = 'placement'
    id             = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    placement_date = db.Column(db.DateTime, default=datetime.utcnow)
    joining_date   = db.Column(db.Date)
    salary         = db.Column(db.String(50))   # LPA as string, e.g. "8 LPA", "12-15 LPA"

    def __repr__(self):
        return f'<Placed appl={self.application_id} salary={self.salary}>'


class Notification(db.Model):
    __tablename__ = 'notification'
    id             = db.Column(db.Integer, primary_key=True)
    student_id     = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    message   = db.Column(db.Text, nullable=False)
    is_read   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notif stud={self.student_id} read={self.is_read}>'


# ---------- utils ----------

def chk_resume_ext(fname):
    # basic extension check - not foolproof but good enough for internal portal
    return '.' in fname and fname.rsplit('.', 1)[-1].lower() in RESUME_EXTS


def save_resume(resume_file, stud_id):
    """
    Saves uploaded resume to disk.
    Returns: filename on success, False on bad ext, None if no file.
    Wrapping file.save in try/except after that prod crash (Mar 2024) where
    upload folder perms got reset after server migration.
    """
    if not resume_file or resume_file.filename == '':
        return None
    if not chk_resume_ext(resume_file.filename):
        return False
    safe_name = secure_filename(f"stud{stud_id}_{resume_file.filename}")
    dest = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
    try:
        resume_file.save(dest)
    except OSError as e:
        logger.exception(f"Resume upload failed for stud_id={stud_id}, dest={dest}: {e}")
        return None
    return safe_name


def notify_stud(stud_id, appl_id, new_status):
    """push in-app notification on pipeline status change"""
    if new_status not in NOTIF_STATUSES:
        return   # don't spam for Interview stage etc.

    appl = Application.query.get(appl_id)
    if not appl:
        logger.warning(f"notify_stud called with invalid appl_id={appl_id}")
        return

    drive_title = appl.job_position.title
    comp_name   = appl.job_position.company.name

    if new_status == 'Shortlisted':
        msg = f'You have been shortlisted for {drive_title} at {comp_name}. Check the portal for next steps.'
    elif new_status == 'Selected':
        msg = f'Congratulations! You have been selected for {drive_title} at {comp_name}. Await further communication from the placement cell.'
    elif new_status == 'Rejected':
        msg = f'Your application for {drive_title} at {comp_name} was unsuccessful. Keep applying!'
    elif new_status == 'Placed':
        msg = f'You are now officially placed at {comp_name}! Congratulations. Please submit your offer letter copy to the TPO office.'

    db.session.add(Notification(
        student_id=stud_id,
        application_id=appl_id,
        message=msg,
        is_read=False,
    ))


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
            print("Default admin seeded. Creds: admin / admin123  <-- change this in prod!!")


@app.context_processor
def inject_stud_ctx():
    # makes `student` available in all templates without passing it every time
    if session.get('role') == 'student':
        return dict(student=Student.query.get(session['user_id']))
    return dict(student=None)


# ==================== PUBLIC ====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        pwd   = request.form.get('password', '')
        role  = request.form.get('role')

        if role == 'admin':
            usr = Admin.query.filter_by(email=email).first()
            if usr and check_password_hash(usr.password, pwd):
                session['user_id'] = usr.id
                session['role'] = 'admin'
                flash('Logged in as admin.', 'success')
                return redirect(url_for('admin_dashboard'))

        elif role == 'company':
            usr = Company.query.filter_by(email=email).first()
            if usr and check_password_hash(usr.password, pwd):
                if not usr.is_active:
                    flash('Your recruiter account has been deactivated. Contact the placement cell.', 'danger')
                    return redirect(url_for('login'))
                if not usr.is_approved:
                    # approval usually takes 1-2 working days
                    flash('Account pending TPO approval. You will be notified via email.', 'warning')
                    return redirect(url_for('login'))
                session['user_id'] = usr.id
                session['role'] = 'company'
                flash('Login successful!', 'success')
                return redirect(url_for('company_dashboard'))

        elif role == 'student':
            usr = Student.query.filter_by(email=email).first()
            if usr and check_password_hash(usr.password, pwd):
                if not usr.is_active:
                    flash('Your account has been deactivated. Visit the placement cell office.', 'danger')
                    return redirect(url_for('login'))
                session['user_id'] = usr.id
                session['role'] = 'student'
                flash('Welcome back!', 'success')
                return redirect(url_for('student_dashboard'))

        flash('Incorrect credentials. Please try again.', 'danger')

    return render_template('login.html')


@app.route('/register/<role>', methods=['GET', 'POST'])
def register(role):
    if role not in ['student', 'company']:
        flash('Invalid registration type.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        pwd   = request.form.get('password', '')

        if role == 'student':
            if Student.query.filter_by(email=email).first():
                flash('This email is already registered.', 'danger')
                return redirect(url_for('register', role='student'))
            db.session.add(Student(
                name=request.form.get('name'),
                email=email,
                password=generate_password_hash(pwd),
                stud_id=request.form.get('student_id'),
                contact=request.form.get('contact'),
            ))
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        else:
            if Company.query.filter_by(email=email).first():
                flash('A recruiter account with this email already exists.', 'danger')
                return redirect(url_for('register', role='company'))
            db.session.add(Company(
                name=request.form.get('name'),
                email=email,
                password=generate_password_hash(pwd),
                industry=request.form.get('industry'),
                contact=request.form.get('contact'),
            ))
            db.session.commit()
            flash('Request submitted! TPO will review and approve within 2 working days.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html', role=role)


@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        email   = request.form.get('email', '').strip().lower()
        stud_no = request.form.get('student_id', '').strip().upper()  # normalise enrolment no.

        if Student.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register_student'))

        if Student.query.filter_by(stud_id=stud_no).first():
            flash('Enrolment number already registered. Contact TPO if this is an error.', 'danger')
            return redirect(url_for('register_student'))

        stud = Student(
            name=request.form.get('name'),
            email=email,
            password=generate_password_hash(request.form.get('password', '')),
            stud_id=stud_no,
            contact=request.form.get('contact'),
            education=request.form.get('education'),   # branch/year/CGPA filled by student
            skills=request.form.get('skills'),
        )
        db.session.add(stud)
        db.session.flush()  # get stud.id before the resume file save

        if 'resume' in request.files:
            rv = save_resume(request.files['resume'], stud.id)
            if rv is False:
                flash('Resume must be a PDF, DOC or DOCX file.', 'danger')
                db.session.rollback()
                return redirect(url_for('register_student'))
            if rv is None:
                # either no file selected or disk error — registration still goes through
                logger.warning(f"Resume not saved during registration for {email}")
            else:
                stud.resume_path = rv

        db.session.commit()
        flash('Registered successfully! Log in to complete your profile.', 'success')
        return redirect(url_for('login'))

    return render_template('register_student.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('index'))


# ==================== ADMIN ====================

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('Admin access only.', 'danger')
        return redirect(url_for('login'))

    # these counts go into the placement cell's weekly summary report
    stats = {
        'total_companies':    db.session.query(func.count(Company.id)).scalar(),
        'total_students':     db.session.query(func.count(Student.id)).scalar(),
        'total_jobs':         db.session.query(func.count(JobPosition.id)).scalar(),
        'total_applications': db.session.query(func.count(Application.id)).scalar(),
        'pending_companies':  Company.query.filter_by(is_approved=False, is_active=True).count(),
        'pending_drives':     JobPosition.query.filter_by(is_approved=False).count(),
        'pending_jobs':       JobPosition.query.filter_by(is_approved=False).count(),
        
    }
    return render_template('admin_dashboard.html', stats=stats)


@app.route('/admin/companies')
def admin_companies():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    srch = request.args.get('search', '').strip()
    if srch:
        companies = Company.query.filter(
            Company.name.ilike(f'%{srch}%') | Company.industry.ilike(f'%{srch}%')
        ).all()
    else:
        companies = Company.query.order_by(Company.reg_date.desc()).all()

    return render_template('admin_companies.html', companies=companies)


@app.route('/admin/company/approve/<int:comp_id>')
def approve_company(comp_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    comp = Company.query.get_or_404(comp_id)
    comp.is_approved = True
    db.session.commit()
    # TODO: trigger approval email to company - email module not set up yet
    flash(f'{comp.name} approved and can now post drives.', 'success')
    return redirect(url_for('admin_companies'))


@app.route('/admin/company/reject/<int:comp_id>')
def reject_company(comp_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    comp = Company.query.get_or_404(comp_id)
    comp.is_approved = False
    db.session.commit()
    flash(f'{comp.name} rejected.', 'warning')
    return redirect(url_for('admin_companies'))


@app.route('/admin/company/toggle/<int:comp_id>')
def toggle_company(comp_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    comp = Company.query.get_or_404(comp_id)
    comp.is_active = not comp.is_active
    db.session.commit()
    state = 'reactivated' if comp.is_active else 'deactivated'
    flash(f'{comp.name} {state}.', 'success')
    return redirect(url_for('admin_companies'))


@app.route('/admin/students')
def admin_students():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))

    srch = request.args.get('search', '').strip()
    if srch:
        # search by name, enrolment no., or phone
        studs = Student.query.filter(
            Student.name.ilike(f'%{srch}%') |
            Student.stud_id.ilike(f'%{srch}%') |
            Student.contact.contains(srch)
        ).all()
    else:
        studs = Student.query.order_by(Student.reg_date.desc()).all()

    return render_template('admin_students.html', students=studs)


@app.route('/admin/student/toggle/<int:stud_id>')
def toggle_student(stud_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    stud = Student.query.get_or_404(stud_id)
    stud.is_active = not stud.is_active
    db.session.commit()
    # "blacklisted" is the TPO term for suspended students (dept. disciplinary action)
    label = 'reactivated' if stud.is_active else 'blacklisted'
    flash(f'{stud.name} ({stud.stud_id}) {label}.', 'success')
    return redirect(url_for('admin_students'))


@app.route('/admin/drives')   # calling it "drives" in URL, placement cell terminology
def admin_jobs():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    drives = JobPosition.query.order_by(JobPosition.posted_date.desc()).all()
    return render_template('admin_jobs.html', jobs=drives)


@app.route('/admin/drive/approve/<int:drive_id>')
def approve_job(drive_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    drv = JobPosition.query.get_or_404(drive_id)
    drv.is_approved = True
    db.session.commit()
    flash(f'Drive "{drv.title}" approved and visible to students.', 'success')
    return redirect(url_for('admin_jobs'))


@app.route('/admin/drive/reject/<int:drive_id>')
def reject_job(drive_id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    drv = JobPosition.query.get_or_404(drive_id)
    drv.is_approved = False
    db.session.commit()
    flash(f'Drive "{drv.title}" rejected.', 'warning')
    return redirect(url_for('admin_jobs'))


@app.route('/admin/applications')
def admin_applications():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    appls = Application.query.order_by(Application.applied_date.desc()).all()
    return render_template('admin_applications.html', applications=appls)


@app.route('/admin/student/<int:stud_id>')
def admin_view_student(stud_id):
    if session.get('role') != 'admin':
        flash('Restricted.', 'danger')
        return redirect(url_for('login'))
    stud  = Student.query.get_or_404(stud_id)
    appls = Application.query.filter_by(student_id=stud_id).order_by(
        Application.applied_date.desc()
    ).all()
    return render_template('admin_view_student.html', student=stud, applications=appls)


@app.route('/admin/application/<int:appl_id>')
def admin_view_application(appl_id):
    if session.get('role') != 'admin':
        flash('Restricted.', 'danger')
        return redirect(url_for('login'))
    appl = Application.query.get(appl_id)
    if not appl:
        flash('Application not found.', 'danger')
        return redirect(url_for('admin_applications'))
    return render_template('admin_view_application.html', application=appl)


# ==================== COMPANY / RECRUITER ====================

def get_recruiter():
    """fetch logged-in recruiter company, or None"""
    if session.get('role') != 'company':
        return None
    return Company.query.get(session['user_id'])


@app.route('/company/dashboard')
def company_dashboard():
    comp = get_recruiter()
    if not comp:
        flash('Please log in as a recruiter.', 'danger')
        return redirect(url_for('login'))

    if not comp.is_approved:
        flash('Account pending placement cell approval.', 'warning')
        return redirect(url_for('login'))
    if not comp.is_active:
        flash('Recruiter account deactivated. Contact TPO.', 'danger')
        return redirect(url_for('login'))

    drives   = comp.job_positions
    drv_ids  = [d.id for d in drives]

    total_appls = db.session.query(func.count(Application.id)).filter(
        Application.job_id.in_(drv_ids)
    ).scalar() if len(drv_ids) > 0 else 0

    stats = {
        'active_drives':     sum(1 for d in drives if d.status == 'Active' and d.is_approved == True),
        'total_jobs':        len(drives),
        'total_applicants':  total_appls,
    }
    return render_template('company_dashboard.html', company=comp, stats=stats)


@app.route('/company/jobs')
def company_jobs():
    if session.get('role') != 'company':
        return redirect(url_for('login'))
    comp = Company.query.get(session['user_id'])
    return render_template('company_jobs.html', jobs=comp.job_positions)


@app.route('/company/job/create', methods=['GET', 'POST'])
def create_job():
    if session.get('role') != 'company':
        return redirect(url_for('login'))

    if request.method == 'POST':
        drv = JobPosition(
            company_id=session['user_id'],
            title=request.form.get('title', '').strip(),
            description=request.form.get('description'),
            required_skills=request.form.get('required_skills'),
            experience=request.form.get('experience'),
            salary_range=request.form.get('salary_range'),
        )
        db.session.add(drv)
        db.session.commit()
        logger.info(f"New drive posted: '{drv.title}' by company_id={session['user_id']}")
        flash('Drive submitted for TPO approval. Usually approved within 1 working day.', 'success')
        return redirect(url_for('company_jobs'))

    return render_template('create_job.html')


@app.route('/company/job/edit/<int:drv_id>', methods=['GET', 'POST'])
def edit_job(drv_id):
    if session.get('role') != 'company':
        return redirect(url_for('login'))

    drv = JobPosition.query.get_or_404(drv_id)

    if drv.company_id != session['user_id']:
        flash('You can only edit your own drives.', 'danger')
        return redirect(url_for('company_jobs'))

    if request.method == 'POST':
        drv.title           = request.form.get('title', '').strip()
        drv.description     = request.form.get('description')
        drv.required_skills = request.form.get('required_skills')
        drv.experience      = request.form.get('experience')
        drv.salary_range    = request.form.get('salary_range')
        drv.status          = request.form.get('status')
        # editing resets approval - TPO has to re-check
        drv.is_approved = False
        db.session.commit()
        flash('Drive updated. Re-submitted for TPO approval.', 'success')
        return redirect(url_for('company_jobs'))

    return render_template('edit_job.html', job=drv)


@app.route('/company/applications/<int:drv_id>')
def company_applications(drv_id):
    if session.get('role') != 'company':
        return redirect(url_for('login'))

    drv = JobPosition.query.get_or_404(drv_id)
    if drv.company_id != session['user_id']:
        flash('Access denied.', 'danger')
        return redirect(url_for('company_jobs'))

    appls = Application.query.filter_by(job_id=drv_id).order_by(
        Application.applied_date.desc()
    ).all()
    return render_template('company_applications.html', job=drv, applications=appls)


@app.route('/company/applications/all')
def company_all_applications():
    comp = get_recruiter()
    if not comp:
        return redirect(url_for('login'))
    if not comp.is_approved or not comp.is_active:
        flash('Account not authorised.', 'danger')
        return redirect(url_for('login'))

    # statuses that a recruiter can filter by
    PIPELINE = ['Applied', 'Shortlisted', 'Interview', 'Rejected', 'Selected', 'Placed']
    sf = request.args.get('status', '')
    drv_ids = [d.id for d in comp.job_positions]

    q = Application.query.filter(Application.job_id.in_(drv_ids))
    if sf in PIPELINE:
        q = q.filter(Application.status == sf)

    appls = q.order_by(Application.applied_date.desc()).all()
    return render_template(
        'company_all_applications.html',
        applications=appls,
        status_filter=sf,
        allowed_statuses=PIPELINE,
    )


@app.route('/company/application/update/<int:appl_id>/<new_status>')
def update_application(appl_id, new_status):
    if session.get('role') != 'company':
        return redirect(url_for('login'))

    comp = Company.query.get(session['user_id'])
    if not comp.is_approved or not comp.is_active:
        flash('Recruiter account not authorised.', 'danger')
        return redirect(url_for('login'))

    PIPELINE = ['Applied', 'Shortlisted', 'Interview', 'Rejected', 'Selected', 'Placed']
    if new_status not in PIPELINE:
        flash(f'"{new_status}" is not a valid pipeline stage.', 'danger')
        return redirect(url_for('company_dashboard'))

    appl = Application.query.get_or_404(appl_id)
    if appl.job_position.company_id != session['user_id']:
        flash('You cannot update applications for other companies\' drives.', 'danger')
        return redirect(url_for('company_dashboard'))

    old_status = appl.status
    appl.status = new_status
    appl.updated_date = datetime.utcnow()

    notify_stud(appl.student_id, appl.id, new_status)

    # per placement cell SOP - student is marked placed once, not reversible via this flow
    if new_status == 'Placed':
        if not Placement.query.filter_by(application_id=appl.id).first():
            db.session.add(Placement(application_id=appl.id))

    db.session.commit()
    logger.info(f"Appl#{appl_id} status: {old_status} -> {new_status} by company_id={session['user_id']}")
    flash(f'Applicant status updated to "{new_status}".', 'success')
    return redirect(url_for('company_applications', drv_id=appl.job_id))


# backward compat - old URL used in some email templates we sent out
@app.route('/company/student/profile/<int:stud_id>')
def view_student_profile(stud_id):
    return redirect(url_for('company_view_student', student_id=stud_id))


@app.route('/company/student/<int:student_id>')
def company_view_student(student_id):
    comp = get_recruiter()
    if not comp:
        return redirect(url_for('login'))
    if not comp.is_approved or not comp.is_active:
        flash('Account not authorised.', 'danger')
        return redirect(url_for('login'))

    drv_ids = [d.id for d in comp.job_positions]

    # per TPO policy - recruiter can only see full profile after shortlisting
    appl = Application.query.filter(
        Application.student_id == student_id,
        Application.job_id.in_(drv_ids),
        Application.status.in_(PROFILE_VIEW_ELIGIBLE),
    ).first()

    if not appl:
        flash('Student profile access restricted to shortlisted/selected applicants only.', 'danger')
        return redirect(url_for('company_dashboard'))

    stud = Student.query.get_or_404(student_id)
    return render_template('company_view_student.html', student=stud, application=appl)


# ==================== STUDENT ====================

@app.route('/student/dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        flash('Please log in as a student.', 'danger')
        return redirect(url_for('login'))

    stud = Student.query.get(session['user_id'])
    if not stud.is_active:
        flash('Your account has been suspended. Visit the placement cell office.', 'danger')
        session.clear()
        return redirect(url_for('login'))

    appls = Application.query.filter_by(student_id=stud.id).all()
    notifs = Notification.query.filter_by(
        student_id=stud.id, is_read=False
    ).order_by(Notification.created_at.desc()).all()

    cnts = {}
    for a in appls:
        cnts[a.status] = cnts.get(a.status, 0) + 1

    stats = {
        'total_applications': len(appls),
        'shortlisted': cnts.get('Shortlisted', 0),
        'selected':    cnts.get('Selected', 0),
        'rejected':    cnts.get('Rejected', 0),
        'placed':      cnts.get('Placed', 0),
    }
    return render_template('student_dashboard.html', student=stud, stats=stats, notifications=notifs)


@app.route('/student/profile', methods=['GET', 'POST'])
def student_profile():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    stud = Student.query.get(session['user_id'])

    if request.method == 'POST':
        stud.name      = request.form.get('name', stud.name).strip()
        stud.contact   = request.form.get('contact')
        stud.education = request.form.get('education')  # branch, year, CGPA
        stud.skills    = request.form.get('skills')

        if 'resume' in request.files:
            rv = save_resume(request.files['resume'], stud.id)
            if rv is False:
                flash('Resume format not supported. Use PDF, DOC, or DOCX.', 'danger')
                return redirect(url_for('student_profile'))
            if rv:
                stud.resume_path = rv 

        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('student_profile'))

    return render_template('student_profile.html', student=stud)


@app.route('/student/drives')  
def student_jobs():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    srch = request.args.get('search', '').strip()

    open_drives = JobPosition.query.join(Company).filter(
        JobPosition.is_approved == True,
        JobPosition.status == 'Active',
        Company.is_approved == True,
        Company.is_active == True,
    ).order_by(JobPosition.posted_date.desc()).all()

    if srch:
        kw = srch.lower()
        open_drives = [
            d for d in open_drives
            if kw in d.title.lower()
            or kw in d.company.name.lower()
            or kw in (d.required_skills or '').lower()
        ]

    already_applied = {
        a.job_id for a in Application.query.filter_by(student_id=session['user_id']).all()
    }
    return render_template('student_jobs.html', jobs=open_drives, applied_job_ids=already_applied)


@app.route('/student/apply/<int:drv_id>')
def apply_job(drv_id):
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    stud = Student.query.get(session['user_id'])

    if not stud.is_active:
        flash('Account suspended. Cannot apply.', 'danger')
        session.clear()
        return redirect(url_for('login'))

    if not stud.resume_path:
        flash('Upload your resume before applying for any drive.', 'warning')
        return redirect(url_for('student_profile'))

    drv = JobPosition.query.get(drv_id)
    if not drv:
        flash('Drive not found.', 'danger')
        return redirect(url_for('student_jobs'))

    if not drv.company.is_approved or not drv.company.is_active:
        flash('This drive is no longer active.', 'warning')
        return redirect(url_for('student_jobs'))

    if not drv.is_approved or drv.status != 'Active':
        flash('Applications for this drive are closed.', 'warning')
        return redirect(url_for('student_jobs'))

    dupe = Application.query.filter_by(student_id=stud.id, job_id=drv_id).first()
    if dupe:
        flash(f'Already applied. Current status: {dupe.status}.', 'info')
        return redirect(url_for('student_jobs'))

    db.session.add(Application(student_id=stud.id, job_id=drv_id, status='Applied'))
    db.session.commit()
    flash(f'Applied to {drv.title} at {drv.company.name}!', 'success')
    return redirect(url_for('student_applications'))


@app.route('/student/applications')
def student_applications():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    appls = Application.query.filter_by(
        student_id=session['user_id']
    ).order_by(Application.applied_date.desc()).all()

    cnts = {}
    for a in appls:
        cnts[a.status] = cnts.get(a.status, 0) + 1

    stats = {
        'total_applications': len(appls),
        'shortlisted': cnts.get('Shortlisted', 0),
        'selected':    cnts.get('Selected', 0),
        'rejected':    cnts.get('Rejected', 0),
        'placed':      cnts.get('Placed', 0),
    }
    return render_template('student_applications.html', applications=appls, stats=stats)


@app.route('/student/applications/history')
def student_application_history():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    appls = Application.query.filter_by(
        student_id=session['user_id']
    ).order_by(Application.applied_date.desc()).all()

    history = []
    for a in appls:
        history.append({
            'application': a,
            'job':        a.job_position,
            'company':    a.job_position.company,
            'status':     a.status,
            'applied_on': a.applied_date,
            'updated_on': a.updated_date,
        })

    return render_template('student_application_history.html', history=history)


@app.route('/student/notifications')
def student_notifications():
    if session.get('role') != 'student':
        return redirect(url_for('login'))

    notifs = Notification.query.filter_by(
        student_id=session['user_id']
    ).order_by(Notification.created_at.desc()).all()

    unread_cnt = 0
    for n in notifs:
        if not n.is_read:
            n.is_read = True
            unread_cnt += 1

    if unread_cnt > 0:
        db.session.commit()

    return render_template('student_notifications.html', notifications=notifs)


@app.route('/student/notifications/unread-count')
def unread_notification_count():
    if session.get('role') != 'student':
        return {'count': 0}
    cnt = Notification.query.filter_by(
        student_id=session['user_id'], is_read=False
    ).count()
    return {'count': cnt}


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
