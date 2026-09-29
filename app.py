import asyncio
import asyncpg
import base64
import hashlib
import hmac
import json
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import RedirectResponse

app = FastAPI()

# Remote PostgreSQL Cluster Connection String
POSTGRES_DSN = "postgresql://user:password@remote-cluster-ip:5432/adv_center_db"
ESEWA_SECRET_KEY = "8g8M8ndgYGBwGq8="  # Replace with your actual eSewa Secret Key
ESEWA_VERIFY_URL = "https://esewa.com.np"

# Mock local logger function to replace missing offline analytics references
async def log_to_offline_sqlite(data, error=None):
    print(f"[SQLite Log] Syncing local fallback payload: {data} | Error: {error}")

def generate_esewa_signature(total_amount, transaction_uuid, product_code, secret_key):
    data_string = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
    secret_bytes = bytes(secret_key, 'utf-8')
    data_bytes = bytes(data_string, 'utf-8')
    hmac_result = hmac.new(secret_bytes, data_bytes, hashlib.sha256).digest()
    return base64.b64encode(hmac_result).decode('utf-8')

def verify_esewa_signature(total_amount: str, transaction_uuid: str, product_code: str, received_signature: str) -> bool:
    try:
        data_string = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        secret_bytes = bytes(ESEWA_SECRET_KEY, 'utf-8')
        data_bytes = bytes(data_string, 'utf-8')
        computed_hmac = hmac.new(secret_bytes, data_bytes, hashlib.sha256).digest()
        expected_signature = base64.b64encode(computed_hmac).decode('utf-8')
        return hmac.compare_digest(expected_signature, received_signature)
    except Exception:
        return False

async def save_to_postgres(form_data: dict):
    try:
        conn = await asyncpg.connect(dsn=POSTGRES_DSN)
        await conn.execute('''
            INSERT INTO advertisement_submissions (campaign_name, budget, targeting_data, status)
            VALUES ($1, $2, $3, 'pending_payment')
        ''', form_data.get('name'), form_data.get('budget'), form_data.get('targeting'))
        await conn.close()
    except Exception as e:
        await log_to_offline_sqlite(form_data, error=str(e))

async def finalize_order_in_cluster(transaction_uuid: str, esewa_ref: str, amount: str):
    try:
        conn = await asyncpg.connect(dsn=POSTGRES_DSN)
        await conn.execute('''
            UPDATE advertisement_submissions 
            SET status = 'active', payment_reference = $1, amount_paid = $2, updated_at = NOW()
            WHERE transaction_uuid = $3 AND status = 'pending_payment'
        ''', esewa_ref, amount, transaction_uuid)
        await conn.close()
    except Exception as e:
        print(f"[Critical Error] Failed to update PostgreSQL cluster: {e}")

@app.post("/api/v1/submit-ad")
async def handle_ad_submission(data: dict, background_tasks: BackgroundTasks):
    await log_to_offline_sqlite(data)
    background_tasks.add_task(save_to_postgres, data)
    return {"status": "success", "message": "Form data staged. Initializing eSewa intent."}

@app.get("/payment-success")
async def esewa_payment_success_callback(background_tasks: BackgroundTasks, data: str = Query(...)):
    try:
        decoded_bytes = base64.b64decode(data)
        tx_data = json.loads(decoded_bytes.decode('utf-8'))
        
        total_amount = tx_data.get("total_amount")
        transaction_uuid = tx_data.get("transaction_uuid")
        product_code = tx_data.get("product_code")
        received_sig = tx_data.get("signature")
        
        if not verify_esewa_signature(total_amount, transaction_uuid, product_code, received_sig):
            raise HTTPException(status_code=400, detail="Cryptographic Signature mismatch.")
            
        if tx_data.get("status") != "COMPLETE":
            raise HTTPException(status_code=400, detail="Transaction status unconfirmed.")

        async with httpx.AsyncClient() as client:
            verify_params = {"product_code": product_code, "total_amount": total_amount, "transaction_uuid": transaction_uuid}
            response = await client.get(ESEWA_VERIFY_URL, params=verify_params)
            if response.status_code != 200 or response.json().get("status") != "COMPLETE":
                raise HTTPException(status_code=401, detail="eSewa status validation failed.")
            esewa_ref_id = response.json().get("ref_id")

        background_tasks.add_task(finalize_order_in_cluster, transaction_uuid, esewa_ref_id, total_amount)
        return RedirectResponse(url="/dashboard?payment=success&id=" + transaction_uuid)
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))
