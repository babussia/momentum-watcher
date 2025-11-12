from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from app.services.data_cache import get_hod_data

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/", include_in_schema=False)
def dashboard(request: Request):
    """Main dashboard page (index.html)"""
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/hod/data")
def hod_data():
    """JSON feed for HOD updates"""
    return JSONResponse(get_hod_data())
