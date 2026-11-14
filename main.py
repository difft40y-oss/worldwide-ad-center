from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
import sqlite3, os, time, random, urllib.request, urllib.parse

app = FastAPI()
DB_PATH = os.path.join(os.path.expanduser("~"), "adcenter.db")
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("INTERNAL_DATABASE_URL") or ""
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ADMIN_PIN = os.getenv("ADMIN_PIN", "2026")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

class DBWrapper:
    def __init__(self):
        self.err = ""
        if DATABASE_URL:
            try:
                import psycopg2
                self.conn = psycopg2.connect(DATABASE_URL)
                self.is_pg = True
                return
            except Exception as e:
                self.err = str(e)
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
    db.execute("CREATE TABLE IF NOT EXISTS ad_campaigns (id INTEGER PRIMARY KEY, headline TEXT, subtext TEXT, btn_text TEXT, target_url TEXT, active INTEGER);")
    db.execute("CREATE TABLE IF NOT EXISTS payouts (payout_id TEXT PRIMARY KEY, wallet_phone TEXT, amount_npr REAL, status TEXT, created_at TEXT);")
    if not db.execute("SELECT id FROM ad_campaigns WHERE id=1").fetchone():
        db.execute("INSERT INTO ad_campaigns (id, headline, subtext, btn_text, target_url, active) VALUES (1, 'Worldwide Ad Center Network', 'Monetize your website traffic with instant eSewa payouts.', 'Join Now', 'https://worldwide-ad-center-1.onrender.com', 1);")
    db.commit()
    db.close()

init_db()

def send_telegram_alert(message: str) -> str:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return "telegram_offline"
    url = "https://" + "api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID, "text": message}).encode("utf-8")
    try:
        urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=8)
        return "OK"
    except Exception as e:
        return str(e)

FOOTER = '<div style="text-align:center;margin-top:24px;padding-top:14px;border-top:1px solid #334155;font-size:12px;color:#94a3b8;"><a href="/" style="color:#38bdf8;text-decoration:none;">Hub Home</a> &bull; <a href="/advertise" style="color:#38bdf8;text-decoration:none;">Advertise With Us</a> &bull; <a href="/privacy" style="color:#38bdf8;text-decoration:none;">Privacy Policy</a> &bull; <a href="/terms" style="color:#38bdf8;text-decoration:none;">Terms of Service</a><br><span style="font-size:11px;color:#64748b;">&copy; 2026 Worldwide Ad Center &bull; Admin PIN Protected</span></div>'

