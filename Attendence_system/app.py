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
    """
    Calculates the great-circle distance between two points on Earth 
    using their latitude and longitude in meters.
    """
    R = 6371000 # Earth radius in meters
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# ---- Home / Login ----

@app.route("/", methods=["GET"])
def home():
    """Redirects the root URL to the login page."""
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Handles user authentication for Teachers, Students, and Admins.
    Verifies credentials against the database and sets up session data.
    """
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
                cursor.execute(
                    "SELECT * FROM teachers WHERE (id=%s OR email=%s) AND password=%s",
                    (identifier, identifier, password)
                )
                user = cursor.fetchone()
                if not user:
                    flash("Invalid teacher credentials", "danger")
                    return redirect(url_for("login"))
                if user.get('status') != 'Approved':
                    flash(f"Your account status: {user.get('status')}. Wait for admin approval.", "warning")
                    return redirect(url_for("login"))

                session['role'] = 'teacher'
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                return redirect(url_for("teacher_dashboard"))

            elif role == "student":
                cursor.execute(
                    "SELECT * FROM students WHERE roll_no=%s AND password=%s",
                    (identifier, password)
                )
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

            else:
                flash("Please select a valid role", "warning")
                return redirect(url_for("login"))

        except Exception as e:
            flash(f"Login error: {e}", "danger")
            return redirect(url_for("login"))
        finally:
            cursor.close()
            conn.close()

    return render_template("login.html")


# ---- Signup ----

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """
    Handles registration for new Teachers and Students.
    Teachers are registered with 'Pending' status for Admin approval.
    """
    if request.method == "POST":
        role = request.form.get("role")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        extra = request.form.get("extra", "").strip() if request.form.get("extra") else None
        roll_no_form = request.form.get("roll_no", "").strip()
        year = request.form.get("year", "").strip()
        if "Year" in year:
            year = year.split()[0] 

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
                    return redirect(url_for("signup"))

                cursor.execute(
                    "INSERT INTO teachers(name,email,password,status) VALUES(%s,%s,%s,'Pending')",
                    (name, email, password)
                )
                conn.commit()
                flash("Teacher registered. Please wait for admin approval.", "success")
                return redirect(url_for("login"))

            elif role == "student":
                roll_no = roll_no_form or email
                branch = extra
                cursor.execute("SELECT roll_no, email FROM students WHERE roll_no=%s OR email=%s", (roll_no, email))
                if cursor.fetchone():
                    flash("Student already exists", "danger")
                    return redirect(url_for("signup"))

                cursor.execute(
                    "INSERT INTO students(roll_no,name,branch,email,password,year) VALUES(%s,%s,%s,%s,%s,%s)",
                    (roll_no, name, branch, email, password, year)
                )
                conn.commit()
                flash("Student registered. You can now login.", "success")
                return redirect(url_for("login"))

            else:
                flash("Choose a valid role", "warning")
                return redirect(url_for("signup"))

        except Exception as e:
            conn.rollback()
            flash(f"Signup error: {e}", "danger")
            return redirect(url_for("signup"))
        finally:
            cursor.close()
            conn.close()

    return render_template("signup.html")


# ---- Teacher Dashboard ----

@app.route("/teacher/dashboard")
def teacher_dashboard():
    """
    Renders the teacher's landing page.
    Displays attendance stats, recent sessions, and assigned subjects.
    """
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))

    teacher_id = session.get('user_id')
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Fetch stats for dashboard cards
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN sa.status = 'Present' THEN 1 END) as present_count,
                COUNT(CASE WHEN sa.status = 'Absent' THEN 1 END) as absent_count
            FROM session_attendance sa
            JOIN attendance_sessions ads ON sa.session_id = ads.id
            WHERE ads.teacher_id = %s
        """, (teacher_id,))
        stats = cursor.fetchone() or {'present_count': 0, 'absent_count': 0}

        # Fetch 10 most recent sessions
        cursor.execute("""
            SELECT s.*, sub.name as subject_name 
            FROM attendance_sessions s
            JOIN subjects sub ON s.subject_id = sub.id
            WHERE s.teacher_id = %s 
            ORDER BY s.created_at DESC LIMIT 10
        """, (teacher_id,))
        sessions = cursor.fetchall()

        # Fetch subjects assigned to teacher
        cursor.execute("SELECT id, name FROM subjects WHERE teacher_id = %s", (teacher_id,))
        teacher_subjects = cursor.fetchall()

    except Exception as e:
        flash(f"Error loading dashboard: {e}", "danger")
        stats = {'present_count': 0, 'absent_count': 0}
        sessions = []
        teacher_subjects = []
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "dashboard_teacher.html",
        teacher_id=teacher_id,
        teacher_name=session.get('user_name', 'Teacher'),
        sessions=sessions,
        subjects=teacher_subjects,
        stats=stats
    )

