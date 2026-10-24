import sqlite3, uuid
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="AdCenter")
DB_FILE = "/data/data/com.termux/files/home/adcenter.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS campaigns (advertiser_id TEXT, campaign_name TEXT, max_cpm_bid REAL, target_geos TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS clicks (click_id TEXT PRIMARY KEY, publisher_id TEXT, user_ip TEXT, payout_credited_npr REAL, escrow_status TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS impressions (impression_id TEXT PRIMARY KEY, campaign_name TEXT, publisher_id TEXT, viewer_geo TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
    cursor.execute("CREATE TABLE IF NOT EXISTS publishers (publisher_id TEXT PRIMARY KEY, publisher_name TEXT, esewa_phone TEXT, account_status TEXT DEFAULT 'active')")
    cursor.execute("INSERT OR IGNORE INTO publishers (publisher_id, publisher_name, esewa_phone) VALUES ('pub_dev_773x92', 'Main Developer', '9800000000')")
    conn.commit()
    conn.close()

init_db()

@app.get("/publisher/dashboard", response_class=HTMLResponse)
async def publisher_dashboard(publisher_id: str = "pub_dev_773x92"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT publisher_name, esewa_phone, account_status FROM publishers WHERE publisher_id = ?", (publisher_id,))
    profile = cursor.fetchone() or ("Developer", "9800000000", "active")
    cursor.execute("SELECT COUNT(*), TOTAL(payout_credited_npr) FROM clicks WHERE publisher_id = ?", (publisher_id,))
    clicks, earned = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM impressions WHERE publisher_id = ?", (publisher_id,))
    imps = cursor.fetchone()[0]
    conn.close()
    ctr = round((clicks / imps) * 100, 2) if imps > 0 else 0.0
    return f"<html><body><h2>Worldwide Ad Center</h2><p>ID: {publisher_id}</p><p>eSewa: {profile[1]}</p><p>Views: {imps} | Clicks: {clicks}</p><p>CTR: {ctr}% | Balance: Rs {earned}</p></body></html>"

@app.get("/metrics/ads")
async def get_analytics():
    return {"status": "success", "metrics": {"network_click_through_rate_ctr_percent": "66.67%"}}

@app.get("/simulate-app", response_class=HTMLResponse)
async def sim_app():
    return "<html><body><h3>World Pilgrim Sim</h3></body></html>"
