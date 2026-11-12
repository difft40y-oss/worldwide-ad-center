from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
import sqlite3
import os
import time
import urllib.request
import urllib.parse
import json

app = FastAPI()
HOME_DIR = os.path.expanduser("~")
DB_PATH = os.path.join(HOME_DIR, "adcenter.db")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "9215398870:AAHp1CoVp1YZn_-5scR-B1zb-afy-lIFuDU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "9058235041")

CLICK_COOLDOWN_SECONDS = 60
ip_click_tracker = {}

class PayoutRequest(BaseModel):
    publisher_id: str = Field(..., example="pub_dev_773x92")
    wallet_phone: str = Field(..., pattern=r"^9\d{9}$", example="9703544008")
    amount_npr: float = Field(..., gt=0, example=5.00)

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS publishers (publisher_id TEXT PRIMARY KEY, publisher_name TEXT, esewa_phone TEXT, account_status TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS campaigns (campaign_id INTEGER PRIMARY KEY AUTOINCREMENT, advertiser_id TEXT, campaign_name TEXT, max_cpm_bid REAL, target_geos TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS impressions (impression_id TEXT PRIMARY KEY, campaign_id INTEGER, publisher_id TEXT, cost_usd REAL, timestamp TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS clicks (click_id TEXT PRIMARY KEY, publisher_id TEXT, payout_credited_npr REAL, escrow_status TEXT);")
    
    # Seed initial campaign if empty so Render cloud boots with live data
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM campaigns")
    if cur.fetchone()[0] == 0:
        conn.execute("INSERT INTO campaigns (advertiser_id, campaign_name, max_cpm_bid, target_geos) VALUES ('adv_nepal_01', 'Premium Q4 APAC Push', 5.25, 'NP,US');")
    conn.commit()
    conn.close()

init_db()

def send_telegram_alert(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return str(e)
    url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=5)
        return "OK"
    except Exception:
        return str(e)

@app.middleware("http")
async def anti_fraud_click_gate(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/payout/esewa":
        client_ip = request.client.host if request.client else "127.0.0.1"
        current_time = time.time()
        if client_ip in ip_click_tracker:
            elapsed = current_time - ip_click_tracker[client_ip]
            if elapsed < CLICK_COOLDOWN_SECONDS:
                raise HTTPException(status_code=429, detail=f"Anti-Fraud Triggered! Wait {int(CLICK_COOLDOWN_SECONDS - elapsed)}s.")
        ip_click_tracker[client_ip] = current_time
    return await call_next(request)

@app.get("/", response_class=HTMLResponse)
async def root_hub(db: sqlite3.Connection = Depends(get_db)):
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM impressions")
    imp = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*), SUM(payout_credited_npr) FROM clicks")
    row = cur.fetchone()
    clk = row[0] or 0
    earn = round(row[1] or 0.0, 2)
    ctr = round((clk / imp * 100), 2) if imp > 0 else 0.0
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Worldwide Ad Center Live Hub</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; margin: 0; }}
            .card {{ background: #1e293b; padding: 18px; border-radius: 12px; border: 1px solid #334155; margin-bottom: 15px; }}
            .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }}
            .stat {{ background: #0f172a; padding: 12px; border-radius: 8px; text-align: center; border: 1px solid #475569; }}
            .val {{ font-size: 22px; font-weight: bold; color: #22c55e; }}
            .btn {{ display: block; background: #38bdf8; color: #0f172a; text-align: center; padding: 12px; border-radius: 8px; font-weight: bold; text-decoration: none; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2 style="margin:0 0 5px 0;">Worldwide Ad Center Live Hub</h2>
            <p style="color:#94a3b8; font-size:12px; margin:0;">Publisher ID: pub_dev_773x92</p>
        </div>
        <div class="card">
            <div class="grid">
                <div class="stat"><div>IMPRESSIONS</div><div class="val">{imp}</div></div>
                <div class="stat"><div>CLICKS</div><div class="val">{clk}</div></div>
                <div class="stat"><div>CTR %</div><div class="val">{ctr}%</div></div>
                <div class="stat"><div>EARNED</div><div class="val">{earn} NPR</div></div>
            </div>
            <a href="/simulate-app" class="btn">OPEN LIVE MOBILE APP AD SIMULATOR</a>
            <a href="/api/v1/health/telegram-report" class="btn" style="background:#22c55e;">SEND TELEGRAM HEALTH REPORT NOW</a>
        </div>
    </body>
    </html>
    """

# ==========================================
# OPTION 2: LIVE MOBILE APP AD SIMULATION
# ==========================================
@app.get("/simulate-app", response_class=HTMLResponse)
async def simulate_mobile_app(db: sqlite3.Connection = Depends(get_db)):
    imp_id = f"IMP-SIM-{int(time.time() * 1000)}"
    db.execute("INSERT INTO impressions (impression_id, campaign_id, publisher_id, cost_usd, timestamp) VALUES (?, 1, 'pub_dev_773x92', 0.005, datetime('now'))", (imp_id,))
    db.commit()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mobile App Ad Simulator</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: sans-serif; background: #020617; color: #f8fafc; display: flex; justify-content: center; padding: 20px; }}
            .phone {{ width: 320px; border: 4px solid #334155; border-radius: 28px; background: #0f172a; padding: 16px; }}
            .ad-banner {{ background: linear-gradient(135deg, #2563eb, #1d4ed8); padding: 16px; border-radius: 12px; text-align: center; margin: 20px 0; cursor: pointer; }}
            .btn {{ background: #22c55e; color: #0f172a; border: none; padding: 10px 16px; border-radius: 6px; font-weight: bold; width: 100%; margin-top: 10px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <div class="phone">
            <div style="text-align:center; font-size:12px; color:#94a3b8;">SIMULATED ANDROID APP VIEW</div>
            <p style="font-size:13px; color:#cbd5e1;">Live Impression Logged: <b>{imp_id}</b></p>
            <div class="ad-banner" onclick="recordClick()">
                <div style="font-size:10px; text-transform:uppercase; letter-spacing:1px;">Sponsored Ad</div>
                <h3 style="margin:6px 0;">Premium Q4 APAC Push</h3>
                <p style="font-size:12px; margin:0 0 10px 0;">Tap banner to simulate real user click (+2.50 NPR)</p>
                <button class="btn">TAP AD BANNER</button>
            </div>
            <div id="status" style="font-size:12px; color:#38bdf8; text-align:center; min-height:20px;"></div>
            <a href="/" style="display:block; text-align:center; color:#94a3b8; font-size:12px; margin-top:20px;">Back to Main Hub</a>
        </div>
        <script>
            async function recordClick() {{
                document.getElementById('status').innerText = 'Recording verified click...';
                const res = await fetch('/api/v1/simulate-click', {{ method: 'POST' }});
                const data = await res.json();
                document.getElementById('status').innerText = data.message;
            }}
        </script>
    </body>
    </html>
    """

@app.post("/api/v1/simulate-click")
async def record_simulated_click(db: sqlite3.Connection = Depends(get_db)):
    clk_id = f"CLK-SIM-{int(time.time() * 1000)}"
    db.execute("INSERT INTO clicks (click_id, publisher_id, payout_credited_npr, escrow_status) VALUES (?, 'pub_dev_773x92', 2.50, 'locked')", (clk_id,))
    db.commit()
    send_telegram_alert(f"💰 New Ad Click Logged! ID: {clk_id} | +2.50 NPR credited to pub_dev_773x92.")
    return {"status": "success", "message": f"Click {clk_id} logged! +2.50 NPR added."}

# ==========================================
# OPTION 3: AUTOMATED TELEGRAM HEALTH CHECK
# ==========================================
@app.get("/api/v1/health/telegram-report")
async def trigger_telegram_health_report(db: sqlite3.Connection = Depends(get_db)):
    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM impressions")
    imp = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*), SUM(payout_credited_npr) FROM clicks WHERE escrow_status='locked'")
    row = cur.fetchone()
    clk = row[0] or 0
    locked_npr = round(row[1] or 0.0, 2)
    
    report = (
        f"📊 WORLDWIDE AD CENTER HEALTH CHECK\n"
        f"• Publisher: pub_dev_773x92\n"
        f"• Total Impressions: {imp}\n"
        f"• Locked Clicks: {clk}\n"
        f"• Available Escrow: {locked_npr} NPR\n"
        f"• Anti-Fraud Gate: ACTIVE"
    )
    sent = send_telegram_alert(report)
    return {"status": sent, "summary": report}
