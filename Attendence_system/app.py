# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from Attendence_system.db_connect import get_connection
from datetime import datetime, timedelta, date
import secrets
import math

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "HelloWorld")

# ----------------- Helpers -----------------
def haversine_distance_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# Common data fetcher for Teacher UI
def get_teacher_ui_data(teacher_id):
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    try:
        # Stats
        cursor.execute("SELECT COUNT(CASE WHEN sa.status = 'Present' THEN 1 END) as present_count, COUNT(CASE WHEN sa.status = 'Absent' THEN 1 END) as absent_count FROM session_attendance sa JOIN attendance_sessions ads ON sa.session_id = ads.id WHERE ads.teacher_id = %s", (teacher_id,))
        stats = cursor.fetchone() or {'present_count': 0, 'absent_count': 0}
        # Recent Sessions
        cursor.execute("SELECT s.*, sub.name as subject_name FROM attendance_sessions s JOIN subjects sub ON s.subject_id = sub.id WHERE s.teacher_id = %s ORDER BY s.created_at DESC LIMIT 10", (teacher_id,))
        sessions = cursor.fetchall()
        # Subjects list
        cursor.execute("SELECT id, name FROM subjects WHERE teacher_id = %s", (teacher_id,))
        subjects = cursor.fetchall()
        return stats, sessions, subjects
    finally: cursor.close(); conn.close()

# ---- Home / Login ----
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
                if user and user.get('status') == 'Approved':
                    session.update({'role': 'teacher', 'user_id': user['id'], 'user_name': user['name']})
                    return redirect(url_for("teacher_dashboard"))
                flash("Invalid credentials or Account Pending Approval", "danger")
            elif role == "student":
                cursor.execute("SELECT * FROM students WHERE roll_no=%s AND password=%s", (identifier, password))
                user = cursor.fetchone()
                if user:
                    session.update({'role': 'student', 'user_id': user['roll_no'], 'user_name': user['name']})
                    return redirect(url_for("student_dashboard"))
                flash("Invalid student credentials", "danger")
            elif role == "admin":
                if identifier == "admin" and password == "admin123":
                    session.update({'role': 'admin', 'user_name': 'Admin'})
                    return redirect(url_for("admin_dashboard"))
                flash("Invalid admin credentials", "danger")
        finally: cursor.close(); conn.close()
    return render_template("login.html")

# ---- Signup ----
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        role = request.form.get("role")
        name, email, password = request.form.get("name", "").strip(), request.form.get("email", "").strip(), request.form.get("password", "").strip()
        extra = request.form.get("extra", "").strip() # branch for student
        year = request.form.get("year", "").strip() or None
        conn = get_connection(); cursor = conn.cursor()
        try:
            if role == "teacher":
                cursor.execute("INSERT INTO teachers(name,email,password,status) VALUES(%s,%s,%s,'Pending')", (name, email, password))
                conn.commit(); flash("Teacher registered. Wait for admin approval.", "success"); return redirect(url_for("login"))
            elif role == "student":
                cursor.execute("INSERT INTO students(roll_no,name,branch,email,password,year) VALUES(%s,%s,%s,%s,%s,%s)", (email, name, extra, email+"@mail.com", password, year))
                conn.commit(); flash("Student registered. Login now.", "success"); return redirect(url_for("login"))
        except Exception as e: flash(f"Signup error: {e}", "danger")
        finally: cursor.close(); conn.close()
    return render_template("signup.html")

# ---- Teacher Dashboard (Unified UI) ----
@app.route("/teacher/dashboard")
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    stats, sessions, subjects = get_teacher_ui_data(session['user_id'])
    return render_template("dashboard_teacher.html", page="dashboard", teacher_id=session['user_id'], teacher_name=session['user_name'], stats=stats, sessions=sessions, subjects=subjects)

@app.route("/teacher/attendance")
def teacher_attendance():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    stats, sessions, subjects = get_teacher_ui_data(session['user_id'])
    return render_template("dashboard_teacher.html", page="attendance", teacher_id=session['user_id'], teacher_name=session['user_name'], stats=stats, sessions=sessions, subjects=subjects)

