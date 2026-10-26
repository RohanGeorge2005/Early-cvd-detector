"""Operator commands for generating the local-demo encryption key and staff accounts."""
from __future__ import annotations

import argparse
from getpass import getpass
import os
import secrets

from cryptography.fernet import Fernet

from backend.patient_store import PatientStore, STAFF_ROLES


def main() -> None:
    parser = argparse.ArgumentParser(description="Local XAI-CVD patient-demo administration")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate-key", help="Print a new encryption key; store it in a private environment secret")
    user = sub.add_parser("create-staff", help="Create a staff account in the configured encrypted local store")
    user.add_argument("--username", required=True)
    user.add_argument("--role", choices=sorted(STAFF_ROLES), required=True)
    args = parser.parse_args()

    if args.command == "generate-key":
        print(Fernet.generate_key().decode("ascii"))
        print("Keep this key private and backed up. Losing it makes encrypted demo records unrecoverable.")
        return

    key = os.getenv("XAI_CVD_ENCRYPTION_KEY", "").strip()
    if not key:
        parser.error("Set XAI_CVD_ENCRYPTION_KEY before creating staff accounts.")
    first = getpass("Password (12+ characters): ")
    second = getpass("Confirm password: ")
    if not secrets.compare_digest(first, second):
        parser.error("Passwords did not match.")
    path = os.getenv("XAI_CVD_PATIENT_DB", "data/patient-demo.sqlite3")
    store = PatientStore(path, key)
    try:
        user_record = store.create_user(args.username, first, args.role)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Created {user_record['role']} account {user_record['username']} ({user_record['id']}).")


if __name__ == "__main__":
    main()
