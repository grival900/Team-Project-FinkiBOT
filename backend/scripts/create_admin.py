"""CLI entrypoint to grant admin access: `python -m backend.scripts.create_admin <email>`

Register the account normally first; this only promotes it, so no password ever
goes through the command line. (seed.py also creates admin@email.com / admin for
local development - don't use that one anywhere shared.)
"""

import sys

from backend.db import SessionLocal
from backend.models import User

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m backend.scripts.create_admin <email>", file=sys.stderr)
        sys.exit(1)

    email = sys.argv[1].lower()
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=email).one_or_none()
        if user is None:
            print(f"No account found for {email!r} — register it first (via /auth/register or /register).", file=sys.stderr)
            sys.exit(1)
        user.is_admin = True
        db.commit()
    print(f"{email} is now an admin.")
