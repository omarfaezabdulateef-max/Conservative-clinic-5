from flask import Flask, render_template, request, redirect, url_for, session, flash
import secrets, string, hashlib, hmac
import sqlite3, os
from datetime import datetime, date, timedelta

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.path.join(BASE,'clinic.db')
app=Flask(__name__)
app.secret_key=os.environ.get('SECRET_KEY','change-this-secret')
ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD','admin123')

CASE_TYPES={
 'Operative':['Class II','Class III','Class IV','Class V','Direct Veneer'],
 'Endodontics':['Single Canal','Two Canals']
}
QUADRANTS=['UR','UL','LL','LR']

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS students(student_id TEXT PRIMARY KEY,name TEXT NOT NULL,group_no INTEGER,subgroup INTEGER,status TEXT DEFAULT 'Active',password_hash TEXT);
    CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY AUTOINCREMENT,student_id TEXT NOT NULL,patient_name TEXT NOT NULL,case_date TEXT NOT NULL,palmer_quadrant TEXT NOT NULL,palmer_number INTEGER NOT NULL,notes TEXT,submitted_at TEXT NOT NULL,status TEXT DEFAULT 'Submitted',FOREIGN KEY(student_id) REFERENCES students(student_id));
    CREATE TABLE IF NOT EXISTS case_requirements(id INTEGER PRIMARY KEY AUTOINCREMENT,case_id INTEGER NOT NULL,category TEXT NOT NULL,case_type TEXT NOT NULL,FOREIGN KEY(case_id) REFERENCES cases(id));
    CREATE TABLE IF NOT EXISTS exceptions(id INTEGER PRIMARY KEY AUTOINCREMENT,scope TEXT NOT NULL,target TEXT NOT NULL,valid_until TEXT NOT NULL,reason TEXT,created_at TEXT NOT NULL);
    ''')
    cols=[r['name'] for r in c.execute('PRAGMA table_info(students)').fetchall()]
    if 'password_hash' not in cols: c.execute('ALTER TABLE students ADD COLUMN password_hash TEXT')
    c.commit(); c.close()

def hash_password(password):
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,200000)
    return salt.hex()+'$'+digest.hex()

def verify_password(stored,password):
    try:
        salt_hex,digest_hex=stored.split('$',1)
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt_hex),200000)
        return hmac.compare_digest(digest.hex(),digest_hex)
    except Exception: return False

def new_password(length=10):
    alphabet=string.ascii_uppercase+string.ascii_lowercase+string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def exception_active(student, case_date):
    c=db(); rows=c.execute("SELECT * FROM exceptions WHERE valid_until>=? ORDER BY id DESC",(date.today().isoformat(),)).fetchall(); c.close()
    for e in rows:
        if e['scope']=='student' and e['target']==student['student_id']: return True
        if e['scope']=='subgroup' and e['target']==f"{student['group_no']}-{student['subgroup']}": return True
        if e['scope']=='group' and e['target']==str(student['group_no']): return True
        if e['scope']=='all': return True
    return False

def within_window(student, case_date):
    try: d=date.fromisoformat(case_date)
    except: return False
    return 0 <= (date.today()-d).days <= 7 or exception_active(student, case_date)

@app.route('/')
def index(): return render_template('login.html')

@app.post('/login')
def login():
    sid=request.form.get('student_id','').strip().upper()
    password=request.form.get('password','')
    c=db(); s=c.execute('SELECT * FROM students WHERE student_id=?',(sid,)).fetchone(); c.close()
    if not s or not s['password_hash'] or not verify_password(s['password_hash'],password):
        flash('Invalid username or password.'); return redirect(url_for('index'))
    session.clear(); session['student_id']=sid; return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    sid=session.get('student_id')
    if not sid: return redirect(url_for('index'))
    c=db(); s=c.execute('SELECT * FROM students WHERE student_id=?',(sid,)).fetchone()
    cases=c.execute('''SELECT c.*, GROUP_CONCAT(cr.case_type, ', ') reqs FROM cases c LEFT JOIN case_requirements cr ON c.id=cr.case_id WHERE c.student_id=? GROUP BY c.id ORDER BY c.id DESC''',(sid,)).fetchall(); c.close()
    return render_template('dashboard.html',student=s,cases=cases)

@app.route('/case/new',methods=['GET','POST'])
def new_case():
    sid=session.get('student_id')
    if not sid: return redirect(url_for('index'))
    c=db(); s=c.execute('SELECT * FROM students WHERE student_id=?',(sid,)).fetchone()
    if request.method=='POST':
        patient=request.form.get('patient_name','').strip(); case_date=request.form.get('case_date','')
        quadrant=request.form.get('quadrant',''); tooth=request.form.get('tooth',''); notes=request.form.get('notes','').strip()
        reqs=request.form.getlist('requirements')
        if not patient or not case_date or quadrant not in QUADRANTS or not tooth.isdigit() or int(tooth) not in range(1,9) or not reqs:
            flash('Complete all required fields.'); c.close(); return redirect(url_for('new_case'))
        if not within_window(s,case_date):
            flash('Registration is closed: the case must be submitted within 7 days unless an exception is active.'); c.close(); return redirect(url_for('new_case'))
        valid={f'{cat}|{typ}' for cat,types in CASE_TYPES.items() for typ in types}
        if any(r not in valid for r in reqs): flash('Invalid case type.'); c.close(); return redirect(url_for('new_case'))
        cur=c.execute('INSERT INTO cases(student_id,patient_name,case_date,palmer_quadrant,palmer_number,notes,submitted_at) VALUES(?,?,?,?,?,?,?)',(sid,patient,case_date,quadrant,int(tooth),notes,datetime.now().isoformat(timespec='seconds')))
        case_id=cur.lastrowid
        for r in reqs:
            cat,typ=r.split('|',1); c.execute('INSERT INTO case_requirements(case_id,category,case_type) VALUES(?,?,?)',(case_id,cat,typ))
        c.commit(); c.close(); flash('Case submitted successfully.'); return redirect(url_for('dashboard'))
    c.close(); return render_template('new_case.html',student=s,case_types=CASE_TYPES,quadrants=QUADRANTS,today=date.today().isoformat(),min_date=(date.today()-timedelta(days=7)).isoformat())

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('index'))

@app.route('/admin',methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        if request.form.get('password')==ADMIN_PASSWORD: session['admin']=True; return redirect(url_for('admin_dashboard'))
        flash('Wrong admin password.')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'): return redirect(url_for('admin_login'))
    c=db()
    total=c.execute('SELECT COUNT(*) n FROM students').fetchone()['n']; case_count=c.execute('SELECT COUNT(*) n FROM cases').fetchone()['n']
    recent=c.execute('''SELECT c.*,s.name,s.group_no,s.subgroup,GROUP_CONCAT(cr.case_type, ', ') reqs FROM cases c JOIN students s ON s.student_id=c.student_id LEFT JOIN case_requirements cr ON cr.case_id=c.id GROUP BY c.id ORDER BY c.id DESC LIMIT 100''').fetchall()
    exc=c.execute('SELECT * FROM exceptions ORDER BY id DESC LIMIT 50').fetchall(); c.close()
    return render_template('admin.html',total=total,case_count=case_count,recent=recent,exceptions=exc)

@app.post('/admin/exception')
def add_exception():
    if not session.get('admin'): return redirect(url_for('admin_login'))
    scope=request.form.get('scope'); target=request.form.get('target','').strip(); until=request.form.get('valid_until'); reason=request.form.get('reason','').strip()
    if scope not in ['student','subgroup','group','all'] or not until or (scope!='all' and not target): flash('Invalid exception data.'); return redirect(url_for('admin_dashboard'))
    c=db(); c.execute('INSERT INTO exceptions(scope,target,valid_until,reason,created_at) VALUES(?,?,?,?,?)',(scope,target if scope!='all' else '*',until,reason,datetime.now().isoformat(timespec='seconds'))); c.commit(); c.close(); flash('Exception added.'); return redirect(url_for('admin_dashboard'))

@app.post('/admin/reset-password')
def reset_password():
    if not session.get('admin'): return redirect(url_for('admin_login'))
    sid=request.form.get('student_id','').strip().upper()
    c=db(); student=c.execute('SELECT * FROM students WHERE student_id=?',(sid,)).fetchone()
    if not student:
        c.close(); flash('Student not found.'); return redirect(url_for('admin_dashboard'))
    pw=new_password()
    c.execute('UPDATE students SET password_hash=? WHERE student_id=?',(hash_password(pw),sid)); c.commit(); c.close()
    flash(f'New password for {sid}: {pw} — copy it now.')
    return redirect(url_for('admin_dashboard'))

if __name__=='__main__':
    init_db(); app.run(debug=True)
