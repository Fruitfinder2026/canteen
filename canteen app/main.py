from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3
import json

app = FastAPI()

conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    items TEXT,
    date TEXT
)
""")
conn.commit()

menu = {
    "Monday": ["Samosa", "Gulab Jamun", "Jalebi"],
    "Tuesday": ["Kachori", "Gulab Jamun", "Jalebi"],
    "Wednesday": ["Veg Cutlet", "Gulab Jamun", "Jalebi"],
    "Thursday": ["Onion Pakoda", "Aloo Bonda", "Gulab Jamun", "Jalebi"],
    "Friday": ["Boondi Laddu", "Gulab Jamun", "Jalebi"],
    "Saturday": ["Tea"]
}

class Order(BaseModel):
    name: str
    items: list

@app.get("/")
def home():
    return HTMLResponse(open("index.html").read())

@app.get("/menu")
def get_menu():
    tomorrow = datetime.now() + timedelta(days=1)
    day = tomorrow.strftime("%A")
    return {
        "date": tomorrow.strftime("%Y-%m-%d"),
        "day": day,
        "items": menu.get(day, [])
    }

@app.post("/order")
def place_order(order: Order):
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    cursor.execute(
        "INSERT INTO orders (name, items, date) VALUES (?, ?, ?)",
        (order.name, json.dumps(order.items), tomorrow)
    )
    conn.commit()

    return {"message": "Order placed successfully"}

@app.get("/orders")
def get_orders():
    last_week = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT name, items, date FROM orders WHERE date >= ? ORDER BY date DESC",
        (last_week,)
    )

    rows = cursor.fetchall()

    result = []
    for r in rows:
        result.append({
            "name": r[0],
            "items": json.loads(r[1]),
            "date": r[2]
        })

    return result