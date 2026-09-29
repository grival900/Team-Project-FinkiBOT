import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(engine, "connect")
def _configure_pgvector(dbapi_connection, _connection_record) -> None:
    """The vector index only looks at the 40 nearest chunks and filters by source
    afterwards, so a search limited to one source could come back empty. Iterative
    scan keeps looking until it has enough rows. (The `::vector` query just makes sure
    pgvector is loaded before we set its options.)"""
    try:
        cur = dbapi_connection.cursor()
        try:
            cur.execute("SELECT '[1]'::vector")
            cur.execute("SET hnsw.iterative_scan = relaxed_order")
            cur.execute("SET hnsw.ef_search = 100")
        finally:
            cur.close()
        dbapi_connection.commit()
    except Exception:
        logger.warning("Could not configure pgvector HNSW search parameters", exc_info=True)
        try:
            dbapi_connection.rollback()
        except Exception:
            pass


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
