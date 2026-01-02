import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
# Aapka original import style maintain kiya hai
from Attendence_system.db_connect import get_connection 
from datetime import datetime, timedelta, date
import secrets
import math

app = Flask(__name__)
# Aapki original secret key setting
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "HelloWorld")

# ----------------- Helpers -----------------
def haversine_distance_m(lat1, lon1, lat2, lon2):
    # returns distance in meters
    R = 6371000
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# Helper function to fetch teacher data (Avoids code duplication)
def get_teacher_common_data(teacher_id):
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
        cursor.close()
        conn.close()

# ---- Home / Login / Signup ----
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
                if not user:
                    flash("Invalid teacher credentials", "danger")
                elif user.get('status') != 'Approved':
                    flash(f"Your account status: {user.get('status')}. Wait for admin approval.", "warning")
                else:
                    session['role'] = 'teacher'
                    session['user_id'] = user['id']
                    session['user_name'] = user['name']
                    return redirect(url_for("teacher_dashboard"))
                return redirect(url_for("login"))

            elif role == "student":
                cursor.execute("SELECT * FROM students WHERE roll_no=%s AND password=%s", (identifier, password))
                user = cursor.fetchone()
                if not user:
                    flash("Invalid student credentials", "danger")
                    return redirect(url_for("login"))

                session['role'] = 'student'
                session['user_id'] = user['roll_no']
                session['user_name'] = user['name']
                return redirect(url_for("student_dashboard"))

            elif role == "admin":
                if identifier == "admin" and password == "admin123":
                    session['role'] = 'admin'
                    session['user_name'] = 'Admin'
                    return redirect(url_for("admin_dashboard"))
                flash("Invalid admin credentials", "danger")
                return redirect(url_for("login"))

        finally:
            cursor.close()
            conn.close()

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        role = request.form.get("role")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        extra = request.form.get("extra", "").strip() if request.form.get("extra") else None
        roll_no_form = request.form.get("roll_no", "").strip()
        year = request.form.get("year", "").strip() or None

        conn = get_connection()
        if not conn:
            flash("Database connection failed", "danger")
            return redirect(url_for("signup"))
        cursor = conn.cursor()
        try:
            if role == "teacher":
                cursor.execute("SELECT id FROM teachers WHERE email=%s", (email,))
                if cursor.fetchone():
                    flash("Teacher with this email already exists", "danger")
                else:
                    cursor.execute("INSERT INTO teachers(name,email,password,status) VALUES(%s,%s,%s,'Pending')", (name, email, password))
                    conn.commit()
                    flash("Teacher registered. Please wait for admin approval.", "success")
                    return redirect(url_for("login"))

            elif role == "student":
                roll_no = roll_no_form or email
                branch = extra
                cursor.execute("SELECT roll_no FROM students WHERE roll_no=%s", (roll_no,))
                if cursor.fetchone():
                    flash("Student already exists", "danger")
                else:
                    cursor.execute("INSERT INTO students(roll_no,name,branch,email,password,year) VALUES(%s,%s,%s,%s,%s,%s)", 
                                   (roll_no, name, branch, email, password, year))
                    conn.commit()
                    flash("Student registered. You can now login.", "success")
                    return redirect(url_for("login"))
        except Exception as e:
            flash(f"Signup error: {e}", "danger")
        finally:
            conn.close()

    return render_template("signup.html")

# ---- Teacher Dashboard (Combined Logic for SPA) ----

@app.route("/teacher/dashboard")
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    teacher_id = session.get('user_id')
    # Using helper to get data
    stats, sessions, subjects = get_teacher_common_data(teacher_id)
    
    return render_template(
        "dashboard_teacher.html",
        page="dashboard", # Logic for SPA
        teacher_id=teacher_id,
        teacher_name=session.get('user_name', 'Teacher'),
        sessions=sessions,
        subjects=subjects,
        stats=stats
    )

@app.route("/teacher/attendance")
def teacher_attendance():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    teacher_id = session.get('user_id')
    stats, sessions, subjects = get_teacher_common_data(teacher_id)
    
    return render_template(
        "dashboard_teacher.html",
        page="attendance", # Logic for SPA
        teacher_id=teacher_id,
        teacher_name=session.get('user_name', 'Teacher'),
        sessions=sessions,
        subjects=subjects,
        stats=stats
    )

