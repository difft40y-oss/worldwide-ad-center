from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
import sqlite3, os, time, urllib.request, urllib.parse

app = FastAPI()
DB_PATH = os.path.join(os.path.expanduser("~"), "adcenter.db")
DATABASE_URL = os.getenv("DATABASE_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "9215398870:AAHp1CoVp1YZn_-5scR-B1zb-afy-lIFuDU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "9058235041")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

class DBWrapper:
    def __init__(self):
        if DATABASE_URL:
            import psycopg2
            self.conn = psycopg2.connect(DATABASE_URL)
            self.is_pg = True
        else:
            self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            self.is_pg = False
    def execute(self, q, params=()):
        if self.is_pg:
            q = q.replace("?", "%s")
        cur = self.conn.cursor()
        cur.execute(q, params)
        return cur
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()

def get_db():
    db = DBWrapper()
    try:
        yield db
    finally:
        db.close()

def init_db():
    db = DBWrapper()
    db.execute("CREATE TABLE IF NOT EXISTS impressions (impression_id TEXT PRIMARY KEY, publisher_id TEXT, timestamp TEXT);")
    db.execute("CREATE TABLE IF NOT EXISTS clicks (click_id TEXT PRIMARY KEY, publisher_id TEXT, payout_credited_npr REAL, escrow_status TEXT);")
    db.commit()
    db.close()

init_db()

def send_telegram_alert(message: str) -> str:
    url = "https://" + "api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=8)
        return "OK"
    except Exception as e:
        return str(e)

