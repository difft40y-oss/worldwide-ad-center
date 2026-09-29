mkdir -p backend/app/endpoints backend/tests frontend .github/workflows
echo 'from fastapi import FastAPI; app = FastAPI()' > backend/app/main.py
echo 'from fastapi import APIRouter; router = APIRouter()' > backend/app/endpoints/ads.py
echo -e 'fastapi>=0.100.0\nuvicorn>=0.22.0' > backend/requirements.txt
echo 'Worldwide Ad Center Engine' > frontend/index.html
echo '{version: 2}' > frontend/vercel.json
