"""Vellore-scoped registration rules shared by the vehicle request flow
(app/routers/vehicles.py) and its admin review counterpart
(app/routers/admin.py)."""
import re
import secrets

# Vellore district's RTO code is TN-23 - a real Indian plate is
# TN23<1-2 letter series><1-4 digit number>, e.g. "TN23AB1234". Spaces/
# hyphens are stripped before matching so "TN 23 AB 1234" and "TN-23-AB-1234"
# both normalize the same way; only the district code is enforced strictly,
# since the series/number portion varies too much to validate meaningfully.
_PLATE_RE = re.compile(r"^TN23[A-Z]{1,2}\d{1,4}$")


def normalize_plate(raw: str) -> str:
    return re.sub(r"[\s-]", "", raw).upper()


def is_vellore_plate(raw: str) -> bool:
    return bool(_PLATE_RE.match(normalize_plate(raw)))


def generate_ticket_code() -> str:
    return f"VG-{secrets.token_hex(4).upper()}"


# Fixed multiple-choice reasons shown to the user when requesting a vehicle
# deletion, rather than a free-text box up front - "other" is the only one
# that requires the accompanying reason_detail to be filled in (enforced in
# app/routers/vehicles.py).
DELETE_REASON_CODES = [
    "sold_or_transferred",
    "vehicle_damaged_or_totaled",
    "replacing_with_different_vehicle",
    "duplicate_registration",
    "other",
]
