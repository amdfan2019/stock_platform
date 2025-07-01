from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://stockuser:stockpass@localhost:5432/stock_platform"
    
    # API Keys
    alpha_vantage_api_key: str = ""
    fmp_api_key: str = ""  # Financial Modeling Prep API key
    news_api_key: str = ""
    google_api_key: str = ""
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Application
    secret_key: str = "your-secret-key-here"
    debug: bool = True
    cors_origins: List[str] = ["http://localhost:3000"]
    
    # Data Update Intervals (in minutes)
    stock_data_update_interval: int = 60
    news_update_interval: int = 30
    
    # LLM Settings
    llm_model: str = "gemini-2.5-flash"
    max_tokens: int = 1000
    temperature: float = 0.3
    
    # Rate Limiting
    requests_per_minute: int = 100
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings() 