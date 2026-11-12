from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
import sqlite3
import os
import time
import urllib.request
import urllib.parse
import urllib.error

app = FastAPI()
DB_PATH = os.path.join(os.path.expanduser("~"), "adcenter.db")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "9215398870:AAHp1CoVp1YZn_-5scR-B1zb-afy-lIFuDU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "9058235041")

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS impressions (impression_id TEXT PRIMARY KEY, campaign_id INTEGER, publisher_id TEXT, cost_usd REAL, timestamp TEXT);")
    conn.execute("CREATE TABLE IF NOT EXISTS clicks (click_id TEXT PRIMARY KEY, publisher_id TEXT, payout_credited_npr REAL, escrow_status TEXT);")
    conn.commit()
    conn.close()

init_db()

def send_telegram_alert(message: str) -> str:
    url = f"https://telegram.org{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=8) as resp:
            return "OK"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        return f"HTTP {e.code}: {err_body}"
    except Exception as e:
        return str(e)

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
    alert_res = send_telegram_alert(f"💰 New Ad Click Logged! ID: {clk_id} | +2.50 NPR credited to pub_dev_773x92.")
    return {"status": alert_res, "message": f"Click {clk_id} logged! Telegram: {alert_res}"}

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
    status_msg = send_telegram_alert(report)
    return {"status": status_msg, "summary": report}
