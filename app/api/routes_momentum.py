# app/api/routes_momentum.py

from fastapi import APIRouter
from app.services.data_cache import get_momentum_data

router = APIRouter()

@router.get("/data")
def momentum_data_api():
    return get_momentum_data()
