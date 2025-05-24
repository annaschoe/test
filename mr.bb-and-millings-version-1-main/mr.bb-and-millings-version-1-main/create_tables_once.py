import sqlite3

db_path = "HER-SKRIVER-DU-HELE-VEJEN-TIL-DIN-DATABASE-FIL.db"  # fx "instance/app.db" eller hvad din config siger

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS damaged_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        location TEXT NOT NULL,
        user_id INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS opened_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        location TEXT NOT NULL,
        user_id INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()
conn.close()
print("Tables created!")
