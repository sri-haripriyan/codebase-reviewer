import sys
from pathlib import Path

# Ensure project root is in Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn

from backend.app.core.config import settings


def main():
    """Run the FastAPI application via uvicorn server."""
    print(f"Starting {settings.PROJECT_NAME} backend on {settings.HOST}:{settings.PORT}...")
    uvicorn.run(
        "backend.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
