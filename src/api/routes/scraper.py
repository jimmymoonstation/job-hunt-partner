import asyncio
from fastapi import APIRouter, BackgroundTasks
from src.scraper.engine import get_status, run_scraper
from src.api.schemas import ScraperStatusOut

router = APIRouter(prefix="/scraper", tags=["scraper"])


@router.get("/status", response_model=ScraperStatusOut)
def scraper_status():
    return get_status()


@router.post("/run")
async def trigger_run(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scraper)
    return {"message": "Scraper run triggered"}


@router.post("/discover")
async def trigger_discovery(background_tasks: BackgroundTasks):
    """Run web-search company discovery in the background."""
    from src.scraper.web_search import run_company_discovery
    background_tasks.add_task(run_company_discovery)
    return {"message": "Company discovery triggered — check back in a few minutes"}


@router.post("/validate")
async def trigger_validation(background_tasks: BackgroundTasks):
    """Run job-link validation pass in the background."""
    from src.scraper.validator import run_validation
    background_tasks.add_task(run_validation)
    return {"message": "Validation pass triggered — dead links will be deactivated"}