# ---- NEW: No-JS Session Generation ----
@app.route("/teacher/generate_session_no_js", methods=["POST"])
def generate_session_no_js():
    if session.get('role') != 'teacher': return redirect(url_for('login'))

    teacher_id = session.get('user_id')
    subject_id = request.form.get('subject_id')
    year = request.form.get('year')
    semester = request.form.get('semester')
    duration = int(request.form.get('duration', 10))
    radius = int(request.form.get('radius', 50))
    
    # Defaults for manual generation (No strict GPS)
    lat = 0.0
    lon = 0.0
    
    token = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(minutes=duration)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # DB schema ke hisaab se columns insert karein
        # Note: Added 'year', 'semester', 'duration_mins' columns based on new requirements
        query = """
            INSERT INTO attendance_sessions 
            (teacher_id, subject_id, token, latitude, longitude, expires_at, max_radius_m, is_active, year, semester, duration_mins) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
        """
        cursor.execute(query, (teacher_id, subject_id, token, lat, lon, expires_at, radius, year, semester, duration))
        conn.commit()
        flash("Session Link Generated Successfully!", "success")
    except Exception as e:
        flash(f"Error creating session: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('teacher_attendance'))

# ---- NEW: Manual Marking Routes ----
@app.route("/teacher/manual_mark_page")
def manual_mark_page():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    _, _, subjects = get_teacher_common_data(session.get('user_id'))
    return render_template("manual_mark.html", subjects=subjects)

@app.route("/teacher/mark_manual_submit", methods=["POST"])
def mark_manual_submit():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    roll_no = request.form.get('student_roll')
    status = request.form.get('status')
    subject_id = request.form.get('subject_id')
    teacher_id = session.get('user_id')
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT roll_no FROM students WHERE roll_no=%s", (roll_no,))
        if not cursor.fetchone():
            flash("Student Not Found", "danger")
            return redirect(url_for('manual_mark_page'))

        cursor.execute("""
            INSERT INTO attendance (student_roll_no, subject_id, teacher_id, date, status)
            VALUES (%s, %s, %s, CURDATE(), %s)
            ON DUPLICATE KEY UPDATE status = %s
        """, (roll_no, subject_id, teacher_id, status, status))
        conn.commit()
        flash("Manual Attendance Marked!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for('teacher_attendance'))

# ---- Student Routes (Kept mostly same, fixed imports/formatting) ----

@app.route("/student/dashboard")
def student_dashboard():
    if session.get('role') != 'student': return redirect(url_for('login'))
    student_roll = session.get('user_id')
    
    conn = get_connection()
    if not conn: return redirect(url_for("login"))
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT a.date AS date, COALESCE(s.name,'Unknown') AS subject, a.status AS status 
            FROM attendance a 
            LEFT JOIN subjects s ON a.subject_id = s.id 
            WHERE a.student_roll_no = %s ORDER BY a.date DESC LIMIT 20
        """, (student_roll,))
        rows = cursor.fetchall()
    finally:
        cursor.close(); conn.close()

    return render_template("dashboard_student.html", student_roll=student_roll, student_name=session.get('user_name'), attendance=rows)

@app.route("/session/<token>", methods=["GET"])
def session_link(token):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance_sessions WHERE token=%s AND is_active=1", (token,))
    sess = cursor.fetchone()
    conn.close()
    
    if not sess: 
        flash("Invalid Link", "danger")
        return redirect(url_for('login'))
    if sess['expires_at'] < datetime.now(): 
        flash("Link Expired", "warning")
        return redirect(url_for('login'))
    
    return render_template("session_page.html", sess=sess)

@app.route("/session/<token>/mark", methods=["POST"])
def session_mark(token):
    roll_no = request.form.get('roll_no','').strip()
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')
    ip = request.remote_addr

    if not roll_no or not lat or not lon:
        return jsonify(success=False, msg="Missing roll or location"), 400

    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance_sessions WHERE token=%s AND is_active=1", (token,))
    sess = cursor.fetchone()
    
    if not sess or sess['expires_at'] < datetime.now():
        cursor.close(); conn.close()
        return jsonify(success=False, msg="Invalid or Expired Session"), 400

    cursor.execute("SELECT roll_no FROM students WHERE roll_no=%s", (roll_no,))
    if not cursor.fetchone():
        cursor.close(); conn.close()
        return jsonify(success=False, msg="Student Not Found"), 404

    # Distance Check Logic (Allows 0.0 lat/long for manual generation)
    sess_lat = float(sess['latitude'])
    sess_lon = float(sess['longitude'])
    
    if sess_lat != 0.0 and sess_lon != 0.0:
        dist = haversine_distance_m(sess_lat, sess_lon, float(lat), float(lon))
        if dist > sess['max_radius_m']:
            cursor.close(); conn.close()
            return jsonify(success=False, msg=f"Too far! Distance: {int(dist)}m"), 403

    try:
        cursor.execute("INSERT INTO session_attendance(session_id, student_roll_no, ip_addr, latitude, longitude, status) VALUES(%s,%s,%s,%s,%s,'Present')", 
                       (sess['id'], roll_no, ip, float(lat), float(lon)))
        
        # Sync to main attendance
        today = date.today()
        cursor.execute("INSERT IGNORE INTO attendance(student_roll_no, subject_id, teacher_id, date, status) VALUES(%s,%s,%s,%s,'Present')", 
                       (roll_no, sess['subject_id'], sess['teacher_id'], today))
        conn.commit()
        return jsonify(success=True, msg="Attendance Marked!"), 200
    except Exception:
        conn.rollback()
        return jsonify(success=False, msg="Already Marked"), 409
    finally:
        conn.close()

# ---- Admin & Subjects (Remaining Routes) ----

@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id,name,email,status FROM teachers WHERE status='Pending'")
    pending = cursor.fetchall()
    conn.close()
    return render_template("dashboard_admin.html", pending=pending)

@app.route("/admin_approve")
def admin_approve_page():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id,name,email,status FROM teachers WHERE status='Pending'")
    pending = cursor.fetchall()
    conn.close()
    return render_template("admin_approve.html", pending=pending)

@app.route("/admin/approve/<int:teacher_id>", methods=["POST"])
def admin_approve(teacher_id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    action = request.form.get('action')
    new_status = 'Approved' if action == 'approve' else 'Rejected'
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE teachers SET status=%s WHERE id=%s", (new_status, teacher_id))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_approve_page'))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT",5000))
    )
