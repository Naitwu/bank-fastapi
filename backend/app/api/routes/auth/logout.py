from fastapi import APIRouter, HTTPException, status, Response
from backend.app.core.logging import get_logger
from backend.app.auth.utils import delete_auth_cookies

logger = get_logger()

router = APIRouter(
    prefix="/auth",
)

@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout_user(response: Response) -> dict:
    try:
        delete_auth_cookies(response)
        return {
            "status": "success",
            "message": "You have been successfully logged out."
        }
    except Exception as exc:
        logger.error(f"Error during logout: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request. Please try again later."
        )