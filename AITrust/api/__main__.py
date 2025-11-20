import uvicorn

from AITrust.core.config import get_settings


def main():
    settings = get_settings()
    uvicorn.run(
        "AITrust.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
