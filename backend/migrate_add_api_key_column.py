"""
Migration script to add encrypted_gemini_api_key column to users table.
Run this once to update the database schema.
"""
import sqlite3
import os

# Database path
db_path = os.path.join(os.path.dirname(__file__), "data", "secure_legal.db")

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if column already exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'encrypted_gemini_api_key' in columns:
        print("✅ Column 'encrypted_gemini_api_key' already exists. No migration needed.")
    else:
        # Add the new column
        cursor.execute("ALTER TABLE users ADD COLUMN encrypted_gemini_api_key TEXT;")
        conn.commit()
        print("✅ Successfully added 'encrypted_gemini_api_key' column to users table.")
        
except sqlite3.Error as e:
    print(f"❌ Error during migration: {e}")
    conn.rollback()
finally:
    conn.close()

print("\n📊 Current users table schema:")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(users)")
for row in cursor.fetchall():
    print(f"  - {row[1]} ({row[2]})")
conn.close()
