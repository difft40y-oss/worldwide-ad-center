from backend.app.main import app
@app.get("/")
def home():
return {"status": "online", "message": "Worldwide Ad Center Live API"}

