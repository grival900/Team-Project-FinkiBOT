"""Exports the documents table to backend/seed/documents.json.gz:
`python -m backend.scripts.export_seed`.

Each document comes with its chunks and their vectors so seed.py
can load everything without re-embedding
"""

import base64
import gzip
import json
from pathlib import Path

import numpy as np

from backend.core.config import get_settings
from backend.db import SessionLocal
from backend.models import Chunk, Document

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
SEED_PATH = SEED_DIR / "documents.json.gz"
LEGACY_SEED_PATH = SEED_DIR / "documents.json"  # the old text-only seed


def encode_vector(vector) -> str:
    # float16 halves the size; the rounding is far below what changes a search result
    return base64.b64encode(np.asarray(vector, dtype="<f2").tobytes()).decode("ascii")


def decode_vector(encoded: str) -> list[float]:
    return np.frombuffer(base64.b64decode(encoded), dtype="<f2").astype(np.float32).tolist()


def export_seed() -> int:
    with SessionLocal() as db:
        docs = db.query(Document).order_by(Document.source, Document.type, Document.url).all()
        chunks: dict = {}
        for chunk in db.query(Chunk).order_by(Chunk.document_id, Chunk.chunk_index):
            chunks.setdefault(chunk.document_id, []).append(
                {"text": chunk.text, "embedding": encode_vector(chunk.embedding)}
            )
        rows = [
            {
                "source": d.source,
                "type": d.type,
                "title": d.title,
                "url": d.url,
                "content": d.content,
                "published_at": d.published_at.isoformat() if d.published_at else None,
                "metadata": d.doc_metadata or {},
                "chunks": chunks.get(d.id, []),
            }
            for d in docs
        ]

    seed = {"embedding_model": get_settings().embedding_model_name, "documents": rows}
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    data = json.dumps(seed, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # mtime=0 so exporting the same data twice gives the same file (no noise in git)
    SEED_PATH.write_bytes(gzip.compress(data, compresslevel=9, mtime=0))
    return len(rows)


if __name__ == "__main__":
    count = export_seed()
    print(f"Exported {count} documents to {SEED_PATH}")
