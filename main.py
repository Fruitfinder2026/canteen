from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import pandas as pd
import requests
from fastapi import Body

app = FastAPI()


SHEET_URL = "https://script.google.com/macros/s/AKfycbyoPGSPn13L8gmTzcjpOEjxTBKnWYh74dIJlcpmxDjuHUzM5FIC5g6hAn2aggOQwcCd/exec"

def get_settings():
    try:
        res = requests.get(SHEET_URL, timeout=5)
        data = res.json()

        for r in data:
            if str(r.get("name")).strip().upper() == "SETTINGS":
                settings_str = r.get("items", "")

                settings = {}
                for part in settings_str.split(";"):
                    if "=" in part:
                        k, v = part.split("=")
                        settings[k.strip()] = v.strip()

                return settings

    except:
        pass

    return {"cutoff": "19:00", "whatsapp": "off"}  # fallback

@app.post("/save-settings")
def save_settings(data: dict = Body(...)):

    cutoff = data.get("cutoff", "19:00")
    whatsapp = data.get("whatsapp", "off")

    payload = {
        "type": "settings",
        "items": f"cutoff={cutoff};whatsapp={whatsapp}"
    }

    try:
        res = requests.post(SHEET_URL, json=payload, timeout=5)

        if res.status_code == 200:
            return {"status": "saved"}
        else:
            return {"error": "sheet error"}

    except Exception as e:
        return {"error": str(e)}
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

    if today.weekday() == 5:   # Saturday
        return today + timedelta(days=2)
    elif today.weekday() == 6: # Sunday
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

# ---------------- MENU ----------------
@app.get("/menu")
def get_menu():
    booking_date = get_booking_day()
    day = booking_date.strftime("%A")

    return {
        "date": booking_date.strftime("%Y-%m-%d"),
        "day": day,
        "items": menu.get(day, [])
    }

# ---------------- ORDER ----------------
@app.post("/order")
def place_order(order: Order, request: Request):

    now = get_ist_time()

    # 🔥 GET DYNAMIC SETTINGS
    settings = get_settings()
    cutoff = settings.get("cutoff", "19:00")

    try:
        cutoff_hour, cutoff_min = map(int, cutoff.split(":"))
    except:
        cutoff_hour, cutoff_min = 19, 0  # fallback

    # 🔥 APPLY DYNAMIC CUTOFF
    if (now.hour > cutoff_hour) or (now.hour == cutoff_hour and now.minute >= cutoff_min):
        return {"error": f"Booking closed after {cutoff}"}

    ip = request.client.host
    user_agent = request.headers.get("user-agent")

    formatted_time = now.strftime("%d-%m-%Y %I:%M %p")

    payload = {
        "name": order.name,
        "items": json.dumps(order.items),
        "date": formatted_time,
        "time": formatted_time,
        "ip": ip,
        "instruction": order.instruction,
        "device": user_agent
    }

    try:
        requests.post(SHEET_URL, json=payload, timeout=5)
    except:
        return {"error": "Failed to save order"}

    return {"message": "Order placed successfully"}

# ---------------- ORDERS ----------------
@app.get("/orders")
def get_orders():

    url = "https://script.google.com/macros/s/AKfycbyoPGSPn13L8gmTzcjpOEjxTBKnWYh74dIJlcpmxDjuHUzM5FIC5g6hAn2aggOQwcCd/exec"

    try:
        res = requests.get(url, timeout=5)
        data = res.json()
    except:
        return []

    result = []
    now = get_ist_time()

    for r in data:

        raw_date = str(r.get("date", "")).strip()
        dt = None

        # 🔥 robust parsing (ALL formats supported)
        for fmt in [
            "%d-%m-%Y %I:%M %p",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y",
            "%Y-%m-%d"
        ]:
            try:
                dt = datetime.strptime(raw_date, fmt)
                break
            except:
                continue

        # fallback (never skip order)
        if not dt:
            dt = now

        # last 7 days filter
        if (now - dt).days > 7:
            continue

        try:
            items_dict = json.loads(r["items"])
        except:
            continue

        formatted_items = ", ".join([
            f"{k}({v})" for k, v in items_dict.items() if str(v) != "0"
        ])

        result.append({
            "name": r["name"],
            "items": formatted_items,
            "date": raw_date,
            "instruction": r.get("instruction", "")
        })

    # latest first
    result.reverse()

    return result

# ---------------- ADMIN ----------------
@app.get("/admin")
def admin_dashboard(password: str):

    if password != "admin123":
        return {"error": "Unauthorized"}

    url = "https://script.google.com/macros/s/AKfycbyoPGSPn13L8gmTzcjpOEjxTBKnWYh74dIJlcpmxDjuHUzM5FIC5g6hAn2aggOQwcCd/exec"

    try:
        res = requests.get(url, timeout=5)
        data = res.json()
    except:
        return {}

    count = {}
    today = get_ist_time().strftime("%d-%m-%Y")

    for r in data:

        if today not in str(r.get("date", "")):
            continue

        try:
            items = json.loads(r["items"])
        except:
            continue

        for item, qty in items.items():
            if item == "Jalebi":
                grams = int(qty.replace("g", ""))
                count[item] = count.get(item, 0) + grams
            else:
                count[item] = count.get(item, 0) + int(qty)

    return count

# ---------------- EXPORT ----------------
@app.get("/export")
def export_excel():

    url = "https://script.google.com/macros/s/AKfycbyoPGSPn13L8gmTzcjpOEjxTBKnWYh74dIJlcpmxDjuHUzM5FIC5g6hAn2aggOQwcCd/exec"

    try:
        res = requests.get(url, timeout=5)
        rows = res.json()
    except:
        return {"error": "Failed to fetch data"}

    data = []

    for r in rows:
        try:
            items_dict = json.loads(r["items"])
        except:
            continue

        formatted_items = ", ".join([
            f"{k}({v})" for k, v in items_dict.items()
        ])

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
