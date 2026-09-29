import sqlite3
import json
from uuid import uuid4
from datetime import datetime

def initialize_mock_cloud_tables():
    """Builds the exact database schema layout mirroring your production PostgreSQL setup."""
    connection = sqlite3.connect("simulated_cloud.db")
    cursor = connection.cursor()
    
    # Generate mock master tracking structures
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ads_master (
            ad_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            is_trial_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    connection.commit()
    connection.close()
    print("[Mock Cloud Engine] Clustered relational tables initialized inside storage.")

def simulated_db_execute(title: str, category: str):
    """Intercepts async execution calls and writes records locally to disk."""
    initialize_mock_cloud_tables()
    
    generated_uuid = str(uuid4())
    connection = sqlite3.connect("simulated_cloud.db")
    cursor = connection.cursor()
    
    cursor.execute(
        "INSERT INTO ads_master (ad_id, title, category) VALUES (?, ?, ?)",
        (generated_uuid, title, category)
    )
    connection.commit()
    
    # Verify the write operation by reading the record back
    cursor.execute("SELECT * FROM ads_master WHERE ad_id = ?", (generated_uuid,))
    recorded_row = cursor.fetchone()
    connection.close()
    
    print("\n--- [SIMULATED CLUSTER WRITE SUCCESS] ---")
    print(f"Captured Ad ID   : {recorded_row[0]}")
    print(f"Campaign Title  : {recorded_row[1]}")
    print(f"Category Scope  : {recorded_row[2]}")
    print(f"Timestamp Logged: {recorded_row[4]}")
    print("-----------------------------------------\n")
    return generated_uuid

if __name__ == "__main__":
    simulated_db_execute("Redmi 13 Launch Campaign", "Product Launch")
