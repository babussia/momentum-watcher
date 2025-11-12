from fastapi import APIRouter

router = APIRouter(prefix="/news", tags=["News"])

@router.get("/")
def get_news():
    """Placeholder for news endpoint."""
    return {"message": "News route working!"}