@app.route("/generate_session_api", methods=["POST"])
def generate_session_api():
    """
    Endpoint to create a new attendance session via AJAX.
    Generates a unique token and calculates expiry time.
    """
    if session.get('role') != 'teacher':
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    teacher_id = session.get('user_id')
    
    subject_id = data.get('subject_id')
    duration = int(data.get('duration', 10))
    radius = int(data.get('radius', 50))
    lat = data.get('lat')
    lng = data.get('lng')
    
    token = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(minutes=duration)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        query = """
            INSERT INTO attendance_sessions 
            (teacher_id, subject_id, token, latitude, longitude, expires_at, max_radius_m, is_active) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
        """
        cursor.execute(query, (teacher_id, subject_id, token, lat, lng, expires_at, radius))
        conn.commit()
        
        session_link = url_for('session_link', token=token, _external=True)
        return jsonify({"success": True, "link": session_link})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@app.route("/teacher/attendance")
def teacher_attendance():
    """Displays the attendance management page for teachers."""
    if session.get('role') != 'teacher':
        return redirect(url_for('login'))

    teacher_id = session.get('user_id')
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id, name FROM subjects WHERE teacher_id = %s", (teacher_id,))
        subjects = cursor.fetchall()

        cursor.execute("""
            SELECT s.*, sub.name as subject_name 
            FROM attendance_sessions s 
            JOIN subjects sub ON s.subject_id = sub.id 
            WHERE s.teacher_id = %s ORDER BY s.created_at DESC LIMIT 5
        """, (teacher_id,))
        sessions = cursor.fetchall()
        
    finally:
        cursor.close()
        conn.close()

    return render_template("attendance.html", subjects=subjects, sessions=sessions)


# ---- Student Dashboard ----

@app.route("/student/dashboard")
def student_dashboard():
    """
    Renders the student dashboard.
    Fetches and displays the 20 most recent attendance records for the student.
    """
    if session.get('role') != 'student':
        flash("Please login as student", "warning")
        return redirect(url_for('login'))

    student_roll = session.get('user_id')
    if not student_roll:
        flash("Student id missing in session. Please login again.", "danger")
        return redirect(url_for('login'))

    conn = get_connection()
    if not conn:
        flash("Database connection failed", "danger")
        return redirect(url_for("login"))

    cursor = conn.cursor(dictionary=True)
    try:
        # Try fetching from regular attendance table first
        cursor.execute(
            "SELECT a.date AS date, COALESCE(s.name,'Unknown') AS subject, a.status AS status "
            "FROM attendance a "
            "LEFT JOIN subjects s ON a.subject_id = s.id "
            "WHERE a.student_roll_no = %s "
            "ORDER BY a.date DESC LIMIT 20",
            (student_roll,)
        )
        rows = cursor.fetchall()

        # If empty, try fetching from session-based attendance
        if not rows:
            cursor.execute(
                "SELECT sa.marked_at AS date, COALESCE(sub.name,'Unknown') AS subject, sa.status AS status "
                "FROM session_attendance sa "
                "LEFT JOIN attendance_sessions sess ON sa.session_id = sess.id "
                "LEFT JOIN subjects sub ON sess.subject_id = sub.id "
                "WHERE sa.student_roll_no = %s "
                "ORDER BY sa.marked_at DESC LIMIT 20",
                (student_roll,)
            )
            rows = cursor.fetchall()

        if not rows:
            flash("No recent attendance records found.", "info")

    except Exception as e:
        flash(f"Error loading attendance: {e}", "danger")
        rows = []
    finally:
        cursor.close()
        conn.close()

    return render_template("dashboard_student.html",
                           student_roll=student_roll,
                           student_name=session.get('user_name'),
                           attendance=rows)


