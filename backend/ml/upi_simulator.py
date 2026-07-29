"""Simulated UPI-style payment flow (Section 5.9).

A fake, clearly-labeled-as-simulated QR/UPI payment step for starting a
charging or swap session - matching the payment UX Indian users actually
expect, without touching any real payment rail or moving real money. No
real UPI PSP integration exists here or is intended to; every field name
and the QR payload itself say SIMULATED.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class SimulatedPaymentRequest:
    reference: str
    session_id: str
    amount_rupees: float
    upi_deep_link: str
    qr_payload: str
    status: str  # "pending" | "confirmed" | "failed"
    created_at: datetime


_PENDING_PAYMENTS: dict[str, SimulatedPaymentRequest] = {}


def initiate_payment(session_id: str, amount_rupees: float) -> SimulatedPaymentRequest:
    reference = "SIM-" + secrets.token_hex(8).upper()
    qr_payload = (
        f"upi://pay?pa=simulated.ev-orchestrator@fake&pn=EV%20Orchestrator%20SIMULATED"
        f"&am={amount_rupees:.2f}&cu=INR&tr={reference}&tn=SIMULATED-NOT-REAL-PAYMENT"
    )
    payment = SimulatedPaymentRequest(
        reference=reference,
        session_id=session_id,
        amount_rupees=round(amount_rupees, 2),
        upi_deep_link=qr_payload,
        qr_payload=qr_payload,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    _PENDING_PAYMENTS[reference] = payment
    return payment


def confirm_payment(reference: str) -> SimulatedPaymentRequest:
    """Always succeeds deterministically in simulation - there is no real
    PSP round-trip to fail. A production integration would replace this
    entire module, not extend it."""
    payment = _PENDING_PAYMENTS.get(reference)
    if payment is None:
        raise KeyError(f"unknown simulated payment reference: {reference}")
    payment.status = "confirmed"
    return payment


def get_payment(reference: str) -> SimulatedPaymentRequest | None:
    return _PENDING_PAYMENTS.get(reference)
