import sqlite3
from enum import Enum
from typing import Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="Worldwide Advertisement Center - Professional Master Engine")

# --- Initialize Local Database Instantly ---
def init_local_database():
    connection = sqlite3.connect("simulated_cloud.db")
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ads_master (
            ad_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            tenant_tier TEXT NOT NULL,
            metadata TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.commit()
    connection.close()

init_local_database()

# --- Schemas ---
class AdCategory(str, Enum):
    product_launch = "Product Launch"
    job_board = "Job Board"
    event = "Event"
    game = "Game"

class AccountTierStatus(str, Enum):
    paid_premium = "PaidPremium"
    trial_active = "TrialActive"
    trial_expired = "TrialExpired"

class AdCreationPayload(BaseModel):
    user_id: UUID
    tenant_tier: AccountTierStatus
    category: AdCategory
    title: str = Field(..., max_length=150)
    metadata: Dict[str, Any]
    media_url_raw: str

@app.post("/api/v1/ads/create-verified", status_code=status.HTTP_201_CREATED)
async def create_verified_advertisement(payload: AdCreationPayload):
    # 1. Enforce multi-tenant subscription check guard rails
    if payload.tenant_tier == AccountTierStatus.trial_expired:
        raise HTTPException(
            status_code=402, 
            detail=f"Blocked: Account status '{payload.tenant_tier.value}' requires premium wallet activation."
        )

    generated_ad_id = str(uuid4())
    
    # 2. Insert records natively into your local device database storage file
    try:
        connection = sqlite3.connect("simulated_cloud.db")
        cursor = connection.cursor()
        import json
        cursor.execute(
            "INSERT INTO ads_master (ad_id, title, category, tenant_tier, metadata) VALUES (?, ?, ?, ?, ?)",
            (generated_ad_id, payload.title, payload.category.value, payload.tenant_tier.value, json.dumps(payload.metadata))
        )
        connection.commit()
        connection.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database write fault: {str(e)}")
        
    return {
        "ad_id": generated_ad_id,
        "processing_status": "Provisioned & Saved to Local DB",
        "category": payload.category,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/", response_class=HTMLResponse)
async def serve_mobile_dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>WAC Professional Core</title>
        <style>
            body { font-family: sans-serif; background: #121212; color: #e0e0e0; padding: 15px; margin: 0; }
            .wrapper { max-width: 500px; margin: auto; padding: 10px; }
            h2 { color: #00ffcc; text-shadow: 0 0 5px rgba(0,255,204,0.2); }
            label { font-weight: bold; font-size: 14px; color: #aaa; display: block; margin-top: 10px; }
            select, input, textarea, button { width: 100%; padding: 14px; margin: 6px 0; box-sizing: border-box; border-radius: 8px; border: 1px solid #333; background: #1e1e1e; color: #fff; font-size: 16px; -webkit-appearance: none; }
            button { background: #00ffcc; color: #121212; font-weight: bold; cursor: pointer; border: none; margin-top: 15px; box-shadow: 0 4px 10px rgba(0,255,204,0.3); }
            .infinite-scroll-feed { margin-top: 25px; will-change: transform; transform: translateZ(0); contain: layout style paint; }
            .ad-card-item { background: #1a1a1a; border-radius: 8px; margin-bottom: 15px; padding: 15px; content-visibility: auto; contain-intrinsic-size: 0 240px; border: 1px solid #222; }
            .svg-placeholder { width: 100%; height: 140px; margin-top: 8px; border-radius: 6px; background: #1e1e1e; }
            .response-box { background: #1a1a1a; padding: 12px; border-left: 4px solid #00ffcc; margin-top: 20px; white-space: pre-wrap; font-family: monospace; border-radius: 4px; box-sizing: border-box; overflow-x: auto; }
        </style>
    </head>
    <body>
        <div class="wrapper">
            <h2>WAC Master Core Engine</h2>
            <label>Account Billing Status:</label>
            <select id="tenant_tier">
                <option value="PaidPremium">Paid Premium</option>
                <option value="TrialActive">Trial Active</option>
                <option value="TrialExpired">Trial Expired</option>
            </select>
            
            <label>Ad Taxonomy Category:</label>
            <select id="category" onchange="updateMetadataPlaceholder()">
                <option value="Product Launch">Product Launch</option>
                <option value="Job Board">Job Board</option>
                <option value="Event">Event</option>
                <option value="Game">Game</option>
            </select>
            
            <label>Campaign Title:</label>
            <input type="text" id="title" value="Redmi 13 Database Campaign">
            
            <label>Metadata Attributes (JSON Format):</label>
            <textarea id="metadata" rows="4">{"product_name": "Redmi 13 Ultra", "suggested_retail_price": 29999.00}</textarea>
            
            <button onclick="submitPayload()">Deploy & Write to Database</button>
            
            <h3>API Gateway Output Response:</h3>
            <div id="response" class="response-box">Awaiting submission...</div>
            
            <h3>Optimized Local Ad Feed (90Hz Hardware Vector Graphics)</h3>
            <div class="infinite-scroll-feed" id="feed_container"></div>
        </div>

        <script>
            function updateMetadataPlaceholder() {
                const cat = document.getElementById("category").value;
                const meta = document.getElementById("metadata");
                if(cat === "Product Launch") meta.value = '{"product_name": "Redmi 13 Ultra", "suggested_retail_price": 29999.00}';
                if(cat === "Job Board") meta.value = '{"company_name": "Kathmandu Tech", "employment_type": "Full-Time"}';
                if(cat === "Event") meta.value = '{"venue_name": "Lalitpur Arena", "organizer_contact_email": "info@event.np"}';
                if(cat === "Game") meta.value = '{"game_title": "Himalayan Quest", "app_store_download_link": "https://store.com"}';
            }

            // Using local inline SVG vector drawings to completely bypass network proxy image block errors offline
            const container = document.getElementById("feed_container");
            for (let i = 1; i <= 5; i++) {
                container.innerHTML += `
                    <div class="ad-card-item">
                        <h4>Sponsor Media Card #${i}</h4>
                        <svg class="svg-placeholder" viewBox="0 0 100 50">
                            <rect width="100" height="50" fill="#262626"/>
                            <circle cx="50" cy="25" r="10" fill="#00ffcc" opacity="0.3"/>
                            <text x="50" y="28" font-size="4" fill="#00ffcc" text-anchor="middle">WAC Visual Frame #${i}</text>
                        </svg>
                    </div>
                `;
            }

            async function submitPayload() {
                const responseBox = document.getElementById("response");
                responseBox.innerText = "Processing live insertion loop...";
                try {
                    const res = await fetch("/api/v1/ads/create-verified", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                            user_id: "a3b8c9d0-1234-5678-9012-abcdef123456",
                            tenant_tier: document.getElementById("tenant_tier").value,
                            category: document.getElementById("category").value,
                            title: document.getElementById("title").value,
                            metadata: JSON.parse(document.getElementById("metadata").value),
                            media_url_raw: "http://adcenter.com"
                        })
                    });
                    const data = await res.json();
                    responseBox.innerText = JSON.stringify(data, null, 2);
                    responseBox.style.borderLeftColor = res.ok ? "#00ffcc" : "#ff3366";
                } catch(e) {
                    responseBox.innerText = "Error parsing input format fields.";
                    responseBox.style.borderLeftColor = "#ff3366";
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
