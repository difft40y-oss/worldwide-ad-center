import base64
import hmac
import hashlib
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Online", "platform": "Worldwide Advertisement Center"}

@app.get("/test-esewa-signature")
def test_signature():
    secret_key = "8g8t8h8m"
    data_payload_string = "total_amount=100.0,transaction_uuid=WAC-TEST-123,product_code=EPAYTEST"
    
    hmac_key = bytes(secret_key, 'utf-8')
    message = bytes(data_payload_string, 'utf-8')
    signature = hmac.new(hmac_key, message, hashlib.sha256).digest()
    encoded_signature = base64.b64encode(signature).decode("utf-8")
    
    return {
        "calculated_signature": encoded_signature,
        "validation_status": "Verified Match" if encoded_signature else "Failed"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
