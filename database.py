import sqlite3
import os
from pathlib import Path

DB_PATH = "data/machines_business.db"

def get_connection():
    """Get database connection"""
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schema"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Machines table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS machines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL CHECK(type IN ('Pikachu', 'Pinball')),
        status TEXT NOT NULL CHECK(status IN ('Activa', 'Mantenimiento', 'Inactiva')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Locations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT NOT NULL,
        neighborhood TEXT NOT NULL,
        landlord TEXT NOT NULL,
        phone TEXT NOT NULL,
        machine_id INTEGER UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(machine_id) REFERENCES machines(id)
    )
    """)
    
    # Income table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        date DATE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(machine_id) REFERENCES machines(id)
    )
    """)
    
    # Expenses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id INTEGER NOT NULL,
        expense_type TEXT NOT NULL CHECK(expense_type IN ('Repuestos', 'Mantenimiento', 'Transporte')),
        amount REAL NOT NULL,
        date DATE NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(machine_id) REFERENCES machines(id)
    )
    """)
    
    conn.commit()
    
    # Initialize with 65 machines if empty
    cursor.execute("SELECT COUNT(*) FROM machines")
    if cursor.fetchone()[0] == 0:
        # Create 65 machines: 40 Pikachu, 25 Pinball
        machines = [(f'Pikachu', 'Activa') for _ in range(40)] + \
                   [(f'Pinball', 'Activa') for _ in range(25)]
        cursor.executemany("INSERT INTO machines (type, status) VALUES (?, ?)", machines)
        conn.commit()
    
    conn.close()
