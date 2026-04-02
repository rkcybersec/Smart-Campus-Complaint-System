import os
import sqlite3
import datetime
import smtplib
from email.mime.text import MIMEText

from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_key_123'


# ---------------- EMAIL ---------------- #
def send_email(to_email, subject, message):
    print("Sending email to:", to_email)

    sender_email = "smartcampuscomplaint.system@gmail.com"
    sender_password = "xyrorxzhltimcmkr"

    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print("Email sent")
    except Exception as e:
        print("Email error:", e)


# ---------------- DB ---------------- #
def get_db():
    return sqlite3.connect('database.db')


# ---------------- HOME ---------------- #
@app.route('/')
def home():
    return render_template('index.html')


# ---------------- REGISTER ---------------- #
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        hashed_password = generate_password_hash(password)

        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, password, role, email) VALUES (?, ?, ?, ?)",
            (username, hashed_password, 'student', email)
        )
        conn.commit()
        conn.close()

        return redirect('/login')

    return render_template('register.html')


# ---------------- LOGIN ---------------- #
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user'] = username
            session['role'] = user[3]
            return redirect('/dashboard')
        else:
            return "Invalid username or password"

    return render_template('login.html')


# ---------------- LOGOUT ---------------- #
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------------- DASHBOARD ---------------- #
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0]
    resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]

    conn.close()

    return render_template(
        'dashboard.html',
        total=total,
        pending=pending,
        resolved=resolved,
        role=session['role']
    )


# ---------------- COMPLAINT ---------------- #
@app.route('/complaint', methods=['GET', 'POST'])
def complaint():
    if 'user' not in session:
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        desc = request.form['description']
        category = request.form['category']
        priority = request.form['priority']
        username = session['user']
        status = "Pending"
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        image = request.files['image']
        filename = ""

        if image and image.filename != "":
            filename = secure_filename(image.filename)

            upload_folder = os.path.join(os.getcwd(), 'static', 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            image.save(os.path.join(upload_folder, filename))

        conn = get_db()

        conn.execute("""
            INSERT INTO complaints
            (title, description, category, status, username, created_at, priority, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, desc, category, status, username, created_at, priority, filename))

        conn.commit()

        user_email = conn.execute(
            "SELECT email FROM users WHERE username=?",
            (username,)
        ).fetchone()[0]

        send_email(
            user_email,
            "Complaint Submitted",
            f"Your complaint '{title}' has been submitted successfully."
        )

        conn.close()

        return redirect('/track')

    return render_template('complaint.html')


# ---------------- TRACK ---------------- #
@app.route('/track')
def track():
    if 'user' not in session:
        return redirect('/login')

    conn = get_db()

    if session['role'] == 'admin':
        complaints = conn.execute("SELECT * FROM complaints").fetchall()
    else:
        complaints = conn.execute(
            "SELECT * FROM complaints WHERE username=?",
            (session['user'],)
        ).fetchall()

    conn.close()

    return render_template('track.html', complaints=complaints)


# ---------------- INCHARGE ---------------- #
@app.route('/incharge')
def incharge():
    if 'user' not in session or session.get('role') != 'incharge':
        return "Access Denied ❌"

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute("SELECT * FROM complaints WHERE status='Pending'")
    complaints = cur.fetchall()

    conn.close()

    return render_template('incharge.html', complaints=complaints)

#-----------------NEW ROUTE TO FORWORS TO ADMIN----------#
@app.route('/forward/<int:id>', methods=['POST'])
def forward(id):
    if 'user' not in session or session.get('role') != 'incharge':
        return "Access Denied ❌"

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # 🔥 Update status
    cur.execute("UPDATE complaints SET status='Forwarded' WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect('/incharge')

#------------------REVIEW BY INHCARGE---------#
@app.route('/review/<int:id>', methods=['POST'])
def review(id):
    if 'user' not in session or session.get('role') != 'incharge':
        return "Access Denied ❌"

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # 🔥 Update status to Reviewed
    cur.execute("UPDATE complaints SET status='Reviewed' WHERE id=?", (id,))

    conn.commit()
    conn.close()

    return redirect('/incharge')
# ---------------- ADMIN ---------------- #
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    # 🔒 ACCESS CONTROL
    if 'role' not in session or session['role'] != 'admin':
        return "Access Denied"

    conn = get_db()

    # 🔥 HANDLE STATUS UPDATE
    if request.method == 'POST':
        cid = request.form['id']
        status = request.form['status']

        print("Updating:", cid, status)  # 🔥 debug

        # 🔍 GET USERNAME
        user = conn.execute(
            "SELECT username FROM complaints WHERE id=?",
            (cid,)
        ).fetchone()[0]

        # 🔍 GET EMAIL
        email = conn.execute(
            "SELECT email FROM users WHERE username=?",
            (user,)
        ).fetchone()[0]

        # 🔥 UPDATE STATUS + UPDATED_BY
        conn.execute(
            "UPDATE complaints SET status=?, updated_by=? WHERE id=?",
            (status, "Admin", cid)
        )
        conn.commit()

        # 🔥 SEND EMAIL
        send_email(
            email,
            "Complaint Update",
            f"Your complaint ID {cid} is now '{status}'"
        )

    # 🔥 ANALYTICS
    total = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0]
    resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]
    high = conn.execute("SELECT COUNT(*) FROM complaints WHERE priority='High'").fetchone()[0]

    wifi = conn.execute("SELECT COUNT(*) FROM complaints WHERE category='WiFi'").fetchone()[0]
    hostel = conn.execute("SELECT COUNT(*) FROM complaints WHERE category='Hostel'").fetchone()[0]
    classroom = conn.execute("SELECT COUNT(*) FROM complaints WHERE category='Classroom'").fetchone()[0]
    electrical = conn.execute("SELECT COUNT(*) FROM complaints WHERE category='Electrical'").fetchone()[0]
    physical_education = conn.execute("SELECT COUNT(*) FROM complaints WHERE category='Physical Education'").fetchone()[0]
    student_cell = conn.execute("SELECT COUNT(*) FROM complaints WHERE category='Student Cell'").fetchone()[0]

    # 🔥 ONLY FORWARDED COMPLAINTS
    complaints = conn.execute(
        "SELECT * FROM complaints WHERE status='Forwarded'"
    ).fetchall()

    conn.close()

    return render_template(
        'admin.html',
        complaints=complaints,
        total=total,
        pending=pending,
        resolved=resolved,
        high=high,
        wifi=wifi,
        hostel=hostel,
        classroom=classroom,
        electrical=electrical,
        physical_education=physical_education,
        student_cell=student_cell
    )

# ---------------- DB SETUP ---------------- #
if __name__ == '__main__':
    conn = sqlite3.connect('database.db')

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT,
        role TEXT,
        email TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS complaints(
        id INTEGER PRIMARY KEY,
        title TEXT,
        description TEXT,
        category TEXT,
        status TEXT,
        username TEXT,
        created_at TEXT,
        priority TEXT,
        image TEXT
    )
    """)

    conn.commit()
    conn.close()

    app.run(debug=True)