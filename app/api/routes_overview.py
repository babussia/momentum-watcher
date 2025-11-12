from fastapi import APIRouter

router = APIRouter(prefix="/overview", tags=["Overview"])

@router.get("/")
def get_overview():
    """Placeholder for stock overview endpoint."""
    return {"message": "Overview route working!"}
