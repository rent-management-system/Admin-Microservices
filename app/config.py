from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    JWT_SECRET: str
    USER_MANAGEMENT_URL: str
    PROPERTY_LISTING_URL: str
    PAYMENT_URL: str
    SEARCH_FILTERS_URL: str
    AI_RECOMMENDATION_URL: str
    NOTIFICATION_URL: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    USER_TOKEN: str
    PROPERTY_TOKEN: str
    PAYMENT_TOKEN: str
    SEARCH_TOKEN: str
    NOTIFICATION_TOKEN: str

    class Config:
        env_file = ".env"

settings = Settings()
