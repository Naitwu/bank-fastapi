from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from backend.app.api.main import api_router
from backend.app.core.config import settings
from backend.app.core.db import init_db, engine
from backend.app.core.logging import get_logger
from backend.app.core.health import health_checker, ServiceStatus
from contextlib import asynccontextmanager
import asyncio
import time

logger = get_logger()

async def startup_health_check(timeout: float=90.0) -> bool:
    try:
        async with asyncio.timeout(timeout):
            retry_intervals = [1, 2, 4, 8, 16]
            start_time = time.time()
            while True:
                is_healthy = await health_checker.wait_for_services()
                if is_healthy:
                    logger.info("All services are healthy.")
                    return True
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    logger.error("Services failed health check during startup within timeout.")
                    return False
                wait_time = retry_intervals[min(len(retry_intervals) - 1, int(elapsed /10))]
                logger.warning(f"Services not healthy yet. waiting {wait_time} seconds. before retrying...")
                await asyncio.sleep(wait_time)
    except asyncio.TimeoutError:
        logger.error("Timeout while waiting for services to be healthy during startup.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during startup health check: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        logger.info("Database initialized successfully.")

        await health_checker.add_service("database",check_function=health_checker.check_database)
        await health_checker.add_service("redis",check_function=health_checker.check_redis)
        await health_checker.add_service("celery",check_function=health_checker.check_celery)

        if not await startup_health_check():
            raise RuntimeError("Critical services failed to start.")
        logger.info("All services are healthy. Application startup complete.")
        yield
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        await engine.dispose()
        await health_checker.cleanup()
        raise
    finally:
        logger.info("Shutting down application...")
        await engine.dispose()
        await health_checker.cleanup()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

@app.get("/health", response_model=dict)
async def health_check():
    try:
        health_status = await health_checker.check_all_services()
        if health_status["status"] == ServiceStatus.HEALTHY:
            status_code = status.HTTP_200_OK
        elif health_status["status"] == ServiceStatus.DEGRADED:
            status_code = status.HTTP_206_PARTIAL_CONTENT
        else:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(content=health_status, status_code=status_code)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={"status": ServiceStatus.UNHEALTHY, "error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

app.include_router(api_router, prefix=settings.API_V1_STR)
