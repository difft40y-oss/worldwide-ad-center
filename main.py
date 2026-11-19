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
    db.execute("CREATE TABLE IF NOT EXISTS saved_banners (draft_id TEXT PRIMARY KEY, headline TEXT, subtext TEXT, btn_text TEXT, target_url TEXT, img_data TEXT, expires_at INTEGER);")
    db.execute("CREATE TABLE IF NOT EXISTS tenders (tender_id TEXT PRIMARY KEY, title TEXT, issuer TEXT, province TEXT, category TEXT, deadline TEXT, contact_url TEXT, approved INTEGER);")
    db.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, default_wallet TEXT, cpc_rate REAL, qr_img TEXT);")
    try:
        db.execute("ALTER TABLE settings ADD COLUMN qr_img TEXT;")
    except Exception:
        pass
    if not db.execute("SELECT id FROM settings WHERE id=1").fetchone():
        db.execute("INSERT INTO settings (id, default_wallet, cpc_rate, qr_img) VALUES (1, '9717831225', 2.50, '');")
    db.execute("UPDATE settings SET default_wallet='9717831225' WHERE default_wallet='9703544008';")
    db.execute("CREATE TABLE IF NOT EXISTS tenders (tender_id TEXT PRIMARY KEY, title TEXT, issuer TEXT, category TEXT, deadline TEXT, contact_url TEXT, approved INTEGER);")
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

def render_nav(title: str, subpath: str) -> str:
    return f"""<div style="background:#1e293b;padding:12px 14px;border-radius:12px;border:1px solid #334155;margin-bottom:14px;position:relative;">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
        <a href="/" style="display:flex;align-items:center;gap:8px;text-decoration:none;color:#fff;">
            <span style="background:#0f172a;border:1px solid #38bdf8;padding:5px 9px;border-radius:9px;display:inline-flex;align-items:center;gap:7px;">
                <svg width="26" height="32" viewBox="0 0 60 74" xmlns="http://w3.org">
                    <polygon points="6,4 54,34 22,34 56,68 6,68" fill="#dc143c" stroke="#003893" stroke-width="5" stroke-linejoin="round"/>
                    <circle cx="19" cy="24" r="4.2" fill="#ffffff"/>
                    <circle cx="21" cy="52" r="5.5" fill="#ffffff"/>
                </svg>
                <span style="font-weight:900;font-size:16px;color:#ffffff;letter-spacing:1.2px;">WAC</span>
            </span>
            <div><div style="font-weight:bold;font-size:14px;line-height:1.1;letter-spacing:0.3px;">WORLDWIDE AD CENTER</div><div style="font-size:11px;color:#38bdf8;margin-top:2px;">{subpath} <span id="urlParam" style="color:#94a3b8;font-family:monospace;word-break:break-all;font-size:10px;"></span></div><script>document.getElementById("urlParam").innerText="("+window.location.href+")";</script></div>
        </a>
        <div style="position:relative;">
            <button onclick="var m=document.getElementById('dotMenu');m.style.display=m.style.display==='block'?'none':'block';" style="background:#0f172a;color:#fff;border:1px solid #475569;border-radius:8px;padding:6px 11px;font-size:16px;font-weight:bold;cursor:pointer;">&#8942;</button>
            <div id="dotMenu" style="display:none;position:absolute;right:0;top:38px;background:#0f172a;border:1px solid #475569;border-radius:10px;min-width:190px;z-index:999;box-shadow:0 8px 20px rgba(0,0,0,0.5);overflow:hidden;">
                <a href="/" style="display:block;padding:10px 14px;color:#fff;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#127968; Main Dashboard Hub</a>
                <a href="/simulate-app" style="display:block;padding:10px 14px;color:#cbd5e1;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128241; Mobile App Simulator</a>
                <a href="/payout-hub" style="display:block;padding:10px 14px;color:#f59e0b;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128184; eSewa Payouts &amp; History</a>
                <a href="/tag-preview" style="display:block;padding:10px 14px;color:#a855f7;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128187; Website Ad Tag (&lt;script&gt;)</a>
                <a href="/campaigns" style="display:block;padding:10px 14px;color:#ec4899;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128260; Rotating Ad Campaigns</a>
                <a href="/faq" style="display:block;padding:10px 14px;color:#cbd5e1;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#10067; FAQ &amp; Ad Topics</a>
                <a href="/about" style="display:block;padding:10px 14px;color:#cbd5e1;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#8505;&#65039; About &amp; Contact</a>
                <a href="/privacy" style="display:block;padding:10px 14px;color:#94a3b8;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128274; Privacy Policy</a>
                <a href="/terms" style="display:block;padding:10px 14px;color:#94a3b8;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128220; Terms of Service</a>
                <a href="/gallery" style="display:block;padding:10px 14px;color:#38bdf8;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#128444;&#65039; Ad Creative Gallery</a>
                <a href="/settings" style="display:block;padding:10px 14px;color:#22c55e;text-decoration:none;font-size:12px;border-bottom:1px solid #1e293b;">&#9881;&#65039; Settings</a>
                <a href="javascript:void(0)" onclick="if(window.history.length>1){{window.history.back();}}else{{window.location.href='/';}}" style="display:block;padding:11px 14px;background:#ffffff;color:#000000;font-weight:bold;text-decoration:none;font-size:12px;">&larr; Exit</a>
            </div>
        </div>
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:10px;padding-top:9px;border-top:1px solid #334155;">
        <a href="/" style="background:#0f172a;color:#e2e8f0;border:1px solid #475569;padding:5px 9px;border-radius:6px;font-size:11px;font-weight:bold;text-decoration:none;">Home</a>
        <a href="/tenders" style="background:#38bdf8;color:#0f172a;padding:5px 9px;border-radius:6px;font-size:11px;font-weight:bold;text-decoration:none;">Tenders &amp; Bids</a>
        <a href="/agencies" style="background:#f59e0b;color:#0f172a;padding:5px 9px;border-radius:6px;font-size:11px;font-weight:bold;text-decoration:none;">For Agencies</a>
        <a href="/advertise" style="background:#14b8a6;color:#0f172a;padding:5px 9px;border-radius:6px;font-size:11px;font-weight:bold;text-decoration:none;">Advertise</a>
    </div>
    <div style="font-size:12px;color:#94a3b8;margin-top:8px;">Section: <b style="color:#fff;">{title}</b></div>
</div>"""

