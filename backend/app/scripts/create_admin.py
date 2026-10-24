"""Create (or promote) an admin account. Admins can't self-register; this is the only way in.

Usage:
    python -m app.scripts.create_admin --username organizer.edison --full-name "Edison Organizer" \
        --mandal-name Edison --mandal-type Yuvti
The password is read from ADMIN_PASSWORD or prompted for (never pass it as an argument).
"""

import argparse
import asyncio
import getpass
import os
import sys

from ..audit.service import write_audit
from ..auth.passwords import password_problems
from ..common import utcnow
from ..db import close_db, ensure_indexes, get_db
from ..enums import MANDAL_NAMES, MANDAL_TYPES, AuditAction, Role
from ..users.service import create_user, normalize_username


def _read_password(username: str) -> str:
    pw = os.environ.get("ADMIN_PASSWORD")
    if not pw:
        pw = getpass.getpass("Admin password: ")
        if pw != getpass.getpass("Confirm password: "):
            sys.exit("Passwords do not match.")
    problems = password_problems(pw, username)
    if problems:
        sys.exit("Password rejected: " + " ".join(problems))
    return pw


async def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--username", required=True)
    p.add_argument("--full-name", required=True)
    p.add_argument("--mandal-name", choices=MANDAL_NAMES, default=MANDAL_NAMES[0])
    p.add_argument("--mandal-type", choices=MANDAL_TYPES, default=MANDAL_TYPES[0])
    p.add_argument("--promote", action="store_true", help="Promote an existing user to admin instead of creating one")
    args = p.parse_args(argv)

    db = get_db()
    await ensure_indexes(db)
    existing = await db.users.find_one({"username_lower": normalize_username(args.username)})
    if existing:
        if not args.promote:
            sys.exit(f"User '{args.username}' already exists. Re-run with --promote to make them an admin.")
        await db.users.update_one({"_id": existing["_id"]}, {"$set": {"role": Role.ADMIN.value, "updated_at": utcnow()}})
        await write_audit(db, entity="user", entity_id=existing["_id"], action=AuditAction.UPDATE, actor=None,
                          before={"role": existing["role"]}, after={"role": Role.ADMIN.value}, reason="Promoted via CLI")
        print(f"Promoted {existing['username']} to admin.")
    else:
        pw = _read_password(args.username)
        user = await create_user(db, full_name=args.full_name, username=args.username, password=pw,
                                 mandal_name=args.mandal_name, mandal_type=args.mandal_type, role=Role.ADMIN)
        await write_audit(db, entity="user", entity_id=user["_id"], action=AuditAction.CREATE, actor=None,
                          before=None, after={"username": user["username"], "role": user["role"]},
                          reason="Admin created via CLI")
        print(f"Created admin {user['username']}.")
    close_db()


if __name__ == "__main__":
    asyncio.run(main())
