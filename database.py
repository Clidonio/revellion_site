import sqlite3

conn = sqlite3.connect("revellion.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
email TEXT,
password TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
id INTEGER PRIMARY KEY AUTOINCREMENT,
title TEXT,
description TEXT,
price REAL,
creator TEXT,
file TEXT,
status TEXT
)
""")

conn.commit()
conn.close()

print("Banco de dados criado com sucesso!")