FOOTER = '<div style="text-align:center;margin-top:24px;padding-top:14px;border-top:1px solid #334155;font-size:12px;color:#94a3b8;"><a href="/" style="color:#38bdf8;text-decoration:none;">Hub Home</a> &bull; <a href="/about" style="color:#38bdf8;text-decoration:none;">About &amp; Contact</a> &bull; <a href="/advertise" style="color:#38bdf8;text-decoration:none;">Advertise With Us</a> &bull; <a href="/agencies" style="color:#f59e0b;text-decoration:none;">For Agencies</a> &bull; <a href="/tenders" style="color:#38bdf8;text-decoration:none;">Tenders &amp; Bids</a> &bull; <a href="/faq" style="color:#38bdf8;text-decoration:none;">FAQ &amp; Ad Topics</a> &bull; <a href="/privacy" style="color:#38bdf8;text-decoration:none;">Privacy Policy</a> &bull; <a href="/terms" style="color:#38bdf8;text-decoration:none;">Terms of Service</a><br><span style="font-size:11px;color:#64748b;">&copy; 2026 Worldwide Ad Center &bull; Admin PIN Protected</span></div>'

@app.get("/", response_class=HTMLResponse)
async def root_hub(db: DBWrapper = Depends(get_db)):
    imp = db.execute("SELECT COUNT(*) FROM impressions").fetchone()[0] or 0
    row = db.execute("SELECT COUNT(*), COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()
    clk, earn = row[0], round(float(row[1]), 2)
    ctr = round((clk / imp * 100), 2) if imp > 0 else 0.0
    db_mode = "Cloud PostgreSQL (Permanent)" if db.is_pg else f"Local SQLite ({db.err or 'No DATABASE_URL'})"
    return f"""<!DOCTYPE html><html><head><title>Worldwide Ad Center</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>body{{font-family:sans-serif;background:#0f172a;color:#f8fafc;padding:20px;margin:0}}.card{{background:#1e293b;padding:18px;border-radius:12px;border:1px solid #334155;margin-bottom:15px}}.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}}.stat{{background:#0f172a;padding:12px;border-radius:8px;text-align:center;border:1px solid #475569}}.val{{font-size:22px;font-weight:bold;color:#22c55e}}.btn{{display:block;background:#38bdf8;color:#0f172a;text-align:center;padding:12px;border-radius:8px;font-weight:bold;text-decoration:none;margin-top:10px}}</style></head>
    <body>{render_nav("Main Control Hub", "Home / Dashboard")}<div class="card" style="padding:10px 14px;"><p style="color:#94a3b8;font-size:11px;margin:0;">Storage: <b>{db_mode}</b></p></div>
    <div class="card"><div class="grid"><div class="stat"><div>IMPRESSIONS</div><div class="val">{imp}</div></div><div class="stat"><div>LOCKED CLICKS</div><div class="val">{clk}</div></div><div class="stat"><div>CTR %</div><div class="val">{ctr}%</div></div><div class="stat"><div>AVAILABLE</div><div class="val">{earn} NPR</div></div></div>
    <a href="/simulate-app" class="btn">1. MOBILE APP AD SIMULATOR</a>
    <a href="/payout-hub" class="btn" style="background:#f59e0b;">2. ESEWA WITHDRAWAL &amp; HISTORY</a>
    <a href="/tag-preview" class="btn" style="background:#a855f7;color:#fff;">3. GET WEBSITE AD TAG (&lt;script&gt;)</a>
    <a href="/campaigns" class="btn" style="background:#ec4899;color:#fff;">4. MANAGE &amp; ROTATE AD CAMPAIGNS</a>
    <a href="/advertise" class="btn" style="background:#14b8a6;color:#0f172a;">5. ADVERTISE WITH US (SUBMIT AD)</a>
    <a href="/tenders" class="btn" style="background:#0ea5e9;color:#0f172a;">6. CONSTRUCTION &amp; BIDDER NOTICES</a>
    <a href="/api/v1/health/telegram-report" class="btn" style="background:#22c55e;">7. SEND TELEGRAM HEALTH REPORT</a></div>{FOOTER}</body></html>"""

@app.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(db: DBWrapper = Depends(get_db)):
    rows = db.execute("SELECT id, headline, subtext, btn_text, target_url FROM ad_campaigns ORDER BY id DESC").fetchall()
    items = "".join([f"<div style='background:#0f172a;padding:12px;border-radius:8px;margin-top:8px;border:1px solid #334155;'><b>#{r}: {r}</b><br><span style='font-size:12px;color:#cbd5e1'>{r}</span><br><small style='color:#38bdf8'>{r}</small></div>" for r in rows])
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#fff;padding:20px}}.box{{background:#1e293b;padding:20px;border-radius:12px;margin-bottom:15px}}input{{width:100%;padding:12px;margin:8px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#ec4899;color:#fff;border:none;border-radius:6px;font-weight:bold;margin-top:10px}}</style></head>
    <body>{render_nav("Manage & Rotate Campaigns", "Home / Campaigns")}<div class="box"><h2>Add New Rotating Ad Campaign</h2>
    <input id="hl" placeholder="Ad Headline"><input id="sub" placeholder="Short Description"><input id="btn" placeholder="Button Label (e.g. Visit Site)"><input id="url" placeholder="Destination URL (https://...)"><label style="font-size:12px;">Upload Official eSewa QR Screenshot (Optional, Max 500KB):</label><input type="file" accept="image/*" onchange="readQr(this)" style="font-size:12px;"><input id="pin" type="password" placeholder="Admin PIN (Default: 2026)">
    <button class="btn" onclick="addC()">ADD TO ROTATION</button><p id="res" style="color:#22c55e"></p></div>
    <div class="box"><h3>Active Rotating Ads ({len(rows)})</h3>{items}</div>{FOOTER}
    <script>async function addC(){{const r=await fetch('/api/v1/add-campaign',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{headline:document.getElementById('hl').value,subtext:document.getElementById('sub').value,btn_text:document.getElementById('btn').value,target_url:document.getElementById('url').value,pin:document.getElementById('pin').value}})}});const d=await r.json();document.getElementById('res').innerText=d.message||d.detail;}}</script></body></html>"""

@app.post("/api/v1/add-campaign")
async def add_campaign(req: CampaignReq, db: DBWrapper = Depends(get_db)):
    if req.pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Invalid Admin PIN.")
    nid = int(time.time()) % 1000000
    db.execute("INSERT INTO ad_campaigns (id, headline, subtext, btn_text, target_url, active) VALUES (?, ?, ?, ?, ?, 1)", (nid, req.headline, req.subtext, req.btn_text, req.target_url))
    db.commit()
    return {"message": "Campaign added to live rotation! Refresh page to see list."}

@app.get("/advertise", response_class=HTMLResponse)
async def advertise_portal(db: DBWrapper = Depends(get_db)):
    now = int(time.time())
    db.execute("DELETE FROM saved_banners WHERE expires_at < ?", (now,))
    db.commit()
    rows = db.execute("SELECT draft_id, headline, subtext, img_data, expires_at FROM saved_banners ORDER BY expires_at DESC LIMIT 8").fetchall()
    lib = ""
    for r in rows:
        did, hl, sub, img, exp = r
        hrs = max(1, int((exp - now) / 3600))
        im_tag = f'<img src="{img}" style="width:100%;max-height:80px;object-fit:cover;border-radius:5px;margin-bottom:5px;">' if img else ''
        lib += f'<div style="background:#0f172a;padding:10px;border-radius:8px;margin-top:8px;border:1px solid #334155;">{im_tag}<b>{hl}</b> <span style="color:#f59e0b;font-size:11px;">({hrs}h left)</span><br><small style="color:#94a3b8">{sub}</small><br><button onclick="ld(\'{did}\')" style="background:#38bdf8;border:none;padding:5px 10px;border-radius:4px;font-size:11px;font-weight:bold;margin-top:5px;">Load Draft</button></div>'
    if not lib:
        lib = '<p style="color:#94a3b8;font-size:12px;">No saved drafts yet.</p>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#fff;padding:18px}}.box{{background:#1e293b;padding:16px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}.tpl{{background:#0f172a;border:1px solid #14b8a6;color:#14b8a6;padding:6px 9px;border-radius:6px;font-size:11px;margin:3px}}input{{width:100%;padding:10px;margin:6px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:11px;background:#14b8a6;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:7px}}</style></head>
    <body>{render_nav("Advertiser Studio & 7-Day Library", "Home / Advertise With Us")}<div class="box"><h3 style="margin-top:0">Templates &amp; Live Preview</h3>
    <button class="tpl" onclick="tp('Flash Sale: 50% Off!','Limited-time deals across Nepal.','Shop Now')">E-Commerce</button>
    <button class="tpl" onclick="tp('Smart App Launch','Try free for 14 days today.','Download')">App Launch</button>
    <button class="tpl" onclick="tp('Local Service Offer','Trusted quality &amp; fast booking.','Book Now')">Local Offer</button>
    <div style="background:#0f172a;padding:12px;border-radius:8px;text-align:center;border:1px dashed #38bdf8;margin-top:10px;"><div id="pi"></div><h4 id="ph" style="margin:5px 0">Your Headline</h4><p id="ps" style="font-size:12px;color:#cbd5e1;margin:0 0 8px 0">Offer description</p><span id="pb" style="background:#22c55e;color:#0f172a;padding:5px 12px;border-radius:4px;font-size:12px;font-weight:bold">Learn More</span></div></div>
    <div class="box"><h3 style="margin-top:0">Banner Editor &amp; Attachment</h3>
    <input id="hl" oninput="sy()" placeholder="Headline"><input id="sub" oninput="sy()" placeholder="Description"><input id="btn" oninput="sy()" placeholder="Button Text"><input id="url" placeholder="Target URL (https://...)">
    <input type="file" accept="image/*" onchange="ri(this)" style="font-size:12px">
    <button class="btn" style="background:#38bdf8" onclick="sv()">SAVE TO 7-DAY LIBRARY</button>
    <button class="btn" onclick="sb()">SUBMIT FOR APPROVAL</button><p id="res" style="color:#22c55e;font-size:12px"></p></div>
    <div class="box"><h3 style="margin-top:0">7-Day Temporary Library</h3>{lib}</div>{FOOTER}
    <script>let im="";function sy(){{document.getElementById('ph').innerText=document.getElementById('hl').value||'Your Headline';document.getElementById('ps').innerText=document.getElementById('sub').value||'Offer description';document.getElementById('pb').innerText=document.getElementById('btn').value||'Learn More'}}
    function tp(h,s,b){{document.getElementById('hl').value=h;document.getElementById('sub').value=s;document.getElementById('btn').value=b;sy()}}
    function ri(i){{const f=i.files.item(0);if(!f)return;if(f.size>520000){{alert('Max 500KB');return}}const r=new FileReader();r.onload=e=>{{im=e.target.result;document.getElementById('pi').innerHTML='<img src="'+im+'" style="width:100%;max-height:90px;object-fit:cover;border-radius:5px">'}};r.readAsDataURL(f)}}
    async function sv(){{const r=await fetch('/api/v1/save-banner-draft',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{headline:document.getElementById('hl').value||'Draft',subtext:document.getElementById('sub').value,btn_text:document.getElementById('btn').value||'Learn More',target_url:document.getElementById('url').value,img_data:im}})}});const d=await r.json();document.getElementById('res').innerText=d.message;setTimeout(()=>location.reload(),900)}}
    async function ld(id){{const r=await fetch('/api/v1/load-banner-draft/'+id);const d=await r.json();document.getElementById('hl').value=d.headline;document.getElementById('sub').value=d.subtext;document.getElementById('btn').value=d.btn_text;document.getElementById('url').value=d.target_url;im=d.img_data||'';document.getElementById('pi').innerHTML=im?'<img src="'+im+'" style="width:100%;max-height:90px;object-fit:cover;border-radius:5px">':'';sy()}}
    async function sb(){{const r=await fetch('/api/v1/submit-advertiser',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{headline:document.getElementById('hl').value,subtext:document.getElementById('sub').value,btn_text:document.getElementById('btn').value,target_url:document.getElementById('url').value,img_data:im}})}});const d=await r.json();document.getElementById('res').innerText=d.message}}</script></body></html>"""

