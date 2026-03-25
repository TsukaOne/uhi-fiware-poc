"""
UHI Data Ingestion Service — entry point.

Creates the FastAPI application, registers the API router, and defines
the startup/shutdown lifecycle. All business logic lives in api/ and pipeline/.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import router
from config import DATA_PROCESSED_PATH, DATA_RAW_PATH, ORION_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting UHI Ingestion Service")
    logger.info(f"Orion URL: {ORION_URL}")
    logger.info(f"Raw data path: {DATA_RAW_PATH}")
    logger.info(f"Processed data path: {DATA_PROCESSED_PATH}")
    yield
    logger.info("Shutting down UHI Ingestion Service")


app = FastAPI(
    title="UHI Data Ingestion Service",
    description="Download and process orthophotos, register layers in FIWARE Orion-LD",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)