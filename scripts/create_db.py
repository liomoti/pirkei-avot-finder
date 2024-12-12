import sqlite3
import os

# Ensure the 'data' directory exists
os.makedirs('data', exist_ok=True)

# Connect to the SQLite database (or create it if it doesn't exist) in the 'data' folder
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
db_path = f'sqlite:///{os.path.join(basedir, "data", "pirkei_avot.db")}'
conn = sqlite3.connect(db_path)

# Create a cursor object to execute SQL commands
cur = conn.cursor()

# Create the Mishna table with 'chapter' and 'mishna' fields
cur.execute('''
CREATE TABLE IF NOT EXISTS mishna (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter INTEGER NOT NULL,
    mishna INTEGER NOT NULL,
    text TEXT NOT NULL,
    interpretation TEXT
);
''')

# Create the Tag table
cur.execute('''
CREATE TABLE IF NOT EXISTS tag (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
''')

# Create the Mishna_Tag join table for the many-to-many relationship
cur.execute('''
CREATE TABLE IF NOT EXISTS mishna_tag (
    mishna_id INTEGER,
    tag_id INTEGER,
    FOREIGN KEY (mishna_id) REFERENCES mishna(id),
    FOREIGN KEY (tag_id) REFERENCES tag(id),
    PRIMARY KEY (mishna_id, tag_id)
);
''')

# Commit the changes and close the connection
conn.commit()
conn.close()

print("Database and tables created successfully in the 'data' folder!")
