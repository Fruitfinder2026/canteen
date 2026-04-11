from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import sqlite3
import json
import pandas as pd

app = FastAPI()

# ---------------- DATABASE ----------------
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

# ---------------- MENU ----------------
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
    items: dict

# ---------------- TIME ----------------
def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def get_booking_day():
    today = get_ist_time()

    if today.weekday() == 5:
        return today + timedelta(days=2)
    elif today.weekday() == 6:
        return today + timedelta(days=1)
    else:
        return today + timedelta(days=1)

# ---------------- ROUTES ----------------

@app.get("/")
def home():
    return HTMLResponse(open("index.html").read())

@app.get("/admin-ui")
def admin_ui():
    return HTMLResponse(open("admin.html").read())

# MENU
@app.get("/menu")
def get_menu():
    booking_date = get_booking_day()
    day = booking_date.strftime("%A")

    return {
        "date": booking_date.strftime("%Y-%m-%d"),
        "day": day,
        "items": menu.get(day, [])
    }

# ORDER
@app.post("/order")
def place_order(order: Order, request: Request):

    now = get_ist_time()

    if now.hour >= 19:
        return {"error": "Booking closed after 7 PM"}

    booking_date = get_booking_day().strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT * FROM orders WHERE name=? AND date=?",
        (order.name, booking_date)
    )

    if cursor.fetchone():
        return {"error": "You already booked"}

    ip = request.client.host
    user_agent = request.headers.get("user-agent")
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        "INSERT INTO orders (name, items, date, ip, user_agent, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (order.name, json.dumps(order.items), booking_date, ip, user_agent, timestamp)
    )
    conn.commit()

    return {"message": "Order placed"}

# ORDERS
@app.get("/orders")
def get_orders():
    last_week = (get_ist_time() - timedelta(days=7)).strftime("%Y-%m-%d")

    cursor.execute(
        "SELECT name, items, date FROM orders WHERE date >= ? ORDER BY date DESC",
        (last_week,)
    )

    rows = cursor.fetchall()

    result = []
    for r in rows:
        items_dict = json.loads(r[1])
        formatted = ", ".join([f"{k}({v})" for k, v in items_dict.items()])

        result.append({
            "name": r[0],
            "items": formatted,
            "date": r[2]
        })

    return result

# ADMIN
@app.get("/admin")
def admin_dashboard(password: str):
    if password != "admin123":
        return {"error": "Unauthorized"}

    booking_date = get_booking_day().strftime("%Y-%m-%d")

    cursor.execute("SELECT items FROM orders WHERE date=?", (booking_date,))
    rows = cursor.fetchall()

    count = {}

    for r in rows:
        items = json.loads(r[0])

        for item, qty in items.items():
            if item == "Jalebi":
                grams = int(qty.replace("g", ""))
                count[item] = count.get(item, 0) + grams
            else:
                count[item] = count.get(item, 0) + int(qty)

    return count

# EXPORT
@app.get("/export")
def export_excel():
    cursor.execute("SELECT name, items, date, ip, timestamp FROM orders")
    rows = cursor.fetchall()

    data = []
    for r in rows:
        items_dict = json.loads(r[1])
        formatted_items = ", ".join([f"{k}({v})" for k, v in items_dict.items()])

        data.append({
            "Name": r[0],
            "Items": formatted_items,
            "Date": r[2],
            "IP": r[3],
            "Time": r[4]
        })

    df = pd.DataFrame(data)
    file_path = "orders.xlsx"
    df.to_excel(file_path, index=False)

    return FileResponse(file_path, filename="orders.xlsx")