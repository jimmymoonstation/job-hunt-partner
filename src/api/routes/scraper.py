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
