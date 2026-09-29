"""Loads `backend/seed/documents.json.gz` into the database: `python -m backend.scripts.seed`.

Quick offline setup for a new machine - no scraping. The seed ships each chunk's
vector, so nothing has to be embedded unless the embedding model changed (or the seed
is in the old format without vectors). Uses the same upsert as scraping, so it's safe
to re-run.
"""

import gzip
import json
import logging
from datetime import datetime

from backend.core.auth import hash_password
from backend.core.config import get_settings
from backend.db import SessionLocal
from backend.ingestion.pipeline import reindex_document, replace_chunks, upsert_document
from backend.models import User
from backend.scripts.export_seed import LEGACY_SEED_PATH, SEED_PATH, decode_vector
from backend.scrapers.normalize import NormalizedDocument

logger = logging.getLogger(__name__)

# Default dev admin, so a new machine can log in without setting up email first.
SEED_ADMIN_EMAIL = "admin@email.com"
SEED_ADMIN_PASSWORD = "admin"


def row_to_ndoc(row: dict) -> NormalizedDocument:
    """Pure parsing step, unit-testable against an inline dict."""
    return NormalizedDocument(
        source=row["source"],
        type=row["type"],
        title=row["title"],
        url=row["url"],
        content=row["content"],
        published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
        metadata=row["metadata"],
    ).clean()


def read_seed(data: dict | list) -> tuple[list[dict], bool]:
    """(rows, whether the stored vectors can be used). The old format is a plain list
    without vectors."""
    if isinstance(data, list):
        return data, False
    return data["documents"], data.get("embedding_model") == get_settings().embedding_model_name


def load_seed_file() -> dict | list:
    if SEED_PATH.exists():
        return json.loads(gzip.decompress(SEED_PATH.read_bytes()))
    return json.loads(LEGACY_SEED_PATH.read_text(encoding="utf-8"))


def seed() -> int:
    rows, use_vectors = read_seed(load_seed_file())
    if not use_vectors:
        logger.warning("Seed has no usable vectors for this embedding model - embedding everything (slow)")
    count = 0
    with SessionLocal() as db:
        for row in rows:
            ndoc = row_to_ndoc(row)
            try:
                with db.begin_nested():
                    doc, outcome = upsert_document(db, ndoc)
                    chunks = row.get("chunks")
                    if outcome != "unchanged" and use_vectors and chunks:
                        replace_chunks(db, doc, [c["text"] for c in chunks], [decode_vector(c["embedding"]) for c in chunks])
                    elif outcome != "unchanged":
                        reindex_document(db, doc)
            except Exception:
                logger.exception("Failed to seed %s", ndoc.url)
                continue
            count += 1
            if count % 50 == 0:
                db.commit()
        db.commit()
    return count


def seed_admin() -> bool:
    """Creates the default admin@email.com/admin account if it doesn't exist yet.
    Returns whether it was created."""
    with SessionLocal() as db:
        if db.query(User).filter_by(email=SEED_ADMIN_EMAIL).one_or_none() is not None:
            return False
        db.add(User(email=SEED_ADMIN_EMAIL, password_hash=hash_password(SEED_ADMIN_PASSWORD), is_admin=True))
        db.commit()
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = seed()
    print(f"Seeded {n} documents from {SEED_PATH}")
    if seed_admin():
        print(f"Created admin account {SEED_ADMIN_EMAIL} (password: {SEED_ADMIN_PASSWORD})")
    else:
        print(f"Admin account {SEED_ADMIN_EMAIL} already exists")
