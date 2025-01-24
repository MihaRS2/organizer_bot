import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from bot.config import BotConfig

logger = logging.getLogger(__name__)
Base = declarative_base()

class Database:
    _engine = None
    SessionLocal = None

    @classmethod
    def init(cls):
        if cls._engine is None:
            logger.debug("Database.init called, creating engine...")
            db_url = (
                f"postgresql://{BotConfig.DB_USER}:{BotConfig.DB_PASSWORD}@"
                f"{BotConfig.DB_HOST}:{BotConfig.DB_PORT}/{BotConfig.DB_NAME}"
            )
            logger.debug("DB URL = %s", db_url)
            cls._engine = create_engine(db_url, echo=False)
            cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls._engine)
            Base.metadata.create_all(bind=cls._engine)
            logger.info("Database initialized (tables created).")

    @classmethod
    def get_session(cls):
        if cls._engine is None:
            cls.init()
        return cls.SessionLocal()
