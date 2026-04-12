from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import pandas as pd
import requests

app = FastAPI()

# ---------------- MENU ----------------
menu = {
    "Monday": ["Samosa", "Gulab Jamun", "Jalebi"],
    "Tuesday": ["Kachori", "Gulab Jamun", "Jalebi"],
    "Wednesday": ["Veg Cutlet", "Gulab Jamun", "Jalebi"],
    "Thursday": ["Onion Pakoda", "Aloo Bonda", "Gulab Jamun", "Jalebi"],
    "Friday": ["Boondi Laddu", "Gulab Jamun", "Jalebi"],
    "Saturday": ["Tea"]
}

# ---------------- MODEL ----------------
class Order(BaseModel):
    name: str
    items: dict
    instruction: str = ""

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

@app.get("/ping")
def ping():
    return {"status": "alive"}

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

    ip = request.client.host
    user_agent = request.headers.get("user-agent")
    timestamp = now.strftime("%d-%m-%Y %I:%M %p")

    url = "https://script.google.com/macros/s/AKfycbyoPGSPn13L8gmTzcjpOEjxTBKnWYh74dIJlcpmxDjuHUzM5FIC5g6hAn2aggOQwcCd/exec"

    payload = {
        "name": order.name,
        "items": json.dumps(order.items),
        "date": timestamp,
        "ip": ip,
        "device": user_agent,
        "instruction": order.instruction
    }

    try:
        requests.post(url, json=payload)
    except:
        return {"error": "Failed to save order"}

    return {"message": "Order placed"}

# ORDERS (Last 7 Days)
@app.get("/orders")
def get_orders():

    url = "https://script.google.com/macros/s/AKfycbyoPGSPn13L8gmTzcjpOEjxTBKnWYh74dIJlcpmxDjuHUzM5FIC5g6hAn2aggOQwcCd/exec"

    res = requests.get(url)
    data = res.json()

    result = []
    now = get_ist_time()

    for r in data:
        try:
            dt = datetime.strptime(r["date"], "%d-%m-%Y %I:%M %p")
        except:
            continue

        if (now - dt).days > 7:
            continue

        items_dict = json.loads(r["items"])

        formatted_items = ", ".join([
            f"{k}({v})" for k, v in items_dict.items() if str(v) != "0"
        ])

        result.append({
            "name": r["name"],
            "items": formatted_items,
            "date": r["date"],
            "instruction": r.get("instruction", "")
        })

    return result

# ADMIN
@app.get("/admin")
def admin_dashboard(password: str):

    if password != "admin123":
        return {"error": "Unauthorized"}

    url = "https://script.google.com/macros/s/AKfycbyoPGSPn13L8gmTzcjpOEjxTBKnWYh74dIJlcpmxDjuHUzM5FIC5g6hAn2aggOQwcCd/exec"

    res = requests.get(url)
    data = res.json()

    count = {}

    for r in data:
        items = json.loads(r["items"])

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

    url = "https://script.google.com/macros/s/AKfycbyoPGSPn13L8gmTzcjpOEjxTBKnWYh74dIJlcpmxDjuHUzM5FIC5g6hAn2aggOQwcCd/exec"

    res = requests.get(url)
    rows = res.json()

    data = []

    for r in rows:
        items_dict = json.loads(r["items"])
        formatted_items = ", ".join([f"{k}({v})" for k, v in items_dict.items()])

        data.append({
            "Name": r["name"],
            "Items": formatted_items,
            "Date": r["date"],
            "Instruction": r.get("instruction", "")
        })

    df = pd.DataFrame(data)
    file_path = "orders.xlsx"
    df.to_excel(file_path, index=False)

    return FileResponse(file_path, filename="orders.xlsx")