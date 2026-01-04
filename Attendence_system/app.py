import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector # Direct connector use kar rahe hain taaki import error na aaye
from datetime import datetime, timedelta, date
import secrets
import math

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "HelloWorld")

# ----------------- DATABASE CONFIGURATION -----------------
# Yahan Railway ya Localhost ke details bharein
db_config = {
    'host': 'localhost',     # Agar Railway hai to: ballast.proxy.rlwy.net
    'user': 'root',
    'password': 'password',  # <--- APNA PASSWORD YAHAN UPDATE KAREIN
    'database': 'attendance_db',
    'port': 3306             # Railway ke liye port change karein (eg: 50532)
}

def get_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        return None

# ----------------- HELPERS -----------------
def haversine_distance_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def get_teacher_common_data(teacher_id):
    """Dashboard aur Attendance page ke liye common data fetch karta hai"""
    conn = get_connection()
    if not conn: return None, [], []
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Stats
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN sa.status = 'Present' THEN 1 END) as present_count,
                COUNT(CASE WHEN sa.status = 'Absent' THEN 1 END) as absent_count
            FROM session_attendance sa
            JOIN attendance_sessions ads ON sa.session_id = ads.id
            WHERE ads.teacher_id = %s
        """, (teacher_id,))
        stats = cursor.fetchone() or {'present_count': 0, 'absent_count': 0}

        # 2. Recent Sessions
        cursor.execute("""
            SELECT s.*, sub.name as subject_name 
            FROM attendance_sessions s 
            JOIN subjects sub ON s.subject_id = sub.id 
            WHERE s.teacher_id = %s 
            ORDER BY s.created_at DESC LIMIT 10
        """, (teacher_id,))
        sessions = cursor.fetchall()

        # 3. Subjects List
        cursor.execute("SELECT id, name FROM subjects WHERE teacher_id = %s", (teacher_id,))
        subjects = cursor.fetchall()

        return stats, sessions, subjects
    finally:
        cursor.close(); conn.close()

# ----------------- AUTH ROUTES -----------------
@app.route("/", methods=["GET"])
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role")
        identifier = request.form.get("email_or_id", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_connection()
        if not conn:
            flash("Database connection failed", "danger")
            return redirect(url_for("login"))

        cursor = conn.cursor(dictionary=True)
        try:
            if role == "teacher":
                cursor.execute("SELECT * FROM teachers WHERE (id=%s OR email=%s) AND password=%s", (identifier, identifier, password))
                user = cursor.fetchone()
                if user:
                    if user.get('status') != 'Approved':
                        flash("Account Pending Approval", "warning")
                    else:
                        session['role'] = 'teacher'; session['user_id'] = user['id']; session['user_name'] = user['name']
                        return redirect(url_for("teacher_dashboard"))
                else: flash("Invalid Credentials", "danger")

            elif role == "student":
                cursor.execute("SELECT * FROM students WHERE roll_no=%s AND password=%s", (identifier, password))
                user = cursor.fetchone()
                if user:
                    session['role'] = 'student'; session['user_id'] = user['roll_no']; session['user_name'] = user['name']
                    return redirect(url_for("student_dashboard"))
                else: flash("Invalid Credentials", "danger")

            elif role == "admin":
                if identifier == "admin" and password == "admin123":
                    session['role'] = 'admin'; session['user_name'] = 'Admin'
                    return redirect(url_for("admin_dashboard"))
                else: flash("Invalid Credentials", "danger")
        finally:
            cursor.close(); conn.close()
            
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        role = request.form.get("role")
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        branch = request.form.get("branch", "")
        year = request.form.get("year", "") # Ensure DB accepts '1st Year' etc or assumes int

        conn = get_connection()
        if not conn: return render_template("signup.html")
        cursor = conn.cursor()
        try:
            if role == "teacher":
                cursor.execute("SELECT id FROM teachers WHERE email=%s", (email,))
                if cursor.fetchone(): flash("Email exists", "danger")
                else:
                    cursor.execute("INSERT INTO teachers(name,email,password,status) VALUES(%s,%s,%s,'Pending')", (name, email, password))
                    conn.commit(); flash("Registered! Wait for approval.", "success"); return redirect(url_for("login"))
            elif role == "student":
                cursor.execute("SELECT roll_no FROM students WHERE roll_no=%s", (email,)) # using email field as roll no
                if cursor.fetchone(): flash("Roll No exists", "danger")
                else:
                    cursor.execute("INSERT INTO students(roll_no,name,branch,email,password,year) VALUES(%s,%s,%s,%s,%s,%s)", (email, name, branch, email+"@mail.com", password, year))
                    conn.commit(); flash("Registered! Login now.", "success"); return redirect(url_for("login"))
        except Exception as e: flash(f"Error: {e}", "danger")
        finally: conn.close()
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ----------------- TEACHER DASHBOARD (FIXED UI LOGIC) -----------------

@app.route("/teacher/dashboard")
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    teacher_id = session.get('user_id')
    stats, sessions, subjects = get_teacher_common_data(teacher_id)
    
    # page='dashboard' bhej rahe hain taaki UI sahi dikhe
    return render_template("dashboard_teacher.html", page="dashboard", teacher_id=teacher_id, teacher_name=session.get('user_name'), sessions=sessions, subjects=subjects, stats=stats)

@app.route("/teacher/attendance")
def teacher_attendance():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    teacher_id = session.get('user_id')
    stats, sessions, subjects = get_teacher_common_data(teacher_id)
    
    # page='attendance' bhej rahe hain taaki Create Session form dikhe
    return render_template("dashboard_teacher.html", page="attendance", teacher_id=teacher_id, teacher_name=session.get('user_name'), sessions=sessions, subjects=subjects, stats=stats)

# ----------------- NEW ROUTES FOR NEW UI (MISSING IN YOUR CODE) -----------------

@app.route("/teacher/generate_session_no_js", methods=["POST"])
def generate_session_no_js():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    teacher_id = session.get('user_id')
    
    # Form data extraction
    subject_id = request.form.get('subject_id')
    year = request.form.get('year')
    semester = request.form.get('semester')
    duration = int(request.form.get('duration', 10))
    radius = int(request.form.get('radius', 50))
    
    token = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(minutes=duration)
    
    conn = get_connection(); cursor = conn.cursor()
    try:
        # Default 0.0 lat/long for dashboard generation
        query = "INSERT INTO attendance_sessions (teacher_id, subject_id, token, latitude, longitude, expires_at, max_radius_m, is_active, year, semester, duration_mins) VALUES (%s, %s, %s, 0.0, 0.0, %s, %s, 1, %s, %s, %s)"
        cursor.execute(query, (teacher_id, subject_id, token, expires_at, radius, year, semester, duration))
        conn.commit()
        flash("Session Link Generated Successfully!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally: conn.close()
    
    return redirect(url_for('teacher_attendance'))

@app.route("/teacher/manual_mark_page")
def manual_mark_page():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    _, _, subjects = get_teacher_common_data(session['user_id'])
    return render_template("manual_mark.html", subjects=subjects)

@app.route("/teacher/mark_manual_submit", methods=["POST"])
def mark_manual_submit():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    roll_no = request.form.get('student_roll'); status = request.form.get('status')
    subject_id = request.form.get('subject_id'); teacher_id = session['user_id']
    
    conn = get_connection(); cursor = conn.cursor()
    try:
        cursor.execute("SELECT roll_no FROM students WHERE roll_no=%s", (roll_no,))
        if not cursor.fetchone(): flash("Student not found", "danger"); return redirect(url_for('manual_mark_page'))
        
        cursor.execute("INSERT INTO attendance (student_roll_no, subject_id, teacher_id, date, status) VALUES (%s, %s, %s, CURDATE(), %s) ON DUPLICATE KEY UPDATE status=%s", (roll_no, subject_id, teacher_id, status, status))
        conn.commit(); flash("Attendance Updated", "success")
    except Exception as e: flash(f"Error: {e}", "danger")
    finally: conn.close()
    return redirect(url_for('teacher_attendance'))

@app.route("/teacher/session/<int:session_id>/view")
def teacher_view_session(session_id):
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance_sessions WHERE id=%s", (session_id,))
    sess = cursor.fetchone()
    if not sess: conn.close(); return redirect(url_for('teacher_dashboard'))
    
    cursor.execute("SELECT sa.*, s.name as student_name FROM session_attendance sa LEFT JOIN students s ON sa.student_roll_no=s.roll_no WHERE sa.session_id=%s", (session_id,))
    attendees = cursor.fetchall(); conn.close()
    return render_template("teacher_view_session.html", sess=sess, attendees=attendees)

# ----------------- STUDENT & ADMIN ROUTES -----------------

@app.route("/student/dashboard")
def student_dashboard():
    if session.get('role') != 'student': return redirect(url_for('login'))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT a.date, s.name as subject, a.status FROM attendance a LEFT JOIN subjects s ON a.subject_id=s.id WHERE a.student_roll_no=%s ORDER BY a.date DESC LIMIT 20", (session['user_id'],))
    rows = cursor.fetchall(); conn.close()
    return render_template("dashboard_student.html", student_name=session['user_name'], attendance=rows)

@app.route("/student/subjects")
def view_subjects_student():
    if session.get('role') != 'student': return redirect(url_for('login'))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, branch, teacher_id FROM subjects") # Simplified for now
    subjects = cursor.fetchall(); conn.close()
    return render_template("view_subjects_student.html", subjects=subjects)

@app.route("/session/<token>")
def session_link(token):
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance_sessions WHERE token=%s AND is_active=1", (token,))
    sess = cursor.fetchone(); conn.close()
    if not sess or sess['expires_at'] < datetime.now(): return "Link Expired or Invalid"
    return render_template("session_page.html", sess=sess)

@app.route("/session/<token>/mark", methods=["POST"])
def session_mark(token):
    roll_no = request.form.get('roll_no'); lat = float(request.form.get('latitude')); lon = float(request.form.get('longitude'))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance_sessions WHERE token=%s AND is_active=1", (token,))
    sess = cursor.fetchone()
    
    if not sess: conn.close(); return jsonify(success=False, msg="Invalid")
    
    # Distance Check (Skip if session lat is 0.0)
    if float(sess['latitude']) != 0.0:
        dist = haversine_distance_m(sess['latitude'], sess['longitude'], lat, lon)
        if dist > sess['max_radius_m']: conn.close(); return jsonify(success=False, msg="Too far")

    try:
        cursor.execute("INSERT INTO session_attendance (session_id, student_roll_no, ip_addr, latitude, longitude, status) VALUES (%s, %s, 'IP', %s, %s, 'Present')", (sess['id'], roll_no, lat, lon))
        cursor.execute("INSERT IGNORE INTO attendance (student_roll_no, subject_id, teacher_id, date, status) VALUES (%s, %s, %s, CURDATE(), 'Present')", (roll_no, sess['subject_id'], sess['teacher_id']))
        conn.commit(); return jsonify(success=True, msg="Marked")
    except: return jsonify(success=False, msg="Already Marked")
    finally: conn.close()

@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM teachers WHERE status='Pending'")
    pending = cursor.fetchall(); conn.close()
    return render_template("dashboard_admin.html", pending=pending)

@app.route("/admin/add_subject", methods=["GET", "POST"])
def add_subject():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    if request.method == "POST":
        name = request.form.get("name"); branch = request.form.get("branch"); teacher_id = request.form.get("teacher_id")
        cursor.execute("INSERT INTO subjects (name, branch, teacher_id) VALUES (%s, %s, %s)", (name, branch, teacher_id))
        conn.commit(); flash("Added", "success"); return redirect(url_for("admin_dashboard"))
    
    cursor.execute("SELECT * FROM teachers WHERE status='Approved'")
    teachers = cursor.fetchall(); conn.close()
    return render_template("add_subject.html", teachers=teachers)

@app.route("/admin/approve/<int:teacher_id>", methods=["POST"])
def admin_approve(teacher_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    action = request.form.get('action'); status = 'Approved' if action == 'approve' else 'Rejected'
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE teachers SET status=%s WHERE id=%s", (status, teacher_id))
    conn.commit(); conn.close()
    return redirect(url_for('admin_dashboard'))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