@app.route("/student/subjects")
def view_subjects_student():
    """Lists all subjects available to a student based on their branch."""
    if session.get('role') != 'student':
        flash("Please login as student", "warning")
        return redirect(url_for('login'))

    student_roll = session.get('user_id')
    conn = get_connection()
    if not conn:
        flash("Database connection failed", "danger")
        return redirect(url_for('student_dashboard'))

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT branch FROM students WHERE roll_no=%s", (student_roll,))
        s = cursor.fetchone()
        branch = s['branch'] if s else None

        if branch:
            cursor.execute("SELECT id, name, branch, teacher_id FROM subjects WHERE branch=%s", (branch,))
            subjects = cursor.fetchall()
        else:
            cursor.execute("SELECT id, name, branch, teacher_id FROM subjects")
            subjects = cursor.fetchall()

    except Exception as e:
        flash(f"Error loading subjects: {e}", "danger")
        subjects = []
    finally:
        cursor.close()
        conn.close()

    return render_template("view_subjects_student.html", subjects=subjects, student_roll=student_roll)


@app.route("/student/attendance/subject/<int:subject_id>")
def student_subject_attendance(subject_id):
    """Shows detailed attendance history for a specific subject for the student."""
    if session.get('role') != 'student':
        flash("Please login as student", "warning")
        return redirect(url_for('login'))

    student_roll = session.get('user_id')
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch manual attendance entries
        cursor.execute(
            "SELECT date AS datetime, status, 'regular' AS kind FROM attendance "
            "WHERE student_roll_no=%s AND subject_id=%s",
            (student_roll, subject_id)
        )
        regular = cursor.fetchall()

        # Fetch session-based attendance entries
        cursor.execute(
            "SELECT sa.marked_at AS datetime, sa.status, 'session' AS kind, sa.latitude, sa.longitude "
            "FROM session_attendance sa "
            "JOIN attendance_sessions sess ON sa.session_id = sess.id "
            "WHERE sa.student_roll_no=%s AND sess.subject_id=%s",
            (student_roll, subject_id)
        )
        session_entries = cursor.fetchall()

        cursor.execute("SELECT name FROM subjects WHERE id=%s", (subject_id,))
        s = cursor.fetchone()
        subject_name = s['name'] if s else "Unknown Subject"

        combined = []
        for r in regular:
            combined.append({"datetime": r['datetime'], "status": r['status'], "kind": r['kind'], "lat": None, "lon": None})
        for r in session_entries:
            combined.append({"datetime": r['datetime'], "status": r['status'], "kind": r['kind'], "lat": r.get('latitude'), "lon": r.get('longitude')})

        combined.sort(key=lambda x: x['datetime'] or datetime.min, reverse=True)

    except Exception as e:
        flash(f"Error loading subject attendance: {e}", "danger")
        combined = []
        subject_name = "Unknown Subject"
    finally:
        cursor.close()
        conn.close()

    return render_template("student_subject_attendance.html",
                           subject_id=subject_id,
                           subject_name=subject_name,
                           attendance=combined,
                           student_roll=student_roll)


# ---- Admin Dashboard ----

@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():
    """Displays the admin panel with a list of teachers pending approval."""
    if session.get('role') != 'admin':
        flash("Please login as admin", "warning")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id,name,email,status FROM teachers WHERE status='Pending'")
        pending = cursor.fetchall()
    except Exception as e:
        flash(f"Error loading pending teachers: {e}", "danger")
        pending = []
    finally:
        cursor.close()
        conn.close()

    return render_template("dashboard_admin.html", pending=pending)


