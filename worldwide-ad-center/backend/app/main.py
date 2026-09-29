from fastapi import FastAPI; app = FastAPI()
@app.get("/convert")
def convert_currency(currency: str = "usd", amount: float = 100.0):
    if currency.lower() == "usd":
        converted = amount * 135.50
    elif currency.lower() == "eur":
        converted = amount * 143.20
    else:
        return {"error": "Unsupported currency. Use usd or eur."}
    
    return {
        "base_currency": currency.upper(),
        "input_amount": amount,
        "converted_npr": round(converted, 2),
        "status": "success"
    }
@app.get("/metrics/ads")
def get_ad_analytics():
    return {
        "status": "active",
        "region_scope": "Gandaki Province",
        "live_campaigns": 8,
        "total_impressions": 1420500,
        "total_clicks": 38420,
        "click_through_rate_pct": round((38420 / 1420500) * 100, 2),
        "estimated_revenue_usd": round(38420 * 0.015, 2)
    }
# Task Option B: Publisher Registration data tracking arrays
@app.post("/publisher/register")
def register_publisher(name: str, site_url: str, region: str = "Gandaki Province"):
    return {
        "status": "pending_verification",
        "publisher_name": name,
        "traffic_channel": site_url,
        "region_scope": region,
        "publisher_id": "PUB-9482-X"
    }

# Security Loop: Anti-Fraud Click Verification System
@app.get("/click/verify")
def verify_ad_click(click_id: str, publisher_id: str, user_ip: str):
    # Simulated validation check parameters 
    if len(click_id) < 5 or "bot" in user_ip.lower():
        return {"status": "rejected", "reason": "Suspicious activity signature flagged"}
    return {
        "status": "validated",
        "click_id": click_id,
        "payout_credited_npr": 2.05,
        "escrow_status": "locked"
    }

# Payout Gateway: Local eSewa Integration Bridge Endpoint
@app.post("/payout/esewa")
def process_esewa_payout(publisher_id: str, wallet_phone: str, amount_npr: float):
    if amount_npr < 500.0:
        return {"status": "failed", "reason": "Minimum payout threshold is Rs 500.0"}
    return {
        "transaction_id": "ESEWA-TXN-849201",
        "recipient_wallet": wallet_phone,
        "payout_status": "processed_success",
        "currency": "NPR",
        "amount_transferred": amount_npr
    }
