from fastapi import APIRouter
from src.api.learning import run_learning_pass

router = APIRouter(prefix="/learning", tags=["learning"])


@router.post("/run")
def trigger_learning():
    """Manually trigger a learning pass. Returns summary of what was learned and cleaned."""
    return run_learning_pass()