@app.post("/api/v1/save-banner-draft")
async def save_banner_draft(req: CampaignReq, db: DBWrapper = Depends(get_db)):
    db.execute("INSERT INTO saved_banners (draft_id, headline, subtext, btn_text, target_url, img_data, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (f"DRF-{int(time.time()*1000)}", req.headline, req.subtext, req.btn_text, req.target_url, req.img_data, int(time.time())+604800))
    db.commit()
    return {"message": "Saved to 7-day library!"}

@app.get("/api/v1/load-banner-draft/{did}")
async def load_banner_draft(did: str, db: DBWrapper = Depends(get_db)):
    r = db.execute("SELECT headline, subtext, btn_text, target_url, img_data FROM saved_banners WHERE draft_id=?", (did,)).fetchone()
    if not r: return {{}}
    hl, sub, btn, url, img = r
    return {"headline":hl,"subtext":sub,"btn_text":btn,"target_url":url,"img_data":img}

@app.post("/api/v1/submit-advertiser")
async def submit_advertiser(req: CampaignReq):
    send_telegram_alert(f"📢 New Advertiser Request!\n• Headline: {req.headline}\n• URL: {req.target_url}")
    return {"message": "Campaign submitted! Network admin notified via Telegram for approval."}

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
    <body>{render_nav("Website Ad Tag (<script>)", "Home / Website Ad Tag")}<h2>Website Ad Tag (&lt;script&gt;)</h2><p>Paste this single line into any website HTML:</p><code>&lt;script src="{base}/api/v1/tag.js"&gt;&lt;/script&gt;</code>
    <h3>Live Rotating Ad Preview:</h3><script src="/api/v1/tag.js"></script>{FOOTER}</body></html>"""




class AgencyReq(BaseModel):
    agency_name: str
    contact_info: str
    monthly_budget: str
    client_count: str


class TenderReq(BaseModel):
    title: str
    issuer: str
    category: str
    deadline: str
    contact_url: str
    pin: str = ""


class SettingsReq(BaseModel):
    default_wallet: str
    cpc_rate: float
    qr_img: str = ""
    pin: str

@app.get("/gallery", response_class=HTMLResponse)
async def gallery_page(db: DBWrapper = Depends(get_db)):
    camps = db.execute("SELECT id, headline, subtext, btn_text, target_url FROM ad_campaigns WHERE active=1 ORDER BY id DESC").fetchall()
    drafts = db.execute("SELECT headline, subtext, btn_text, img_data FROM saved_banners WHERE img_data != '' ORDER BY expires_at DESC LIMIT 8").fetchall()
    cards = ""
    for c in camps:
        cid, hl, sub, btn, url = c
        cards += f'<div style="background:#0f172a;padding:14px;border-radius:10px;text-align:center;border:1px solid #38bdf8;margin-top:10px;"><small style="color:#38bdf8;">LIVE CAMPAIGN #{cid}</small><h4 style="margin:6px 0;color:#fff;">{hl}</h4><p style="font-size:12px;color:#cbd5e1;margin:0 0 10px 0;">{sub}</p><a href="{url}" target="_blank" style="display:inline-block;background:#22c55e;color:#0f172a;padding:6px 14px;border-radius:5px;font-size:12px;font-weight:bold;text-decoration:none;">{btn}</a></div>'
    for d in drafts:
        hl, sub, btn, img = d
        cards += f'<div style="background:#0f172a;padding:14px;border-radius:10px;text-align:center;border:1px dashed #a855f7;margin-top:10px;"><img src="{img}" style="width:100%;max-height:120px;object-fit:cover;border-radius:6px;margin-bottom:8px;"><h4 style="margin:4px 0;color:#fff;">{hl}</h4><p style="font-size:12px;color:#cbd5e1;margin:0;">{sub}</p></div>'
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2{{color:#fff;margin-top:0}}</style></head>
    <body>{render_nav("Ad Creative Gallery", "Home / Gallery")}
    <div class="box"><h2>Ad Creative &amp; Visual Gallery</h2><p style="font-size:13px;margin-top:0;">Showcase of active sponsored banners and attached visual creatives across our network:</p>{cards}</div>{FOOTER}</body></html>"""

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(db: DBWrapper = Depends(get_db)):
    row = db.execute("SELECT default_wallet, cpc_rate FROM settings WHERE id=1").fetchone()
    wal, rate = row if row else ("9717831225", 2.50)
    db_st = "Connected (Cloud PostgreSQL)" if db.is_pg else "Local SQLite"
    tg_st = "Active (@WorldwideAdCenterNotificationBot)" if TELEGRAM_BOT_TOKEN else "Not Configured"
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}.row{{background:#0f172a;padding:10px 12px;border-radius:8px;margin-bottom:8px;border:1px solid #334155;font-size:12px}}input{{width:100%;padding:11px;margin:6px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#22c55e;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:8px;cursor:pointer}}</style></head>
    <body>{render_nav("Network Settings", "Home / Settings")}
    <div class="box"><h2>System Status &amp; Diagnostics</h2>
    <div class="row"><b>Database Storage:</b> <span style="color:#22c55e;">{db_st}</span></div>
    <div class="row"><b>Telegram Alert Bot:</b> <span style="color:#38bdf8;">{tg_st}</span></div>
    <div class="row"><b>Admin Security:</b> PIN Protected (Manage via Render <code>ADMIN_PIN</code>)</div></div>

    <div class="box"><h3>Payout &amp; Rate Configuration</h3>
    <label style="font-size:12px;">Default eSewa Wallet Number:</label><input id="wal" value="{wal}">
    <label style="font-size:12px;">Standard CPC Rate (NPR per Click):</label><input id="rt" type="number" step="0.1" value="{rate}">
    <label style="font-size:12px;">Upload Official eSewa QR Screenshot (Optional, Max 500KB):</label><input type="file" accept="image/*" onchange="readQr(this)" style="font-size:12px;"><input id="pin" type="password" placeholder="Admin PIN (Default: 2026)">
    <button class="btn" onclick="saveSet()">SAVE NETWORK SETTINGS</button>
    <p id="res" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}
    <script>let qrData="";function readQr(i){{const f=i.files.item(0);if(!f)return;if(f.size>520000){{alert('Max 500KB');return}}const r=new FileReader();r.onload=e=>{{qrData=e.target.result;}};r.readAsDataURL(f)}}
    async function saveSet(){{const r=await fetch('/api/v1/save-settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{default_wallet:document.getElementById('wal').value,cpc_rate:parseFloat(document.getElementById('rt').value),qr_img:qrData,pin:document.getElementById('pin').value}})}});const d=await r.json();document.getElementById('res').innerText=d.message||d.detail;}}</script></body></html>"""

@app.post("/api/v1/save-settings")
async def save_settings(req: SettingsReq, db: DBWrapper = Depends(get_db)):
    if req.pin != ADMIN_PIN:
        raise HTTPException(status_code=403, detail="Invalid Admin PIN.")
    if req.qr_img:
        db.execute("UPDATE settings SET default_wallet=?, cpc_rate=?, qr_img=? WHERE id=1", (req.default_wallet, req.cpc_rate, req.qr_img))
    else:
        db.execute("UPDATE settings SET default_wallet=?, cpc_rate=? WHERE id=1", (req.default_wallet, req.cpc_rate))
    db.commit()
    return {"message": "Network settings saved to Cloud PostgreSQL!"}

@app.get("/tenders", response_class=HTMLResponse)
async def tenders_portal(db: DBWrapper = Depends(get_db)):
    rows = db.execute("SELECT tender_id, title, issuer, category, deadline, contact_url FROM tenders WHERE approved=1 ORDER BY tender_id DESC LIMIT 20").fetchall()
    cards = ""
    for r in rows:
        tid, ttl, iss, cat, ddl, curl = r
        cards += f'<div style="background:#0f172a;padding:13px;border-radius:8px;margin-top:10px;border-left:4px solid #38bdf8;"><div style="display:flex;justify-content:space-between;align-items:center;"><span style="background:#1e293b;color:#38bdf8;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:bold;">{cat}</span><span style="color:#f59e0b;font-size:11px;">Deadline: {ddl}</span></div><h4 style="margin:8px 0 4px 0;color:#fff;">{ttl}</h4><p style="margin:0 0 8px 0;font-size:12px;color:#94a3b8;">Issued by: <b>{iss}</b> &bull; ID: {tid}</p><a href="{curl}" target="_blank" style="display:inline-block;background:#22c55e;color:#0f172a;padding:6px 12px;border-radius:5px;font-size:12px;font-weight:bold;text-decoration:none;">View Bid / Contact</a></div>'
    if not cards:
        cards = '<p style="color:#94a3b8;font-size:12px;">No active construction notices yet. Publish the first Invitation for Bid (IFB) or Contractor Notice below!</p>'

    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}input,select{{width:100%;padding:11px;margin:6px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#38bdf8;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:8px;cursor:pointer}}</style></head>
    <body>
    <div class="box"><span style="background:#38bdf8;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:bold;">INFRASTRUCTURE &amp; PROCUREMENT</span>
    <h2 style="margin:8px 0 6px 0;">Construction &amp; Bidder Notices</h2>
    <p style="font-size:13px;margin:0;">Active Invitation for Bids (IFB), Sealed Quotations, Subcontractor Calls &amp; Material Supply Tenders:</p>
    {cards}</div>

    <div class="box"><h3>Publish Construction / Bidder Notice</h3>
    <p style="font-size:12px;margin-top:0;">Submit a notice for admin review, or enter your <b>Admin PIN</b> to publish immediately:</p>
    <input id="ttl" placeholder="Project / Notice Title (e.g. Road Blacktopping &amp; Drainage IFB)">
    <input id="iss" placeholder="Issuing Office / Contractor Name">
    <select id="cat"><option>Civil &amp; Road Construction</option><option>Building &amp; Structural Works</option><option>Sealed Quotation / Supply</option><option>Subcontractor &amp; Heavy Equipment</option><option>Consultancy &amp; Engineering</option></select>
    <input id="ddl" placeholder="Bid Deadline (e.g. 2026-12-05, 12:00 PM)">
    <input id="url" placeholder="Notice Link, Phone, or Email (https://... or tel:...)">
    <input id="pin" type="password" placeholder="Admin PIN (Optional - leave blank for review)">
    <button class="btn" onclick="postTender()">SUBMIT / PUBLISH BIDDER NOTICE</button>
    <p id="res" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}

    <script>
    async function postTender(){{
        const r = await fetch('/api/v1/submit-tender',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{title:document.getElementById('ttl').value,issuer:document.getElementById('iss').value,category:document.getElementById('cat').value,deadline:document.getElementById('ddl').value,contact_url:document.getElementById('url').value,pin:document.getElementById('pin').value}})}});
        const d = await r.json(); document.getElementById('res').innerText = d.message || d.detail;
        if(d.published) setTimeout(()=>location.reload(), 1000);
    }}
    </script></body></html>"""

@app.post("/api/v1/submit-tender")
async def submit_tender(req: TenderReq, db: DBWrapper = Depends(get_db)):
    tid = f"BID-{int(time.time()) % 1000000}"
    is_admin = (req.pin == ADMIN_PIN and req.pin != "")
    approved = 1 if is_admin else 0
    db.execute("INSERT INTO tenders (tender_id, title, issuer, category, deadline, contact_url, approved) VALUES (?, ?, ?, ?, ?, ?, ?)", (tid, req.title, req.issuer, req.category, req.deadline, req.contact_url, approved))
    db.commit()
    st_txt = "PUBLISHED LIVE" if is_admin else "PENDING REVIEW"
    send_telegram_alert(f"🏗️ CONSTRUCTION / BIDDER NOTICE ({st_txt})!\n• ID: {tid}\n• Title: {req.title}\n• Issuer: {req.issuer}\n• Category: {req.category}\n• Deadline: {req.deadline}\n• Contact: {req.contact_url}")
    if is_admin:
        return {"message": f"Notice {tid} published live on the Bidder Board!", "published": True}
    return {"message": f"Notice {tid} submitted! Admin notified via Telegram for approval.", "published": False}

@app.get("/agencies", response_class=HTMLResponse)
async def agencies_portal():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:18px;line-height:1.5}}.box{{background:#1e293b;padding:18px;border-radius:12px;margin-bottom:14px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}.tier{{background:#0f172a;padding:11px;border-radius:8px;margin-top:8px;border-left:3px solid #f59e0b;font-size:13px}}input{{width:100%;padding:11px;margin:6px 0;border-radius:6px;border:1px solid #475569;background:#0f172a;color:#fff;box-sizing:border-box}}.btn{{width:100%;padding:12px;background:#f59e0b;color:#0f172a;border:none;border-radius:6px;font-weight:bold;margin-top:8px;cursor:pointer}}.stat{{background:#0f172a;padding:10px;border-radius:8px;text-align:center;border:1px solid #38bdf8;margin-top:10px}}</style></head>
    <body>{render_nav("Agency Partner Program", "Home / For Agencies")}
    <div class="box"><span style="background:#f59e0b;color:#0f172a;padding:3px 8px;border-radius:4px;font-size:11px;font-weight:bold;">AGENCY PARTNER PROGRAM</span>
    <h2 style="margin:8px 0 6px 0;">Agency Media Kit &amp; Rate Card</h2>
    <p style="font-size:13px;margin:0 0 10px 0;">Scale your clients across Nepal &amp; global web publishers with transparent CPC pricing, zero cookie friction, and priority Telegram campaign support.</p>
    <div class="tier"><b>Standard Agency Rate:</b> 2.50 NPR / Verified Click (Free Unlimited Impressions)</div>
    <div class="tier"><b>Growth Tier (25,000+ NPR/mo):</b> 10% Bonus Click Credits + Priority Ad Rotation</div>
    <div class="tier"><b>Enterprise Tier (100,000+ NPR/mo):</b> 20% Bonus Credits + Dedicated Multi-Brand Account</div>
    <div class="tier"><b>Ad Specs &amp; Formats:</b> Responsive Native Card, 300x250 / 728x90 Banner + Optional Creative Attachment (JPG/PNG/WEBP)</div></div>

    <div class="box"><h3>Live Budget &amp; ROI Estimator</h3>
    <p style="font-size:12px;margin-top:0;">Enter your client campaign budget in NPR to calculate guaranteed clicks &amp; estimated reach:</p>
    <input id="bud" type="number" value="10000" oninput="calc()" placeholder="Campaign Budget (NPR)">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div class="stat"><small style="color:#94a3b8;">VERIFIED CLICKS</small><div id="clk" style="font-size:20px;font-weight:bold;color:#22c55e;">4,000</div></div>
        <div class="stat"><small style="color:#94a3b8;">EST. IMPRESSIONS</small><div id="imp" style="font-size:20px;font-weight:bold;color:#38bdf8;">80,000+</div></div>
    </div></div>

    <div class="box"><h3>Agency Partner Fast-Track Request</h3>
    <p style="font-size:12px;margin-top:0;">Apply for priority multi-client onboarding. Our network desk responds directly via Telegram/WhatsApp:</p>
    <input id="ag" placeholder="Agency / Company Name">
    <input id="ct" placeholder="WhatsApp, Telegram, or Email Contact">
    <input id="mb" placeholder="Estimated Monthly Client Spend (e.g. 50,000 NPR)">
    <input id="cc" placeholder="Number of Active Client Brands (e.g. 5 Brands)">
    <button class="btn" onclick="sendAg()">REQUEST AGENCY PARTNER ACCESS</button>
    <p id="res" style="color:#22c55e;font-size:13px;"></p></div>{FOOTER}

    <script>
    function calc(){{
        const b = parseFloat(document.getElementById('bud').value) || 0;
        let bonus = b >= 100000 ? 1.20 : (b >= 25000 ? 1.10 : 1.0);
        const clicks = Math.floor((b / 2.50) * bonus);
        document.getElementById('clk').innerText = clicks.toLocaleString();
        document.getElementById('imp').innerText = (clicks * 20).toLocaleString() + "+";
    }}
    async function sendAg(){{
        const r = await fetch('/api/v1/agency-fast-track',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{agency_name:document.getElementById('ag').value,contact_info:document.getElementById('ct').value,monthly_budget:document.getElementById('mb').value,client_count:document.getElementById('cc').value}})}});
        const d = await r.json(); document.getElementById('res').innerText = d.message;
    }}
    </script></body></html>"""

