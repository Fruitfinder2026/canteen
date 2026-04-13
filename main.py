from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import json, requests

app = FastAPI()

SHEET_URL = "https://script.google.com/macros/s/AKfycbyoPGSPn13L8gmTzcjpOEjxTBKnWYh74dIJlcpmxDjuHUzM5FIC5g6hAn2aggOQwcCd/exec"

from fastapi import Body

@app.post("/save-settings")
def save_settings(data: dict = Body(...)):

    cutoff = data.get("cutoff", "19:00")
    whatsapp = data.get("whatsapp", "off")

    payload = {
        "type": "settings",
        "items": f"cutoff={cutoff};whatsapp={whatsapp}"
    }

    try:
        requests.post(SHEET_URL, json=payload)
        return {"status": "saved"}
    except:
        return {"error": "failed"}
# ---------------- MODEL ----------------
class Order(BaseModel):
    name: str
    items: dict
    instruction: str = ""

# ---------------- TIME ----------------
def get_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ---------------- SETTINGS ----------------
def get_settings():

    try:
        data = requests.get(SHEET_URL).json()
    except:
        return {"cutoff": "19:00", "whatsapp": "off"}

    for r in data:
        if r["name"] == "SETTINGS":
            raw = r["items"]
            parts = dict(x.split("=") for x in raw.split(";"))
            return parts

    return {"cutoff": "19:00", "whatsapp": "off"}

# ---------------- BOOKING DAY ----------------
def get_booking_day():

    now = get_ist()
    settings = get_settings()

    cutoff = settings.get("cutoff", "19:00")
    cutoff_hour = int(cutoff.split(":")[0])

    if now.hour < cutoff_hour:
        return now  # SAME DAY
    else:
        return now + timedelta(days=1)

# ---------------- ROUTES ----------------
@app.get("/")
def home():
    return HTMLResponse(open("index.html").read())

@app.get("/admin-ui")
def admin():
    return HTMLResponse(open("admin.html").read())

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
def menu_api():

    d = get_booking_day()
    day = d.strftime("%A")

    return {
        "date": d.strftime("%Y-%m-%d"),
        "day": day,
        "items": menu.get(day, [])
    }

# ---------------- ORDER ----------------
@app.post("/order")
def order(o: Order, request: Request):

    now = get_ist()
    settings = get_settings()

    cutoff_hour = int(settings.get("cutoff", "19:00").split(":")[0])

    if now.hour >= cutoff_hour:
        return {"error": "Booking closed"}

    payload = {
        "name": o.name,
        "items": json.dumps(o.items),
        "date": now.strftime("%d-%m-%Y %I:%M %p"),
        "time": now.strftime("%d-%m-%Y %I:%M %p"),
        "ip": request.client.host,
        "instruction": o.instruction,
        "device": request.headers.get("user-agent")
    }

    requests.post(SHEET_URL, json=payload)

    # -------- WhatsApp --------
    if settings.get("whatsapp") == "on":

        msg = f"{o.name} ordered {o.items}"

        try:
            requests.get(
                f"https://api.callmebot.com/whatsapp.php?phone=YOUR_NUMBER&text={msg}&apikey=YOUR_API_KEY"
            )
        except:
            pass

    return {"msg": "Order placed"}

# ---------------- ORDERS ----------------
@app.get("/orders")
def orders():

    data = requests.get(SHEET_URL).json()
    result = []
    now = get_ist()

    for r in data:

        if r["name"] == "SETTINGS":
            continue

        raw = r.get("date","")

        try:
            dt = datetime.strptime(raw, "%d-%m-%Y %I:%M %p")
        except:
            dt = now

        if (now - dt).days > 7:
            continue

        items = json.loads(r["items"])

        formatted = ", ".join(f"{k}({v})" for k,v in items.items() if v!="0")

        result.append({
            "name": r["name"],
            "items": formatted,
            "date": raw,
            "instruction": r.get("instruction","")
        })

    result.reverse()
    return result

@app.post("/save-settings")
def save_settings(request: Request):

    data = request.json()