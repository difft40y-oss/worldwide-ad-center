async def root():
    return {"status": "online", "engine": "FastAPI Asynchronous Cluster"} -e from fastapi import FastAPI
app = FastAPI()
@app.get("/")
async def root():
    return {"status": "online", "engine": "FastAPI Asynchronous Cluster"}
