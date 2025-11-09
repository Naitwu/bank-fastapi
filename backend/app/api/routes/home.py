from fastapi import APIRouter
from app.core.logging import get_logger

logger = get_logger()

router = APIRouter(
    prefix="/home",
)


@router.get("/")
def home():
    logger.info("Home endpoint was called")
    logger.debug("Debugging home endpoint")
    logger.warning("This is a warning from the home endpoint")
    logger.error("This is an error from the home endpoint")
    logger.critical("This is a critical message from the home endpoint")
    return {"message": "Welcome to the Bank FastAPI application!"}
