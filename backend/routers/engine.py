from fastapi import APIRouter

router = APIRouter(prefix="/api/engine", tags=["engine"])


@router.get("/models")
def list_models() -> dict:
    return {"models": []}
