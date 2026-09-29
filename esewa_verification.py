import base64
import hmac
import hashlib
import json

ESEWA_LIVE_SECRET_KEY = "8g8t8h8m" 

def verify_live_esewa_response(encoded_response_data: str) -> dict:
    try:
        decoded_bytes = base64.b64decode(encoded_response_data)
        response_json = json.loads(decoded_bytes.decode('utf-8'))
        
        total_amount = response_json.get("total_amount")
        transaction_uuid = response_json.get("transaction_uuid")
        product_code = response_json.get("product_code")
        provided_signature = response_json.get("signature")
        status = response_json.get("status")
        
        # Exact data structure string layout defined by eSewa documentation
        validation_data_string = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"
        
        hmac_key = bytes(ESEWA_LIVE_SECRET_KEY, 'utf-8')
        message_bytes = bytes(validation_data_string, 'utf-8')
        calculated_hash = hmac.new(hmac_key, message_bytes, hashlib.sha256).digest()
        expected_signature = base64.b64encode(calculated_hash).decode("utf-8")
        
        # Dynamically evaluate the cryptographic hash matching sequence
        if provided_signature == expected_signature and status == "COMPLETE":
            return {
                "verified": True,
                "ad_id": transaction_uuid.split('-')[1] if '-' in transaction_uuid else transaction_uuid,
                "amount_received": total_amount,
                "message": "Payment cleared successfully. Ad promotion unlocked."
            }
        else:
            return {
                "verified": False, 
                "message": "Security error: Signature verification mismatch.",
                "debug_info": {"expected": expected_signature, "provided": provided_signature}
            }
            
    except Exception as e:
        return {"verified": False, "message": f"Processing failure parsing transaction data: {str(e)}"}

if __name__ == "__main__":
    # Generate a matching mock transaction sequence payload to test the algorithm
    test_amount = "150.0"
    test_uuid = "WAC-4099-1700000000"
    test_product = "EPAYTEST"
    
    raw_signature_string = f"total_amount={test_amount},transaction_uuid={test_uuid},product_code={test_product}"
    gen_hash = hmac.new(bytes(ESEWA_LIVE_SECRET_KEY, 'utf-8'), bytes(raw_signature_string, 'utf-8'), hashlib.sha256).digest()
    valid_crypto_sig = base64.b64encode(gen_hash).decode("utf-8")
    
    mock_payload = {
        "status": "COMPLETE",
        "signature": valid_crypto_sig,
        "transaction_uuid": test_uuid,
        "total_amount": test_amount,
        "product_code": test_product
    }
    
    encoded_sample = base64.b64encode(json.dumps(mock_payload).encode('utf-8')).decode('utf-8')
    print("Running Corrected eSewa Response Parser Engine:")
    print(json.dumps(verify_live_esewa_response(encoded_sample), indent=2))
