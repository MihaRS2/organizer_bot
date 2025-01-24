import os
import logging

logger = logging.getLogger(__name__)

class BotConfig:
    logger.debug("Loading BotConfig from environment...")

    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

    BOT_TOKEN_ENCRYPTED = os.getenv("BOT_TOKEN_ENCRYPTED", "")
    CALDAV_USERNAME = os.getenv("CALDAV_USERNAME", "")
    CALDAV_ENCRYPTED_PASSWORD = os.getenv("CALDAV_ENCRYPTED_PASSWORD", "")

    DB_HOST = os.getenv("DB_HOST", "db")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "mydb")
    DB_USER = os.getenv("DB_USER", "myuser")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "mypassword")

    SUPPORT_CHAT_ID = int(os.getenv("SUPPORT_CHAT_ID", "0"))
    SALES_CHAT_ID = int(os.getenv("SALES_CHAT_ID", "0"))

    CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
    DAILY_NOTIFICATION_HOUR = int(os.getenv("DAILY_NOTIFICATION_HOUR", "20"))
    MORNING_REPORT_HOUR = int(os.getenv("MORNING_REPORT_HOUR", "7"))

    logger.debug(
        "BotConfig loaded: SUPPORT_CHAT_ID=%d, SALES_CHAT_ID=%d, MORNING_REPORT_HOUR=%d",
        SUPPORT_CHAT_ID, SALES_CHAT_ID, MORNING_REPORT_HOUR
    )