@app.get("/", response_class=HTMLResponse)
async def root_hub(db: DBWrapper = Depends(get_db)):
    imp = db.execute("SELECT COUNT(*) FROM impressions").fetchone()[0] or 0
    row = db.execute("SELECT COUNT(*), COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()
    clk, earn = row[0], round(float(row[1]), 2)
    ctr = round((clk / imp * 100), 2) if imp > 0 else 0.0
    db_mode = "Cloud PostgreSQL (Permanent)" if db.is_pg else "Local SQLite (Temporary)"
    return f"""<!DOCTYPE html><html><head><title>Worldwide Ad Center</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body{{font-family:sans-serif;background:#0f172a;color:#f8fafc;padding:20px;margin:0}}.card{{background:#1e293b;padding:18px;border-radius:12px;border:1px solid #334155;margin-bottom:15px}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.stat{{background:#0f172a;padding:12px;border-radius:8px;text-align:center;border:1px solid #475569}}.val{{font-size:22px;font-weight:bold;color:#22c55e}}.btn{{display:block;background:#38bdf8;color:#0f172a;text-align:center;padding:12px;border-radius:8px;font-weight:bold;text-decoration:none;margin-top:10px}}</style></head>
    <body><div class="card"><h2 style="margin:0 0 5px 0;">Worldwide Ad Center Hub</h2><p style="color:#94a3b8;font-size:12px;margin:0;">Storage: <b>{db_mode}</b></p></div>
    <div class="card"><div class="grid"><div class="stat"><div>IMPRESSIONS</div><div class="val">{imp}</div></div><div class="stat"><div>LOCKED CLICKS</div><div class="val">{clk}</div></div><div class="stat"><div>CTR %</div><div class="val">{ctr}%</div></div><div class="stat"><div>AVAILABLE</div><div class="val">{earn} NPR</div></div></div>
    <a href="/simulate-app" class="btn">1. OPEN MOBILE APP AD SIMULATOR</a>
    <a href="/payout-hub" class="btn" style="background:#f59e0b;">2. OPEN ESEWA WITHDRAWAL PORTAL</a>
    <a href="/tag-preview" class="btn" style="background:#a855f7;color:#fff;">3. GET WEBSITE AD TAG (&lt;script&gt;)</a>
    <a href="/api/v1/health/telegram-report" class="btn" style="background:#22c55e;">4. SEND TELEGRAM HEALTH REPORT</a></div></body></html>"""

class PayoutReq(BaseModel):
    wallet_phone: str
    amount_npr: float

@app.get("/simulate-app", response_class=HTMLResponse)
async def simulate_app(db: DBWrapper = Depends(get_db)):
    imp_id = f"IMP-{int(time.time()*1000)}"
    db.execute("INSERT INTO impressions (impression_id, publisher_id, timestamp) VALUES (?, 'pub_dev_773x92', 'now')", (imp_id,))
    db.commit()
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#020617;color:#fff;padding:20px;text-align:center}}.banner{{background:#2563eb;padding:20px;border-radius:12px;margin:20px 0;cursor:pointer}}.btn{{background:#22c55e;border:none;padding:10px 20px;border-radius:6px;font-weight:bold}}</style></head>
    <body><h3>Simulated App Ad</h3><p>Impression: {imp_id}</p><div class="banner" onclick="clk()"><h4>Premium Q4 APAC Push</h4><p>Tap to earn +2.50 NPR</p><button class="btn">TAP BANNER</button></div><div id="st"></div><br><a href="/" style="color:#94a3b8">Back to Hub</a>
    <script>async function clk(){{const r=await fetch('/api/v1/simulate-click',{{method:'POST'}});const d=await r.json();document.getElementById('st').innerText=d.message;}}</script></body></html>"""

@app.post("/api/v1/simulate-click")
async def sim_click(db: DBWrapper = Depends(get_db)):
    clk_id = f"CLK-{int(time.time()*1000)}"
    db.execute("INSERT INTO clicks (click_id, publisher_id, payout_credited_npr, escrow_status) VALUES (?, 'pub_dev_773x92', 2.50, 'locked')", (clk_id,))
    db.commit()
    send_telegram_alert(f"💰 Click Logged: {clk_id} (+2.50 NPR)")
    return {"message": f"Click {clk_id} recorded (+2.50 NPR)!"}

@app.get("/payout-hub", response_class=HTMLResponse)
async def payout_hub(db: DBWrapper = Depends(get_db)):
    bal = round(float(db.execute("SELECT COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()[0]), 2)
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#fff;padding:20px}}.box{{background:#1e293b;padding:20px;border-radius:12px}}input{{width:100%;padding:12px;margin:8px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#22c55e;border:none;border-radius:6px;font-weight:bold;margin-top:10px}}</style></head>
    <body><div class="box"><h2>eSewa Withdrawal Portal</h2><p>Available Balance: <b style="color:#22c55e">{bal} NPR</b></p>
    <input id="ph" value="9703544008" placeholder="eSewa Phone"><input id="am" type="number" step="0.01" value="{bal}" placeholder="Amount NPR">
    <button class="btn" onclick="wd()">REQUEST ESEWA PAYOUT</button><p id="res" style="color:#38bdf8"></p><a href="/" style="color:#94a3b8">Back to Hub</a></div>
    <script>async function wd(){{const r=await fetch('/payout/esewa',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{wallet_phone:document.getElementById('ph').value,amount_npr:parseFloat(document.getElementById('am').value)}})}});const d=await r.json();document.getElementById('res').innerText=d.message||d.detail;}}</script></body></html>"""

@app.post("/payout/esewa")
async def process_esewa(req: PayoutReq, db: DBWrapper = Depends(get_db)):
    bal = round(float(db.execute("SELECT COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()[0]), 2)
    if req.amount_npr <= 0 or req.amount_npr > bal:
        raise HTTPException(status_code=400, detail=f"Invalid amount. Available: {bal} NPR")
    db.execute("UPDATE clicks SET escrow_status='processed_success' WHERE escrow_status='locked'")
    db.commit()
    send_telegram_alert(f"💸 eSewa Payout Settled!\n• Wallet: {req.wallet_phone}\n• Amount: {req.amount_npr} NPR")
    return {"message": f"Success! {req.amount_npr} NPR sent to eSewa {req.wallet_phone}."}

@app.get("/api/v1/tag.js")
async def ad_tag_js(db: DBWrapper = Depends(get_db)):
    imp_id = f"IMP-WEB-{int(time.time()*1000)}"
    db.execute("INSERT INTO impressions (impression_id, publisher_id, timestamp) VALUES (?, 'pub_dev_773x92', 'now')", (imp_id,))
    db.commit()
    js = f"""(function(){{var d=document.createElement('div');d.style='background:#1e293b;color:#fff;padding:15px;border-radius:8px;text-align:center;font-family:sans-serif;border:1px solid #38bdf8;margin:10px 0;';d.innerHTML='<small style="color:#38bdf8">WORLDWIDE AD CENTER</small><h4 style="margin:5px 0">Premium Q4 APAC Push</h4><button onclick="fetch(\\'https://worldwide-ad-center-1.onrender.com/api/v1/simulate-click\\',{{method:\\'POST\\'}});alert(\\'Ad Click Recorded!\\')" style="background:#22c55e;border:none;padding:8px 14px;border-radius:4px;font-weight:bold;cursor:pointer">Learn More</button>';document.currentScript.parentNode.insertBefore(d,document.currentScript);}})();"""
    return Response(content=js, media_type="application/javascript")

@app.get("/tag-preview", response_class=HTMLResponse)
async def tag_preview():
    return """<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{font-family:sans-serif;background:#0f172a;color:#fff;padding:20px}code{display:block;background:#1e293b;padding:12px;border-radius:8px;color:#38bdf8;word-break:break-all;margin:15px 0}</style></head>
    <body><h2>Website Ad Tag (&lt;script&gt;)</h2><p>Paste this single line into any website HTML:</p><code>&lt;script src="https://worldwide-ad-center-1.onrender.com/api/v1/simulate-click"&gt;&lt;/script&gt;</code>
    <h3>Live Ad Preview:</h3><script src="/api/v1/tag.js"></script><br><a href="/" style="color:#94a3b8">Back to Hub</a></body></html>"""

@app.get("/api/v1/health/telegram-report")
async def health_report(db: DBWrapper = Depends(get_db)):
    imp = db.execute("SELECT COUNT(*) FROM impressions").fetchone()[0] or 0
    row = db.execute("SELECT COUNT(*), COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()
    report = f"📊 AD CENTER REPORT\n• Impressions: {imp}\n• Locked Clicks: {row[0]}\n• Available Escrow: {round(float(row[1]), 2)} NPR"
    st = send_telegram_alert(report)
    return {"status": st, "summary": report}
