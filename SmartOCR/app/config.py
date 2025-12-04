from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


class Settings:
    api_key: Optional[str]
    poppler_path: Optional[str]
    tesseract_cmd: Optional[str]
    webhook_timeout_seconds: float

    def __init__(self) -> None:
        self.api_key = os.getenv("SMARTOCR_API_KEY")
        self.poppler_path = os.getenv("POPPLER_PATH")
        self.tesseract_cmd = os.getenv("TESSERACT_CMD")
        self.webhook_timeout_seconds = float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "3.0"))


settings = Settings()
