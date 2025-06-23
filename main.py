from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from routes import health_routes, auth, health_data
from utils.security import get_current_user
from config import get_settings
import os
from dotenv import load_dotenv
import logging
from logging.handlers import TimedRotatingFileHandler
from fastapi import APIRouter

load_dotenv()

settings = get_settings()

app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])

# Include health routes (both authenticated and non-authenticated)
app.include_router(
    health_routes.router,
    prefix="/api/v1/health",
    tags=["health"]
)

# Include health data routes (including webhook)
app.include_router(
    health_data.router,
    prefix="/api/v1",
    tags=["health-data"]
)

TAIL_PATH = "logs"
FILE_NAME = "integration-be.log"

log_path = os.path.join(os.getcwd(), TAIL_PATH)
simple_logger = logging.getLogger("log")
if not os.path.exists(log_path):
    os.makedirs(log_path)
log_formatter = logging.Formatter(
    '%(asctime)s - %(pathname)20s:%(lineno)4s - %(funcName)20s() - %(levelname)s ## %(message)s')
handler = TimedRotatingFileHandler(log_path + "/" + FILE_NAME,
                                   when="d",
                                   interval=1,
                                   backupCount=10)
handler.setFormatter(log_formatter)
if not len(simple_logger.handlers):
    simple_logger.addHandler(handler)
simple_logger.setLevel(logging.DEBUG)

app.state.logger = simple_logger

@app.get("/")
async def root():
    return {
        "message": "Welcome to FoodHak Health API",
        "version": settings.API_VERSION,
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8009)
