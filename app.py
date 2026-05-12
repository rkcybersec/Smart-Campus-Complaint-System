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
    try:
        sender_email = "your_email@gmail.com"
        sender_password = "your_app_password"

        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = to_email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Email error:", e)


# ---------------- DB ---------------- #
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- HOME ---------------- #
@app.route('/')
def home():
    return render_template('index.html')


# ---------------- REGISTER ---------------- #
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        email = request.form['email']

        conn = get_db()
        conn.execute(
            "INSERT INTO users (username, password, role, email) VALUES (?, ?, ?, ?)",
            (username, password, 'student', email)
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

        if user and check_password_hash(user['password'], password):
            session['user'] = username
            session['role'] = user['role']

            if user['role'] == 'admin':
                return redirect('/admin')
            elif user['role'] == 'incharge':
                return redirect('/incharge')
            else:
                return redirect('/dashboard')

        return  render_template('login.html', error="Iinvalid username or Password")

    return render_template('login.html')


# ---------------- FORGOT PASSWORD ---------------- #
@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':

        # 🔥 STEP 2 FIRST (VERY IMPORTANT)
        if 'new_password' in request.form:
            username = request.form['username']
            new_password = generate_password_hash(request.form['new_password'])

            conn = get_db()
            conn.execute(
                "UPDATE users SET password=? WHERE username=?",
                (new_password, username)
            )
            conn.commit()
            conn.close()

            return render_template('forgot.html', msg="Password Updated Successfully")

        # 🔥 STEP 1
        if 'username' in request.form:
            username = request.form['username']

            conn = get_db()
            user = conn.execute(
                "SELECT * FROM users WHERE username=?",
                (username,)
            ).fetchone()
            conn.close()

            if user:
                return render_template('forgot.html', username=username)
            else:
                return render_template('forgot.html', msg="User not found")

    return render_template('forgot.html')
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

    return render_template('dashboard.html', total=total, pending=pending, resolved=resolved)


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
            os.makedirs(upload_folder, exist_ok=True)
            image.save(os.path.join(upload_folder, filename))

        conn = get_db()
        conn.execute("""
            INSERT INTO complaints
            (title, description, category, status, username, created_at, priority, image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, desc, category, status, username, created_at, priority, filename))
        conn.commit()
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
    if session.get('role') != 'incharge':
        return "Access Denied ❌"

    conn = get_db()
    complaints = conn.execute(
        "SELECT * FROM complaints WHERE status IN ('Pending','Reviewed')"
    ).fetchall()
    conn.close()

    return render_template('incharge.html', complaints=complaints)


# ---------------- REVIEW ---------------- #
@app.route('/review/<int:id>', methods=['POST'])
def review(id):
    if session.get('role') != 'incharge':
        return "Access Denied ❌"

    conn = get_db()
    conn.execute("UPDATE complaints SET status='Reviewed' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/incharge')


# ---------------- FORWARD ---------------- #
@app.route('/forward/<int:id>', methods=['POST'])
def forward(id):
    if session.get('role') != 'incharge':
        return "Access Denied ❌"

    conn = get_db()
    conn.execute("UPDATE complaints SET status='Forwarded' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/incharge')


# ---------------- ASSIGN ---------------- #
@app.route('/assign/<int:id>', methods=['POST'])
def assign(id):
    if session.get('role') != 'admin':
        return "Access Denied ❌"

    person = request.form.get('person')

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT category FROM complaints WHERE id=?", (id,))
    category = cur.fetchone()[0]

    if not person or person == "Select Worker":
        if category == "Library":
            person = "Librarian"
        elif category == "Examination Branch Issues":
            person = "Examination Incharge"
        else:
            person = "Cleaner"

    phone_map = {
        "Electrician": "9876543210",
        "Plumber": "9123456780",
        "Cleaner": "9000000000",
        "Librarian": "9011111111",
        "Examination Incharge": "9022222222"
    }

    phone = phone_map.get(person)

    cur.execute("""
        UPDATE complaints 
        SET assigned_to=?, phone=?, assigned_by=?, status='In Progress'
        WHERE id=?
    """, (person, phone, session['user'], id))

    conn.commit()
    conn.close()

    return redirect('/admin')


# ---------------- ADMIN ---------------- #
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('role') != 'admin':
        return "Access Denied ❌"

    conn = get_db()

    if request.method == 'POST':
        cid = request.form['id']
        status = request.form['status']

        conn.execute(
            "UPDATE complaints SET status=?, updated_by=? WHERE id=?",
            (status, "Admin", cid)
        )
        conn.commit()

    complaints = conn.execute(
        "SELECT * FROM complaints WHERE status IN ('Forwarded','In Progress')"
    ).fetchall()

    conn.close()
    return render_template('admin.html', complaints=complaints)


# ---------------- RUN ---------------- #
if __name__ == '__main__':
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT,
        role TEXT,
        email TEXT
    )
    """)

    cur.execute("""
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

    for col in ["assigned_to", "phone", "assigned_by"]:
        try:
            cur.execute(f"ALTER TABLE complaints ADD COLUMN {col} TEXT")
        except:
            pass

    conn.commit()
    conn.close()

    app.run(debug=True)