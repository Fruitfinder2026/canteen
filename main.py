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
ADMIN_WHATSAPP = "917021740931"  # <-- change

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
                        k,v = part.split("=")
                        out[k.strip()] = v.strip()
                return out
    except:
        pass

    return {"cutoff":"19:00","whatsapp":"off"}

@app.get("/settings")
def settings_api():
    return get_settings()

@app.post("/save-settings")
def save_settings(data: dict = Body(...)):
    payload = {
        "type":"settings",
        "items": f"cutoff={data['cutoff']};whatsapp={data['whatsapp']}"
    }

    res = requests.post(SHEET_URL, json=payload)
    return {"status":"saved"} if res.status_code==200 else {"error":"fail"}

# ---------------- MENU ----------------
menu = {
    "Monday": ["Samosa","Gulab Jamun","Jalebi"],
    "Tuesday": ["Kachori","Gulab Jamun","Jalebi"],
    "Wednesday": ["Veg Cutlet","Gulab Jamun","Jalebi"],
    "Thursday": ["Onion Pakoda","Aloo Bonda","Gulab Jamun","Jalebi"],
    "Friday": ["Boondi Laddu","Gulab Jamun","Jalebi"],
    "Saturday": ["Tea"]
}

# ---------------- MODEL ----------------
class Order(BaseModel):
    name:str
    items:dict
    instruction:str=""

# ---------------- TIME ----------------
def ist():
    return datetime.utcnow()+timedelta(hours=5,minutes=30)

# ---------------- ROUTES ----------------
@app.get("/")
def home():
    return HTMLResponse(open("index.html").read())

@app.get("/admin-ui")
def admin():
    return HTMLResponse(open("admin.html").read())

# ---------------- MENU LOGIC ----------------
@app.get("/menu")
def get_menu():
    now = ist()
    settings = get_settings()

    h,m = map(int, settings.get("cutoff","19:00").split(":"))
    cutoff = now.replace(hour=h,minute=m,second=0)

    days = []

    if now < cutoff:
        days.append(now)

    days.append(now+timedelta(days=1))

    result = []

    for d in days:
        result.append({
            "date": d.strftime("%Y-%m-%d"),
            "day": d.strftime("%A"),
            "items": menu.get(d.strftime("%A"),[])
        })

    return result

# ---------------- ORDER ----------------
@app.post("/order")
def order(o:Order, request:Request):

    now = ist()
    settings = get_settings()

    h,m = map(int, settings.get("cutoff","19:00").split(":"))
    cutoff = now.replace(hour=h,minute=m)

    if now >= cutoff:
        return {"error":"Booking closed"}

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

    # WhatsApp
    wa = ""
    if settings.get("whatsapp")=="on":
        msg = f"New Order\n{o.name}\n{o.items}"
        

    return {"message":"ok","whatsapp":wa}

# ---------------- ORDERS ----------------
@app.get("/orders")
def orders():

    try:
        res = requests.get(SHEET_URL, timeout=5)
        data = res.json()
    except:
        return []

    now = ist()
    result = []

    for r in data:

        raw_date = str(r.get("date","")).strip()
        dt = None

        # 🔥 MULTI FORMAT SUPPORT (THIS FIXES YOUR ISSUE)
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

        if not dt:
            continue

        if (now - dt).days > 7:
            continue

        try:
            items = json.loads(r["items"])
        except:
            continue

        items_text = ", ".join([
            f"{k}({v})" for k,v in items.items() if str(v)!="0"
        ])

        result.append({
            "name": r["name"],
            "items": items_text,
            "date": raw_date,
            "instruction": r.get("instruction","")
        })

    return list(reversed(result))

# ---------------- ADMIN ----------------
@app.get("/admin")
def admin(password:str):

    if password!="admin123":
        return {"error":"unauthorized"}

    res = requests.get(SHEET_URL)
    data = res.json()

    today = ist().strftime("%d-%m-%Y")
    count={}

    for r in data:
        if today not in str(r["date"]):
            continue

        items=json.loads(r["items"])

        for k,v in items.items():
            if k=="Jalebi":
                count[k]=count.get(k,0)+int(v.replace("g",""))
            else:
                count[k]=count.get(k,0)+int(v)

    return count

# ---------------- EXPORT ----------------
@app.get("/export")
def export():

    res = requests.get(SHEET_URL)
    rows = res.json()

    data=[]

    for r in rows:
        items=json.loads(r["items"])
        text=", ".join([f"{k}({v})" for k,v in items.items()])

        data.append({
            "Name":r["name"],
            "Items":text,
            "Date":r["date"],
            "Instruction":r.get("instruction","")
        })

    df=pd.DataFrame(data)
    file="orders.xlsx"
    df.to_excel(file,index=False)

    return FileResponse(file)