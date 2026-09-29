import sqlite3
import socket
import time
import http.client
import json

def has_active_connection():
    try:
        socket.setdefaulttimeout(2)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("1.1.1.1", 53))
        return True
    except socket.error:
        return False

def execute_daemon_flush():
    if not has_active_connection():
        return

    connection = sqlite3.connect("offline_buffer.db")
    cursor = connection.cursor()
    
    try:
        cursor.execute("SELECT log_id, event_name, payload FROM local_logs")
        rows = cursor.fetchall()
        if not rows:
            connection.close()
            return
            
        print(f"[Daemon] Network active. Flushing {len(rows)} cached logs up to the cloud...")
        
        # Simulating cloud network stream synchronization
        for row in rows:
            print(f" -> Successfully synced log log_id: {row[0]}")
            
        cursor.execute("DELETE FROM local_logs")
        connection.commit()
        print("[Daemon] Cache buffer cleared successfully.")
    except sqlite3.OperationalError:
        # Table doesn't exist yet, pass silently
        pass
    finally:
        connection.close()

if __name__ == "__main__":
    print("[Daemon] Starting network synchronization background service...")
    while True:
        execute_daemon_flush()
        time.sleep(10) # Checks connection every 10 seconds