@app.route("/admin_approve", methods=["GET"])
def admin_approve_page():
    """Separate page for Admin to review and approve/reject teacher requests."""
    if session.get('role') != 'admin':
        flash("Please login as admin", "warning")
        return redirect(url_for("login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id,name,email,status FROM teachers WHERE status='Pending'")
        pending = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template("admin_approve.html", pending=pending)


@app.route("/admin/approve/<int:teacher_id>", methods=["POST"])
def admin_approve(teacher_id):
    """Updates a teacher's status to 'Approved' or 'Rejected'."""
    if session.get('role') != 'admin':
        flash("Please login as admin", "warning")
        return redirect(url_for("login"))

    action = request.form.get('action')
    new_status = 'Approved' if action == 'approve' else 'Rejected'

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE teachers SET status=%s WHERE id=%s", (new_status, teacher_id))
        conn.commit()
        flash(f"Teacher {teacher_id} set to {new_status}", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating status: {e}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('admin_approve_page'))


# ---- Teacher Attendance Management ----

@app.route("/teacher/mark", methods=["GET", "POST"])
def teacher_mark():
    """Allows teachers to manually mark attendance for a student."""
    if session.get('role') != 'teacher':
        flash("Please login as teacher", "warning")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == "POST":
            student_roll = request.form.get('student_roll')
            subject_id = request.form.get('subject_id')
            status = request.form.get('status')
            today = date.today()

            cursor.execute(
                "SELECT id FROM attendance WHERE student_roll_no=%s AND subject_id=%s AND date=%s",
                (student_roll, subject_id, today)
            )
            if cursor.fetchone():
                flash("Attendance already marked for today", "warning")
            else:
                cursor.execute(
                    "INSERT INTO attendance(student_roll_no,subject_id,teacher_id,date,status) VALUES(%s,%s,%s,%s,%s)",
                    (student_roll, subject_id, session.get('user_id'), today, status)
                )
                conn.commit()
                flash("Attendance marked", "success")

        cursor.execute("SELECT id,name FROM subjects WHERE teacher_id=%s", (session.get('user_id'),))
        subjects = cursor.fetchall()
    except Exception as e:
        flash(f"Error in mark attendance: {e}", "danger")
        subjects = []
    finally:
        cursor.close()
        conn.close()

    return render_template("mark_attendance.html", subjects=subjects)


@app.route("/teacher/<int:teacher_id>/subjects")
def view_subjects_teacher(teacher_id):
    """Lists all subjects handled by a specific teacher."""
    if session.get('role') not in ('teacher', 'admin'):
        flash("Please login", "warning")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id,name,branch FROM subjects WHERE teacher_id=%s", (teacher_id,))
        subs = cursor.fetchall()
    except Exception as e:
        flash(f"Error loading subjects: {e}", "danger")
        subs = []
    finally:
        cursor.close()
        conn.close()

    return render_template("view_subjects_teacher.html", subjects=subs, teacher_id=teacher_id)


@app.route("/teacher/session/create", methods=["GET", "POST"])
def create_session():
    """Renders the session creation form and handles session data storage."""
    if session.get('role') != 'teacher':
        flash("Please login as teacher", "warning")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if request.method == "POST":
            subject_id = request.form.get('subject_id')
            lat = request.form.get('latitude')
            lon = request.form.get('longitude')
            duration = int(request.form.get('duration', 10))
            radius = int(request.form.get('radius', 20))
            note = request.form.get('note','')

            if not subject_id or not lat or not lon:
                flash("Subject and location required", "danger")
                return redirect(url_for('create_session'))

            token = secrets.token_urlsafe(16)
            expires_at = datetime.utcnow() + timedelta(minutes=duration)

            cursor.execute(
                "INSERT INTO attendance_sessions(teacher_id,subject_id,token,latitude,longitude,expires_at,max_radius_m,session_note) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (session['user_id'], subject_id, token, float(lat), float(lon), expires_at, radius, note)
            )
            conn.commit()
            link = url_for('session_link', token=token, _external=True)
            flash(f"Session created. Share this link: {link}", "success")
            return redirect(url_for('teacher_dashboard'))

        cursor.execute("SELECT id, name FROM subjects WHERE teacher_id=%s", (session['user_id'],))
        subjects = cursor.fetchall()
    except Exception as e:
        conn.rollback()
        flash(f"Error creating session: {e}", "danger")
        subjects = []
    finally:
        cursor.close()
        conn.close()

    return render_template("create_session.html", subjects=subjects)


# ---- Attendance Session Access ----

@app.route("/session/<token>", methods=["GET"])
def session_link(token):
    """Displays the attendance submission page for students when they open a session link."""
    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance_sessions WHERE token=%s AND is_active=1", (token,))
    sess = cursor.fetchone()
    cursor.close(); conn.close()
    
    if not sess:
        flash("Invalid or inactive attendance link", "danger")
        return redirect(url_for('login'))

    if sess['expires_at'] < datetime.utcnow():
        flash("This attendance link has expired", "warning")
        return redirect(url_for('login'))

    return render_template("session_page.html", sess=sess)


@app.route("/session/<token>/mark", methods=["POST"])
def session_mark(token):
    """
    Processes student attendance for a session.
    Verifies location (distance) and ensures no duplicate marking.
    """
    roll_no = request.form.get('roll_no','').strip()
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')
    ip = request.remote_addr

    if not roll_no or not lat or not lon:
        return jsonify(success=False, msg="Missing roll or location"), 400

    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance_sessions WHERE token=%s AND is_active=1", (token,))
    sess = cursor.fetchone()
    if not sess:
        cursor.close(); conn.close()
        return jsonify(success=False, msg="Invalid session"), 400

    if sess['expires_at'] < datetime.utcnow():
        cursor.close(); conn.close()
        return jsonify(success=False, msg="Session expired"), 400

    cursor.execute("SELECT roll_no FROM students WHERE roll_no=%s", (roll_no,))
    if not cursor.fetchone():
        cursor.close(); conn.close()
        return jsonify(success=False, msg="Student not found"), 404

    # Perform distance check between student and teacher's set coordinates
    dist = haversine_distance_m(sess['latitude'], sess['longitude'], float(lat), float(lon))
    if dist > sess['max_radius_m']:
        cursor.close(); conn.close()
        return jsonify(success=False, msg=f"Not in range ({int(dist)} m)"), 403

    try:
        cursor.execute(
            "INSERT INTO session_attendance(session_id, student_roll_no, ip_addr, latitude, longitude, status) VALUES(%s,%s,%s,%s,%s,%s)",
            (sess['id'], roll_no, ip, float(lat), float(lon), 'Present')
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        cursor.close(); conn.close()
        return jsonify(success=False, msg="Already marked or DB error"), 409

    # Sync with main daily attendance record
    try:
        today = date.today()
        cursor.execute(
            "INSERT IGNORE INTO attendance(student_roll_no, subject_id, teacher_id, date, status) VALUES(%s,%s,%s,%s,%s)",
            (roll_no, sess['subject_id'], sess['teacher_id'], today, 'Present')
        )
        conn.commit()
    except:
        conn.rollback()

    cursor.close(); conn.close()
    return jsonify(success=True, msg="Attendance marked"), 200


@app.route("/teacher/session/<int:session_id>/view", methods=["GET"])
def teacher_view_session(session_id):
    """Allows a teacher to see the list of students who marked attendance in a specific session."""
    if session.get('role') != 'teacher':
        flash("Login as teacher", "warning")
        return redirect(url_for('login'))

    conn = get_connection(); cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance_sessions WHERE id=%s AND teacher_id=%s", (session_id, session['user_id']))
    sess = cursor.fetchone()
    if not sess:
        cursor.close(); conn.close()
        flash("Session not found", "danger")
        return redirect(url_for('teacher_dashboard'))

    cursor.execute("SELECT sa.*, s.name AS student_name FROM session_attendance sa LEFT JOIN students s ON sa.student_roll_no=s.roll_no WHERE sa.session_id=%s", (session_id,))
    attendees = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template("teacher_view_session.html", sess=sess, attendees=attendees)


# ---- Admin Subject Management ----

@app.route("/admin/add_subject", methods=["GET", "POST"])
def add_subject():
    if session.get('role') != 'admin':
        flash("Please login as admin", "warning")
        return redirect(url_for('login'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form.get("name").strip()
        branch = request.form.get("branch").strip()
        teacher_id = request.form.get("teacher_id")
        # Naye fields extract karein
        year = request.form.get("year")
        semester = request.form.get("semester")

        # Database insert query update 
        try:
            cursor.execute(
                "INSERT INTO subjects(name, branch, teacher_id, year, semester) VALUES(%s, %s, %s, %s, %s)",
                (name, branch, teacher_id, year, semester)
            )
            conn.commit()
            flash("Subject added successfully!", "success")
            return redirect(url_for("admin_dashboard"))
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            cursor.close(); conn.close()
            
    cursor.execute("SELECT id, name FROM teachers WHERE status='Approved'")
    teachers = cursor.fetchall()
    cursor.close(); conn.close()
    return render_template("add_subject.html", teachers=teachers)


# ---- Logout ----

@app.route("/logout")
def logout():
    """Clears user session and redirects to login page."""
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT",5000))
    )


