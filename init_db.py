import sqlite3

conn = sqlite3.connect('database.db')

conn.execute("""
CREATE TABLE users(
    id INTEGER PRIMARY KEY,
    username TEXT,
    password TEXT,
    role TEXT
)
""")

conn.execute("""
CREATE TABLE complaints(
    id INTEGER PRIMARY KEY,
    title TEXT,
    description TEXT,
    category TEXT,
    status TEXT,
    username TEXT,
    created_at TEXT,
    priority TEXT
)
""")

conn.commit()
conn.close()

print("Database created successfully!")