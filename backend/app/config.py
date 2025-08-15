from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env 檔案路徑與編碼設定
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # 從 .env 讀取的變數
    POLYGON_API_KEY: str = "YOUR_POLYGON_KEY"
    FMP_API_KEY: str = "YOUR_FMP_KEY"
    SQLALCHEMY_DATABASE_URL: str = "sqlite+aiosqlite:///./trade_journal.db"
    SECRET_KEY: str = "YOUR_SECRET_KEY"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    APP_DEBUG: bool = False


# 建立一個全域的 settings 物件供應用程式使用
settings = Settings()
