"""The `cm` command line, run with `uv run python -m app.cli`."""

import argparse
import getpass
import sys
from datetime import datetime

from sqlalchemy.orm import Session

from app.clock import SystemClock
from app.db import SessionLocal, init_db
from app.models import Profile, Role
from app.security import hash_password


class TreasurerExistsError(RuntimeError):
    pass


def create_treasurer(db: Session, name: str, email: str, password: str, now: datetime) -> Profile:
    existing = db.query(Profile).filter(Profile.role == Role.treasurer).first()
    if existing is not None:
        raise TreasurerExistsError("A Treasurer already exists")

    profile = Profile(
        name=name,
        email=email.lower(),
        phone=None,
        password_hash=hash_password(password),
        role=Role.treasurer,
        confirmed_at=now,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="cm")
    subcommands = parser.add_subparsers(dest="command", required=True)

    create = subcommands.add_parser("create-treasurer")
    create.add_argument("--name", required=True)
    create.add_argument("--email", required=True)

    args = parser.parse_args(argv)

    init_db()
    password = getpass.getpass("Password: ")
    db = SessionLocal()
    try:
        try:
            create_treasurer(db, args.name, args.email, password, SystemClock().now())
        except TreasurerExistsError as exc:
            print(exc, file=sys.stderr)
            raise SystemExit(1) from exc
    finally:
        db.close()


if __name__ == "__main__":
    main()
