from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3
import json
import pandas as pd

app = FastAPI()

conn = sqlite3.connect("orders.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    items TEXT,
    date TEXT,
    ip TEXT,
    user_agent TEXT,
    timestamp TEXT
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

# ? Get menu
@app.get("/menu")
def get_menu():
    tomorrow = datetime.now() + timedelta(days=1)
    day = tomorrow.strftime("%A")

    return {
        "date": tomorrow.strftime("%Y-%m-%d"),
        "day": day,
        "items": menu.get(day, [])
    }

# ? Place order with checks
@app.post("/order")
def place_order(order: Order, request: Request):

    now = datetime.now()

    # ? Cutoff time (7 PM)
    if now.hour >= 19:
        return {"error": "Booking closed after 7 PM"}

    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    # ? Duplicate check
    cursor.execute(
        "SELECT * FROM orders WHERE name=? AND date=?",
        (order.name, tomorrow)
    )

    if cursor.fetchone():
        return {"error": "You have already placed an order for tomorrow"}

    # ?? Device tracking
    ip = request.client.host
    user_agent = request.headers.get("user-agent")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        "INSERT INTO orders (name, items, date, ip, user_agent, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (order.name, json.dumps(order.items), tomorrow, ip, user_agent, timestamp)
    )
    conn.commit()

    return {"message": "Order placed successfully"}

# ? Get last 7 days orders
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

# ? Admin Dashboard (count items)
@app.get("/admin")
def admin_dashboard():
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT items FROM orders WHERE date=?",
        (tomorrow,)
    )

    rows = cursor.fetchall()

    count = {}

    for r in rows:
        items = json.loads(r[0])
        for item in items:
            count[item] = count.get(item, 0) + 1

    return count

# ? Export Excel
@app.get("/export")
def export_excel():
    cursor.execute("SELECT name, items, date, ip, timestamp FROM orders")
    rows = cursor.fetchall()

    data = []
    for r in rows:
        data.append({
            "Name": r[0],
            "Items": ", ".join(json.loads(r[1])),
            "Date": r[2],
            "IP": r[3],
            "Time": r[4]
        })

    df = pd.DataFrame(data)
    file_path = "orders.xlsx"
    df.to_excel(file_path, index=False)

    return FileResponse(file_path, filename="orders.xlsx")