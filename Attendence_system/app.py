import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from datetime import datetime, timedelta, date
import secrets
import math

app = Flask(__name__)
app.secret_key = "HelloWorld"  

# --- DATABASE CONFIGURATION ---
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'password',  # <--- APNA PASSWORD YAHAN LIKHEIN
    'database': 'attendance_db'
}

def get_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        return None

# --- HELPER FUNCTIONS ---
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

# --- AUTH ROUTES (LOGIN & SIGNUP) ---

@app.route("/", methods=["GET"])
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role")
        email = request.form.get("email_or_id")
        password = request.form.get("password")

        conn = get_connection()
        if not conn:
            flash("Database Connection Error", "danger")
            return render_template("login.html")

        cursor = conn.cursor(dictionary=True)
        try:
            if role == 'teacher':
                cursor.execute("SELECT * FROM teachers WHERE email=%s AND password=%s", (email, password))
                user = cursor.fetchone()
                if user:
                    session['role'] = 'teacher'
                    session['user_id'] = user['id']
                    session['user_name'] = user['name']
                    return redirect(url_for("teacher_dashboard"))
                else:
                    flash("Invalid Email or Password", "danger")
            
            elif role == 'student':
                cursor.execute("SELECT * FROM students WHERE roll_no=%s AND password=%s", (email, password)) # email field acts as roll_no here based on form
                user = cursor.fetchone()
                if user:
                    session['role'] = 'student'
                    session['user_id'] = user['roll_no']
                    session['user_name'] = user['name']
                    return redirect(url_for("student_dashboard"))
                else:
                    flash("Invalid Roll No or Password", "danger")

        finally:
            cursor.close()
            conn.close()
            
    return render_template("login.html")

# --- YE RAHA MISSING SIGNUP ROUTE ---
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        role = request.form.get("role")
        name = request.form.get("name")
        email = request.form.get("email") # Teachers ke liye Email, Students ke liye Roll No
        password = request.form.get("password")
        
        # Extra fields for student
        branch = request.form.get("branch", "") 
        year = request.form.get("year", "")

        conn = get_connection()
        if not conn:
            flash("Database Connection Error", "danger")
            return render_template("signup.html")

        cursor = conn.cursor()
        try:
            if role == "teacher":
                # Check existing
                cursor.execute("SELECT id FROM teachers WHERE email=%s", (email,))
                if cursor.fetchone():
                    flash("Email already exists!", "danger")
                else:
                    cursor.execute("INSERT INTO teachers (name, email, password, status) VALUES (%s, %s, %s, 'Pending')", 
                                   (name, email, password))
                    conn.commit()
                    flash("Teacher Registered! Wait for approval.", "success")
                    return redirect(url_for("login"))

            elif role == "student":
                # Check existing
                cursor.execute("SELECT roll_no FROM students WHERE roll_no=%s", (email,)) # Form field might say email but acts as identifier
                if cursor.fetchone():
                    flash("Roll Number already exists!", "danger")
                else:
                    cursor.execute("INSERT INTO students (roll_no, name, email, password, branch, year) VALUES (%s, %s, %s, %s, %s, %s)", 
                                   (email, name, email + "@college.com", password, branch, year))
                    conn.commit()
                    flash("Student Registered! Login now.", "success")
                    return redirect(url_for("login"))
                    
        except Exception as e:
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()
            conn.close()

    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- TEACHER ROUTES ---

@app.route("/teacher/dashboard")
def teacher_dashboard():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    teacher_id = session['user_id']
    stats, sessions, subjects = get_teacher_common_data(teacher_id)
    
    return render_template("dashboard_teacher.html", 
                           page="dashboard",
                           teacher_name=session['user_name'],
                           teacher_id=teacher_id,
                           stats=stats, sessions=sessions, subjects=subjects)

@app.route("/teacher/attendance")
def teacher_attendance():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    
    teacher_id = session['user_id']
    stats, sessions, subjects = get_teacher_common_data(teacher_id)
    
    return render_template("dashboard_teacher.html", 
                           page="attendance",
                           teacher_name=session['user_name'],
                           teacher_id=teacher_id,
                           stats=stats, sessions=sessions, subjects=subjects)

@app.route("/teacher/generate_session_no_js", methods=["POST"])
def generate_session_no_js():
    if session.get('role') != 'teacher': return redirect(url_for('login'))

    teacher_id = session['user_id']
    subject_id = request.form.get('subject_id')
    year = request.form.get('year')
    semester = request.form.get('semester')
    duration = int(request.form.get('duration', 10))
    radius = int(request.form.get('radius', 50))
    
    token = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(minutes=duration)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO attendance_sessions 
            (teacher_id, subject_id, token, latitude, longitude, expires_at, max_radius_m, is_active, year, semester, duration_mins) 
            VALUES (%s, %s, %s, 0.0, 0.0, %s, %s, 1, %s, %s, %s)
        """, (teacher_id, subject_id, token, expires_at, radius, year, semester, duration))
        conn.commit()
        flash("Session Link Generated Successfully!", "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for('teacher_attendance'))

@app.route("/teacher/manual_mark_page")
def manual_mark_page():
    if session.get('role') != 'teacher': return redirect(url_for('login'))
    _, _, subjects = get_teacher_common_data(session['user_id'])
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

# --- STUDENT DASHBOARD ---
@app.route("/student/dashboard")
def student_dashboard():
    if session.get('role') != 'student': return redirect(url_for('login'))
    return render_template("dashboard_student.html") # Create this file if missing

if __name__ == "__main__":
    app.run(debug=True, port=5000)
