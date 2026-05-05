import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    ENABLE_ECourts: bool = os.getenv("ENABLE_ECourts", "true").lower() in {"1", "true", "yes", "on"}
    ECOURT_BASE_URL: str = os.getenv("ECOURT_BASE_URL", "https://legtech-backend.azurewebsites.net").rstrip("/")
    ECOURT_USERNAME: str = os.getenv("ECOURT_USERNAME", "")
    ECOURT_PASSWORD: str = os.getenv("ECOURT_PASSWORD", "")


settings = Settings()
