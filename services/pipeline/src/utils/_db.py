import os
import time

from sqlalchemy import create_engine
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm import Session as SQLAlchemySession

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./geovect.db")
DB_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "10"))
DB_RETRY_ATTEMPTS = int(os.getenv("DB_RETRY_ATTEMPTS", "10"))
DB_RETRY_BASE_DELAY_SECONDS = float(os.getenv("DB_RETRY_BASE_DELAY_SECONDS", "0.3"))
DB_POOL_RECYCLE_SECONDS = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))

# SQLite requires this flag for FastAPI's threaded execution model.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
if not DATABASE_URL.startswith("sqlite"):
    connect_args["connect_timeout"] = DB_CONNECT_TIMEOUT_SECONDS


class RetryingSession(SQLAlchemySession):
    def _run_with_retries(self, fn, *args, **kwargs):
        last_exc = None
        for attempt in range(1, DB_RETRY_ATTEMPTS + 1):
            try:
                return fn(*args, **kwargs)
            except (
                sa_exc.OperationalError,
                sa_exc.InterfaceError,
                sa_exc.DBAPIError,
            ) as exc:
                if attempt >= DB_RETRY_ATTEMPTS:
                    raise

                last_exc = exc
                try:
                    self.invalidate()
                except Exception:
                    self.close()

                # Tiny backoff helps when DB wakes from idle/sleeping state.
                time.sleep(DB_RETRY_BASE_DELAY_SECONDS * attempt)

        raise last_exc

    def get(self, *args, **kwargs):
        return self._run_with_retries(super().get, *args, **kwargs)

    def execute(self, *args, **kwargs):
        return self._run_with_retries(super().execute, *args, **kwargs)

    def commit(self):
        return self._run_with_retries(super().commit)


engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=DB_POOL_RECYCLE_SECONDS,
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=RetryingSession,
)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    from src.utils.models import *

    Base.metadata.create_all(bind=engine)