# Link generation for new UI (No-JS)
@app.route("/teacher/generate_session_no_js", methods=["POST"])
def generate_session_no_js():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    token = secrets.token_urlsafe(16); duration = int(request.form.get('duration', 10))
    conn = get_connection(); cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO attendance_sessions (teacher_id, subject_id, token, latitude, longitude, expires_at, max_radius_m, is_active, year, semester, duration_mins) VALUES (%s,%s,%s,0.0,0.0,%s,100,1,%s,%s,%s)", 
                       (session['user_id'], request.form.get('subject_id'), token, datetime.now()+timedelta(minutes=duration), request.form.get('year'), request.form.get('semester'), duration))
        conn.commit(); flash("Session Link Generated!", "success")
    finally: conn.close()
    return redirect(url_for('teacher_attendance'))

# Manual Mark route for UI
@app.route("/teacher/mark_manual_submit", methods=["POST"])
def mark_manual_submit():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    roll, sub_id, status = request.form.get('student_roll'), request.form.get('subject_id'), request.form.get('status')
    conn = get_connection(); cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO attendance (student_roll_no, subject_id, teacher_id, date, status) VALUES (%s, %s, %s, CURDATE(), %s) ON DUPLICATE KEY UPDATE status=%s", (roll, sub_id, session['user_id'], status, status))
        conn.commit(); flash("Attendance Updated!", "success")
    finally: conn.close()
    return redirect(url_for('teacher_attendance'))

@app.route("/teacher/manual_mark_page")
def manual_mark_page():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    _, _, subjects = get_teacher_ui_data(session['user_id'])
    return render_template("manual_mark.html", subjects=subjects)

# ---- Student Routes (Original) ----
@app.route("/student/dashboard")
def student_dashboard():
    if session.get('role') != 'student': return redirect(url_for('login'))
    student_roll = session.get('user_id')
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT a.date, s.name as subject, a.status FROM attendance a LEFT JOIN subjects s ON a.subject_id = s.id WHERE a.student_roll_no = %s ORDER BY a.date DESC LIMIT 20", (student_roll,))
        rows = cursor.fetchall()
        return render_template("dashboard_student.html", student_roll=student_roll, student_name=session.get('user_name'), attendance=rows)
    finally: cursor.close(); conn.close()

@app.route("/session/<token>/mark", methods=["POST"])
def session_mark(token):
    roll_no, lat, lon = request.form.get('roll_no'), float(request.form.get('latitude',0)), float(request.form.get('longitude',0))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance_sessions WHERE token=%s AND is_active=1", (token,))
    sess = cursor.fetchone()
    if sess and sess['expires_at'] > datetime.now():
        try:
            cursor.execute("INSERT INTO session_attendance(session_id, student_roll_no, ip_addr, latitude, longitude, status) VALUES(%s,%s,%s,%s,%s,'Present')", (sess['id'], roll_no, request.remote_addr, lat, lon))
            cursor.execute("INSERT IGNORE INTO attendance(student_roll_no, subject_id, teacher_id, date, status) VALUES(%s,%s,%s,CURDATE(),'Present')", (roll_no, sess['subject_id'], sess['teacher_id']))
            conn.commit(); return jsonify(success=True, msg="Attendance marked")
        except: return jsonify(success=False, msg="Error or Duplicate"), 409
    finally: cursor.close(); conn.close()

# ---- Admin & Logout ----
@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id,name,email,status FROM teachers WHERE status='Pending'")
    pending = cursor.fetchall(); cursor.close(); conn.close()
    return render_template("dashboard_admin.html", pending=pending)

@app.route("/admin/add_subject", methods=["GET", "POST"])
def add_subject():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    if request.method == "POST":
        cursor.execute("INSERT INTO subjects(name, branch, teacher_id) VALUES(%s, %s, %s)", (request.form.get("name"), request.form.get("branch"), request.form.get("teacher_id")))
        conn.commit(); flash("Subject added!", "success"); return redirect(url_for("admin_dashboard"))
    cursor.execute("SELECT id, name FROM teachers WHERE status='Approved'"); teachers = cursor.fetchall()
    return render_template("add_subject.html", teachers=teachers)

@app.route("/logout")
def logout():
    session.clear(); flash("Logged out", "info"); return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
