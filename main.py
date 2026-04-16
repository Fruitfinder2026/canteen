from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import pandas as pd
import requests
from fastapi import Body


app = FastAPI()

CACHE = {
    "orders": [],
    "last_fetch": None
}

SHEET_URL = "https://script.google.com/macros/s/AKfycbyoPGSPn13L8gmTzcjpOEjxTBKnWYh74dIJlcpmxDjuHUzM5FIC5g6hAn2aggOQwcCd/exec"

# ---------------- SETTINGS ----------------
def get_settings():
    try:
        res = requests.get(SHEET_URL, timeout=5)
        data = res.json()

        for r in data:
            if str(r.get("name")).upper() == "SETTINGS":
                s = r.get("items", "")
                out = {}
                for part in s.split(";"):
                    if "=" in part:
                        k, v = part.split("=")
                        out[k.strip()] = v.strip()
                return out
    except:
        pass

    return {"cutoff": "19:00", "whatsapp": "off"}


@app.get("/settings")
def settings_api():
    return get_settings()


@app.post("/save-settings")
def save_settings(data: dict = Body(...)):
    payload = {
        "type": "settings",
        "items": f"cutoff={data['cutoff']};whatsapp={data['whatsapp']}"
    }

    requests.post(SHEET_URL, json=payload)
    return {"status": "saved"}


# ---------------- MODEL ----------------
class Order(BaseModel):
    name: str
    items: dict
    instruction: str = ""


# ---------------- TIME ----------------
def ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


# ---------------- DATE PARSER ----------------
def parse_date(raw):
    raw = str(raw).strip()

    formats = [
        "%d-%m-%Y %H:%M",        # ✅ YOUR SHEET FORMAT (FIXED)
        "%d-%m-%Y %I:%M %p",
        "%d-%m-%Y",
        "%Y-%m-%d"
    ]

    for f in formats:
        try:
            return datetime.strptime(raw, f)
        except:
            continue

    return None


# ---------------- ROUTES ----------------
from fastapi.responses import FileResponse
import os

@app.get("/")
def home():
    file_path = os.path.join(os.getcwd(), "index.html")

    if not os.path.exists(file_path):
        return {"error": "index.html not found on server"}

    return FileResponse(file_path)


@app.get("/admin")
def admin_page():
    file_path = os.path.join(os.getcwd(), "admin.html")

    if not os.path.exists(file_path):
        return {"error": "admin.html not found"}

    return FileResponse(file_path)

# ---------------- MENU ----------------
menu = {
    "Monday": ["Samosa", "Gulab Jamun", "Jalebi"],
    "Tuesday": ["Kachori", "Gulab Jamun", "Jalebi"],
    "Wednesday": ["Veg Cutlet", "Gulab Jamun", "Jalebi"],
    "Thursday": ["Onion Pakoda", "Aloo Bonda", "Gulab Jamun", "Jalebi"],
    "Friday": ["Boondi Laddu", "Gulab Jamun", "Jalebi"],
    "Saturday": ["Tea"]
}


@app.get("/menu")
def get_menu():
    now = ist()
    settings = get_settings()

    h, m = map(int, settings.get("cutoff", "19:00").split(":"))
    cutoff = now.replace(hour=h, minute=m, second=0)

    days = []

    if now < cutoff:
        days.append(now)

    days.append(now + timedelta(days=1))

    result = []

    for d in days:
        result.append({
            "date": d.strftime("%Y-%m-%d"),
            "day": d.strftime("%A"),
            "items": menu.get(d.strftime("%A"), [])
        })

    return result


# ---------------- ORDER ----------------
@app.post("/order")
def order(o: Order, request: Request):
    now = ist()
    settings = get_settings()

    h, m = map(int, settings.get("cutoff", "19:00").split(":"))
    cutoff = now.replace(hour=h, minute=m)

    if now >= cutoff:
        return {"error": "Booking closed"}

    time_str = now.strftime("%d-%m-%Y %I:%M %p")

    payload = {
        "name": o.name,
        "items": json.dumps(o.items),
        "date": time_str,
        "time": time_str,
        "ip": request.client.host,
        "instruction": o.instruction,
        "device": request.headers.get("user-agent")
    }

    requests.post(SHEET_URL, json=payload)

    return {"message": "ok"}


# ---------------- ORDERS ----------------
from datetime import timedelta

@app.get("/orders")
def orders():

    now = ist()

    # ⏱ 10-second cache
    if CACHE["last_fetch"] and (now - CACHE["last_fetch"]).seconds < 10:
        return CACHE["orders"]

    try:
        res = requests.get(SHEET_URL, timeout=5)
        data = res.json()
    except:
        return []

    result = []

    for r in data:

        dt = parse_date(r.get("date"))
        if not dt:
            dt = now

        if (now - dt).days > 7:
            continue

        try:
            items = json.loads(r["items"])
        except:
            continue

        items_text = ", ".join([
            f"{k}({v})" for k, v in items.items() if str(v) != "0"
        ])

        result.append({
            "name": r["name"],
            "items": items_text,
            "date": r["date"],
            "instruction": r.get("instruction", "")
        })

    result = list(reversed(result))

    CACHE["orders"] = result
    CACHE["last_fetch"] = now

    return result

# ---------------- ADMIN ----------------
@app.get("/admin-data")
def admin_data(password: str):

    if password != "admin123":
        return {"error": "unauthorized"}

    try:
        res = requests.get(SHEET_URL, timeout=5)
        data = res.json()
    except:
        return {}

    now = ist()
    count = {}

    for r in data:

        dt = parse_date(r.get("date"))

        if not dt:
            dt = now

        if dt.date() != now.date():
            continue

        try:
            items = json.loads(r["items"])
        except:
            continue

        for k, v in items.items():

            if str(v) == "0":
                continue

            if k == "Jalebi":
                val = int(str(v).replace("g", "").strip())
            else:
                val = int(v)

            count[k] = count.get(k, 0) + val

    return count


# ---------------- EXPORT ----------------
@app.get("/export")
def export():
    res = requests.get(SHEET_URL)
    rows = res.json()

    data = []

    for r in rows:
        try:
            items = json.loads(r["items"])
            text = ", ".join([f"{k}({v})" for k, v in items.items()])
        except:
            continue

        data.append({
            "Name": r["name"],
            "Items": text,
            "Date": r["date"],
            "Instruction": r.get("instruction", "")
        })

    df = pd.DataFrame(data)
    file = "orders.xlsx"
    df.to_excel(file, index=False)

    return FileResponse(file)