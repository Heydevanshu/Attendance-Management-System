import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from datetime import datetime, timedelta, date
import secrets
import math

app = Flask(__name__)
app.secret_key = "SuperSecretKey123"  

# ----------------- DATABASE CONNECTION -----------------
db_config = {
    'host': 'localhost',
    'user': 'root',          
    'password': 'password',  
    'database': 'attendance_db' 
}

def get_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None

# ----------------- HELPER FUNCTIONS -----------------
def haversine_distance_m(lat1, lon1, lat2, lon2):
    # Earth radius in meters
    R = 6371000
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def get_teacher_data(teacher_id):
    """Helper to fetch common data for dashboard & attendance pages"""
    conn = get_connection()
    if not conn: return None, None, None
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Stats
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN sa.status = 'Present' THEN 1 END) as present_count,
                COUNT(CASE WHEN sa.status = 'Absent' THEN 1 END) as absent_count
            FROM session_attendance sa
            JOIN attendance_sessions ads ON sa.session_id = ads.id
            WHERE ads.teacher_id = %s AND DATE(sa.marked_at) = CURDATE()
        """, (teacher_id,))
        stats = cursor.fetchone()
        if not stats: stats = {'present_count': 0, 'absent_count': 0}

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
            flash("Database Error", "danger")
            return render_template("login.html")
            
        cursor = conn.cursor(dictionary=True)
        try:
            if role == "teacher":
                cursor.execute("SELECT * FROM teachers WHERE (id=%s OR email=%s) AND password=%s", (identifier, identifier, password))
                user = cursor.fetchone()
                if user:
                    if user['status'] != 'Approved':
                        flash("Account pending approval", "warning")
                    else:
                        session['role'] = 'teacher'
                        session['user_id'] = user['id']
                        session['user_name'] = user['name']
                        return redirect(url_for("teacher_dashboard"))
                else:
                    flash("Invalid Credentials", "danger")

            elif role == "student":
                cursor.execute("SELECT * FROM students WHERE roll_no=%s AND password=%s", (identifier, password))
                user = cursor.fetchone()
                if user:
                    session['role'] = 'student'
                    session['user_id'] = user['roll_no']
                    session['user_name'] = user['name']
                    return redirect(url_for("student_dashboard"))
                else:
                    flash("Invalid Credentials", "danger")
            
            elif role == "admin":
                if identifier == "admin" and password == "admin123":
                    session['role'] = 'admin'
                    session['user_name'] = 'Admin'
                    return redirect(url_for("admin_dashboard"))
                else:
                    flash("Invalid Admin Credentials", "danger")

        finally:
            cursor.close()
            conn.close()

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ----------------- TEACHER ROUTES (SINGLE PAGE LOGIC) -----------------

@app.route("/teacher/dashboard")
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    teacher_id = session['user_id']
    stats, sessions, subjects = get_teacher_data(teacher_id)
    
    return render_template("dashboard_teacher.html", 
                           page="dashboard", # Logic for SPA
                           teacher_name=session['user_name'],
                           teacher_id=teacher_id,
                           stats=stats, sessions=sessions, subjects=subjects)

@app.route("/teacher/attendance")
def teacher_attendance():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    teacher_id = session['user_id']
    stats, sessions, subjects = get_teacher_data(teacher_id)
    
    return render_template("dashboard_teacher.html", 
                           page="attendance", # Logic for SPA
                           teacher_name=session['user_name'],
                           teacher_id=teacher_id,
                           stats=stats, sessions=sessions, subjects=subjects)

# ----------------- SESSION GENERATION -----------------

@app.route("/teacher/generate_session_no_js", methods=["POST"])
def generate_session_no_js():
    if session.get('role') != 'teacher': return redirect(url_for('login'))

    teacher_id = session['user_id']
    subject_id = request.form.get('subject_id')
    year = request.form.get('year')
    semester = request.form.get('semester')
    duration = int(request.form.get('duration', 10))
    radius = int(request.form.get('radius', 50))
    
    lat = 0.0
    lon = 0.0
    
    token = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(minutes=duration)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # DB schema ke hisaab se columns insert
        query = """
            INSERT INTO attendance_sessions 
            (teacher_id, subject_id, token, latitude, longitude, expires_at, max_radius_m, is_active, year, semester, duration_mins) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
        """
        cursor.execute(query, (teacher_id, subject_id, token, lat, lon, expires_at, radius, year, semester, duration))
        conn.commit()
        flash("Session Created Successfully!", "success")
    except Exception as e:
        print(e)
        flash("Error creating session", "danger")
    finally:
        cursor.close()
        conn.close()
    
    return redirect(url_for('teacher_attendance'))

# ----------------- MANUAL MARKING -----------------

@app.route("/teacher/manual_mark")
def manual_marking_page():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    # Subjects fetch and for dropdown
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM subjects WHERE teacher_id=%s", (session['user_id'],))
    subjects = cursor.fetchall()
    conn.close()
    
    return render_template("manual_mark.html", subjects=subjects)

@app.route("/teacher/mark_manual_submit", methods=["POST"])
def mark_manual_submit():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    roll_no = request.form.get('student_roll')
    status = request.form.get('status')
    subject_id = request.form.get('subject_id')
    teacher_id = session['user_id']
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Check if student exists
        cursor.execute("SELECT roll_no FROM students WHERE roll_no=%s", (roll_no,))
        if not cursor.fetchone():
            flash(f"Roll No {roll_no} not found", "danger")
            return redirect(url_for('manual_marking_page'))
            
        # Insert Attendance
        query = """
            INSERT INTO attendance (student_roll_no, subject_id, teacher_id, date, status)
            VALUES (%s, %s, %s, CURDATE(), %s)
            ON DUPLICATE KEY UPDATE status = %s
        """
        cursor.execute(query, (roll_no, subject_id, teacher_id, status, status))
        conn.commit()
        flash("Attendance Marked Manually", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
        
    return redirect(url_for('teacher_attendance'))

# ----------------- STUDENT LINK ACCESS -----------------

@app.route("/session/<token>")
def session_link(token):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance_sessions WHERE token=%s AND is_active=1", (token,))
    sess = cursor.fetchone()
    conn.close()
    
    if not sess: return "Invalid Link", 404
    if sess['expires_at'] < datetime.now(): return "Link Expired", 403
    
    return render_template("session_page.html", sess=sess)

@app.route("/session/<token>/mark", methods=["POST"])
def session_mark(token):
    roll_no = request.form.get('roll_no')
    lat = float(request.form.get('latitude'))
    lon = float(request.form.get('longitude'))
    ip = request.remote_addr
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Validate Session
    cursor.execute("SELECT * FROM attendance_sessions WHERE token=%s AND is_active=1", (token,))
    sess = cursor.fetchone()
    if not sess or sess['expires_at'] < datetime.now():
        conn.close()
        return jsonify(success=False, msg="Session Invalid or Expired")
        
    # 2. Validate Student
    cursor.execute("SELECT roll_no FROM students WHERE roll_no=%s", (roll_no,))
    if not cursor.fetchone():
        conn.close()
        return jsonify(success=False, msg="Student Not Found")
        
    # 3. Distance Check (Skip if session lat/lon is 0.0)
    sess_lat = float(sess['latitude'])
    sess_lon = float(sess['longitude'])
    
    if sess_lat != 0.0 and sess_lon != 0.0:
        dist = haversine_distance_m(sess_lat, sess_lon, lat, lon)
        if dist > sess['max_radius_m']:
            conn.close()
            return jsonify(success=False, msg=f"Too far! Distance: {int(dist)}m")
            
    # 4. Mark Attendance
    try:
        cursor.execute("""
            INSERT INTO session_attendance (session_id, student_roll_no, ip_addr, latitude, longitude, status)
            VALUES (%s, %s, %s, %s, %s, 'Present')
        """, (sess['id'], roll_no, ip, lat, lon))
        
        # Sync with main attendance
        cursor.execute("""
            INSERT IGNORE INTO attendance (student_roll_no, subject_id, teacher_id, date, status)
            VALUES (%s, %s, %s, CURDATE(), 'Present')
        """, (roll_no, sess['subject_id'], sess['teacher_id']))
        
        conn.commit()
        return jsonify(success=True, msg="Attendance Marked!")
    except Exception as e:
        return jsonify(success=False, msg="Already Marked")
    finally:
        conn.close()

# ----------------- ADMIN & STUDENT DASHBOARDS -----------------
# (Basic implementation to prevent errors)

@app.route("/student/dashboard")
def student_dashboard():
    if session.get('role') != 'student': return redirect(url_for('login'))
    return render_template("dashboard_student.html", student_name=session['user_name'])

@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    return render_template("dashboard_admin.html")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