@app.post("/api/v1/agency-fast-track")
async def agency_fast_track(req: AgencyReq):
    send_telegram_alert(f"🏢 PRIORITY AGENCY INQUIRY!\n• Agency: {req.agency_name}\n• Contact: {req.contact_info}\n• Monthly Budget: {req.monthly_budget}\n• Client Brands: {req.client_count}")
    return {"message": "Fast-track request received! Our Agency Desk has been alerted via Telegram."}

@app.get("/about", response_class=HTMLResponse)
async def about_page(db: DBWrapper = Depends(get_db)):
    row = db.execute("SELECT default_wallet, qr_img FROM settings WHERE id=1").fetchone()
    wal = row.__getitem__(0) if row else "9717831225"
    qimg = row.__getitem__(1) if (row and len(row) > 1 and row.__getitem__(1)) else ""
    qr_payload = urllib.parse.quote(f'{{"eSewa_id":"{wal}","name":"Worldwide Ad Center"}}')
    qr_src = qimg if qimg else f"https://qrserver.com{qr_payload}"
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:20px;line-height:1.6}}.box{{background:#1e293b;padding:20px;border-radius:12px;margin-bottom:15px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}.row{{background:#0f172a;padding:12px;border-radius:8px;margin-bottom:10px;border:1px solid #334155;font-size:13px}}.btn{{display:block;background:#38bdf8;color:#0f172a;text-align:center;padding:12px;border-radius:8px;font-weight:bold;text-decoration:none;margin-top:12px}}</style></head>
    <body>{render_nav("About & Contact Support", "Home / About Us")}
    <div class="box"><h2>About Worldwide Ad Center</h2>
    <p><b>Worldwide Ad Center</b> is an independent, performance-driven digital advertising network built to connect businesses directly with quality blogs, news portals, and mobile apps—without middleman fees or invasive tracking cookies.</p>
    <p>Our lightweight <code>&lt;script&gt;</code> tag empowers publishers in Nepal and worldwide to monetize their traffic transparently at <b>2.50 NPR per verified human click</b> with fast mobile wallet settlements.</p></div>

    <div class="box"><h3>Contact &amp; Advertiser Support</h3>
    <p style="font-size:13px;">Have questions about launching an ad campaign, publisher integration, or eSewa payouts? Reach our network team directly:</p>
    <div class="row"><b>Official Telegram Bot:</b> <a href="https://t.me" target="_blank" style="color:#38bdf8;text-decoration:none;">@WorldwideAdCenterNotificationBot</a></div>
    <div class="row"><b>Support Desk / Inquiries:</b> <a href="mailto:difft40y@gmail.com" style="color:#38bdf8;text-decoration:none;">difft40y@gmail.com</a></div>
    <div class="row"><b>Direct Phone / WhatsApp (eSewa):</b> +977-9717831225</div>
    <div class="row"><b>Payout Settlement Gateway:</b> eSewa Verified Merchant Support (Nepal)</div>
    <div class="row"><b>Operating Region:</b> Gandaki Province, Nepal &bull; Serving Global Web Traffic</div>
    <div style="background:#0f172a;padding:16px;border-radius:10px;text-align:center;border:1px solid #22c55e;margin:14px 0;">
        <span style="background:#22c55e;color:#0f172a;padding:3px 9px;border-radius:4px;font-size:11px;font-weight:bold;">INSTANT ESEWA PAYMENT QR</span>
        <div style="background:#ffffff;padding:10px;border-radius:10px;display:inline-block;margin:12px auto;">
            <img src="{qr_src}" alt="eSewa QR" style="width:170px;height:170px;display:block;">
        </div>
        <div style="font-size:13px;color:#fff;font-weight:bold;">eSewa ID: {wal}</div>
        <p style="font-size:11px;color:#94a3b8;margin:4px 0 10px 0;">Scan via eSewa App or copy ID to deposit campaign funds</p>
        <button onclick="navigator.clipboard.writeText('{wal}');this.innerText='Copied: {wal}';" style="background:#22c55e;color:#0f172a;border:none;padding:7px 14px;border-radius:6px;font-size:12px;font-weight:bold;cursor:pointer;">Copy eSewa ID ({wal})</button>
    </div>
    <a href="https://t.me" target="_blank" class="btn">MESSAGE US ON TELEGRAM</a>
    <a href="/advertise" class="btn" style="background:#14b8a6;">SUBMIT AN AD CAMPAIGN</a></div>
    {FOOTER}</body></html>"""

@app.get("/faq", response_class=HTMLResponse)
async def faq_page():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:20px;line-height:1.6}}.box{{background:#1e293b;padding:20px;border-radius:12px;margin-bottom:15px;border:1px solid #334155}}h2,h3{{color:#fff;margin-top:0}}.q{{color:#38bdf8;font-weight:bold;margin-top:14px}}.tag{{display:inline-block;background:#0f172a;border:1px solid #14b8a6;color:#14b8a6;padding:4px 10px;border-radius:20px;font-size:12px;margin:4px 4px 0 0}}.ban{{border-color:#ef4444;color:#ef4444}}</style></head>
    <body>{render_nav("Help Center & Ad Topics", "Home / FAQ & Guidelines")}
    <div class="box"><h2>Help Center &amp; Frequently Asked Questions</h2>
    <div class="q">1. How much does advertising cost?</div>
    <p>Advertisers pay a flat, transparent rate of <b>2.50 NPR per verified human click</b>. Impressions are served free across our partner publisher network.</p>
    <div class="q">2. How fast is my ad campaign approved?</div>
    <p>As soon as you submit your campaign on the <a href="/advertise" style="color:#14b8a6;">Advertise With Us</a> page, our admin team receives an instant Telegram alert and reviews your link within a few hours.</p>
    <div class="q">3. How do website owners earn money?</div>
    <p>Bloggers and website owners simply copy our single <code>&lt;script&gt;</code> tag from the hub and paste it into their HTML, Blogger, or WordPress site. Every verified click credits <b>+2.50 NPR</b> to escrow, payable directly to your <b>eSewa mobile wallet</b>.</p>
    <div class="q">4. How does your anti-fraud protection work?</div>
    <p>Our network filters duplicate refreshes and automated bot clicks so advertisers only pay for genuine human interest.</p></div>

    <div class="box"><h3>Supported &amp; Prohibited Ad Topics</h3>
    <p style="font-size:13px;">To keep our publisher websites family-friendly and brand-safe, all ads must follow our content guidelines:</p>
    <p style="margin-bottom:6px;color:#fff;font-size:13px;"><b>Allowed Topics:</b></p>
    <span class="tag">E-Commerce &amp; Retail</span><span class="tag">Tech &amp; Mobile Apps</span><span class="tag">Education &amp; Courses</span><span class="tag">Local Nepal Businesses</span><span class="tag">Finance &amp; SaaS</span><span class="tag">Blogs &amp; Media</span>
    <p style="margin:14px 0 6px 0;color:#fff;font-size:13px;"><b>Strictly Prohibited Topics:</b></p>
    <span class="tag ban">Adult / Explicit Content</span><span class="tag ban">Gambling &amp; Betting</span><span class="tag ban">Malware / Fake Downloads</span><span class="tag ban">Illegal Products</span><span class="tag ban">Click-Fraud Schemes</span></div>
    {FOOTER}</body></html>"""

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:20px;line-height:1.6}}.box{{background:#1e293b;padding:20px;border-radius:12px}}h2,h3{{color:#fff}}</style></head>
    <body>{render_nav("Privacy Policy", "Home / Legal / Privacy Policy")}<div class="box"><h2>Privacy Policy</h2><p><b>Effective Date:</b> November 2026</p><h3>1. Cookie-Free Ad Delivery</h3><p>Worldwide Ad Center delivers contextual advertisements without storing third-party tracking cookies on visitor browsers.</p><h3>2. Impression &amp; Click Logging</h3><p>We log anonymized impression counts, verified click events, and basic anti-fraud rate limits solely to calculate publisher earnings and prevent automated bot traffic.</p><h3>3. Publisher Payout Data</h3><p>Registered mobile wallet numbers (such as eSewa IDs) are used strictly for processing requested publisher settlements.</p></div>{FOOTER}</body></html>"""

@app.get("/terms", response_class=HTMLResponse)
async def terms_of_service():
    return f"""<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><style>body{{font-family:sans-serif;background:#0f172a;color:#cbd5e1;padding:20px;line-height:1.6}}.box{{background:#1e293b;padding:20px;border-radius:12px}}h2,h3{{color:#fff}}</style></head>
    <body>{render_nav("Terms of Service", "Home / Legal / Terms of Service")}<div class="box"><h2>Terms of Service</h2><h3>1. Publisher Guidelines</h3><p>Publishers embedding the Worldwide Ad Center script tag must not generate artificial clicks, automated refreshes, or incentivized click fraud.</p><h3>2. Escrow &amp; Settlements</h3><p>Verified clicks accrue in locked escrow and become eligible for settlement via supported mobile wallets upon admin verification.</p></div>{FOOTER}</body></html>"""

@app.get("/api/v1/health/telegram-report")
async def health_report(db: DBWrapper = Depends(get_db)):
    imp = db.execute("SELECT COUNT(*) FROM impressions").fetchone() or 0
    row = db.execute("SELECT COUNT(*), COALESCE(SUM(payout_credited_npr), 0) FROM clicks WHERE escrow_status='locked'").fetchone()
    report = f"📊 AD CENTER REPORT\n• Impressions: {imp}\n• Locked Clicks: {row}\n• Available Escrow: {round(float(row), 2)} NPR"
    st = send_telegram_alert(report)
    return {"status": st, "summary": report}