@app.get("/", response_class=HTMLResponse)
async def root_hub(db: DBWrapper = Depends(get_db)):
    imp = db.execute("SELECT COUNT(*) FROM impressions").fetchone()[0] or 0
    row = db.execute("SELECT COUNT(*), COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()
    clk, earn = row[0], round(float(row[1]), 2)
    ctr = round((clk / imp * 100), 2) if imp > 0 else 0.0
    db_mode = "Cloud PostgreSQL (Permanent)" if db.is_pg else f"Local SQLite ({db.err or 'No DATABASE_URL'})"
    return f"""<!DOCTYPE html><html><head><title>Worldwide Ad Center</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body{{font-family:sans-serif;background:#0f172a;color:#f8fafc;padding:20px;margin:0}}.card{{background:#1e293b;padding:18px;border-radius:12px;border:1px solid #334155;margin-bottom:15px}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.stat{{background:#0f172a;padding:12px;border-radius:8px;text-align:center;border:1px solid #475569}}.val{{font-size:22px;font-weight:bold;color:#22c55e}}.btn{{display:block;background:#38bdf8;color:#0f172a;text-align:center;padding:12px;border-radius:8px;font-weight:bold;text-decoration:none;margin-top:10px}}</style></head>
    <body><div class="card"><h2 style="margin:0 0 5px 0;">Worldwide Ad Center Hub</h2><p style="color:#94a3b8;font-size:12px;margin:0;">Storage: <b>{db_mode}</b></p></div>
    <div class="card"><div class="grid"><div class="stat"><div>IMPRESSIONS</div><div class="val">{imp}</div></div><div class="stat"><div>LOCKED CLICKS</div><div class="val">{clk}</div></div><div class="stat"><div>CTR %</div><div class="val">{ctr}%</div></div><div class="stat"><div>AVAILABLE</div><div class="val">{earn} NPR</div></div></div>
    <a href="/simulate-app" class="btn">1. MOBILE APP AD SIMULATOR</a>
    <a href="/payout-hub" class="btn" style="background:#f59e0b;">2. ESEWA WITHDRAWAL &amp; HISTORY</a>
    <a href="/tag-preview" class="btn" style="background:#a855f7;color:#fff;">3. GET WEBSITE AD TAG (&lt;script&gt;)</a>
    <a href="/campaigns" class="btn" style="background:#ec4899;color:#fff;">4. MANAGE &amp; ROTATE AD CAMPAIGNS</a>
    <a href="/advertise" class="btn" style="background:#14b8a6;color:#0f172a;">5. ADVERTISER SUBMISSION PORTAL</a>
    <a href="/api/v1/health/telegram-report" class="btn" style="background:#22c55e;">6. SEND TELEGRAM HEALTH REPORT</a></div>{FOOTER}</body></html>"""
@app.get("/api/v1/tag.js")
async def ad_tag_js(db: DBWrapper = Depends(get_db)):
    imp_id = f"IMP-WEB-{int(time.time()*1000)}"
    db.execute("INSERT INTO impressions (impression_id, publisher_id, timestamp) VALUES (?, 'pub_dev_773x92', 'now')", (imp_id,))
    db.commit()
    rows = db.execute("SELECT headline, subtext, btn_text, target_url FROM ad_campaigns WHERE active=1").fetchall()
    hl, sub, btn, url = random.choice(rows) if rows else ("Worldwide Ad Center", "Grow your reach today.", "Learn More", "https://onrender.com")
    base = "https://" + "worldwide-ad-center-1" + ".onrender.com"
    js = f"""(function(){{var d=document.createElement('div');d.style='background:#1e293b;color:#fff;padding:16px;border-radius:10px;text-align:center;font-family:sans-serif;border:1px solid #38bdf8;margin:12px 0;';d.innerHTML='<small style="color:#38bdf8;letter-spacing:1px;">SPONSORED &bull; <a href="{base}/privacy" target="_blank" style="color:#94a3b8;text-decoration:none;">Ad Privacy</a></small><h4 style="margin:6px 0;font-size:18px;">{hl}</h4><p style="margin:0 0 12px 0;font-size:13px;color:#cbd5e1;">{sub}</p><button onclick="fetch(\\'{base}/api/v1/simulate-click\\',{{method:\\'POST\\'}});window.open(\\'{url}\\',\\'_blank\\');" style="background:#22c55e;color:#0f172a;border:none;padding:9px 18px;border-radius:6px;font-weight:bold;cursor:pointer;">{btn}</button>';document.currentScript.parentNode.insertBefore(d,document.currentScript);}})();"""
    return Response(content=js, media_type="application/javascript")

@app.get("/tag-preview", response_class=HTMLResponse)
async def tag_preview():
    base = "https://" + "worldwide-ad-center-1" + ".onrender.com"
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#fff;padding:20px}}code{{display:block;background:#1e293b;padding:12px;border-radius:8px;color:#38bdf8;word-break:break-all;margin:15px 0}}</style></head>
    <body><h2>Website Ad Tag (&lt;script&gt;)</h2><p>Paste this single line into any website HTML:</p><code>&lt;script src="{base}/api/v1/tag.js"&gt;&lt;/script&gt;</code>
    <h3>Live Rotating Ad Preview:</h3><script src="/api/v1/tag.js"></script>{FOOTER}</body></html>"""

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:20px;line-height:1.6}}.box{{background:#1e293b;padding:20px;border-radius:12px}}h2,h3{{color:#fff}}</style></head>
    <body><div class="box"><h2>Privacy Policy</h2><p><b>Effective Date:</b> November 2026</p><h3>1. Cookie-Free Ad Delivery</h3><p>Worldwide Ad Center delivers contextual advertisements without storing third-party tracking cookies on visitor browsers.</p><h3>2. Impression &amp; Click Logging</h3><p>We log anonymized impression counts, verified click events, and basic anti-fraud rate limits solely to calculate publisher earnings and prevent automated bot traffic.</p><h3>3. Publisher Payout Data</h3><p>Registered mobile wallet numbers (such as eSewa IDs) are used strictly for processing requested publisher settlements.</p></div>{FOOTER}</body></html>"""

@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:20px;line-height:1.6}}.box{{background:#1e293b;padding:20px;border-radius:12px}}h2,h3{{color:#fff}}</style></head>
    <body><div class="box"><h2>Terms of Service</h2><h3>1. Publisher Guidelines</h3><p>Publishers embedding the Worldwide Ad Center script tag must not generate artificial clicks, automated refreshes, or incentivized click fraud.</p><h3>2. Escrow &amp; Settlements</h3><p>Verified clicks accrue in locked escrow and become eligible for settlement via supported mobile wallets upon admin verification.</p></div>{FOOTER}</body></html>"""

@app.get("/api/v1/health/telegram-report")
async def health_report(db: DBWrapper = Depends(get_db)):
    imp = db.execute("SELECT COUNT(*) FROM impressions").fetchone() or 0
    row = db.execute("SELECT COUNT(*), COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()
    report = f"📊 AD CENTER REPORT\n• Impressions: {imp}\n• Locked Clicks: {row}\n• Available Escrow: {round(float(row), 2)} NPR"
    st = send_telegram_alert(report)
    return {"status": st, "summary": report}
