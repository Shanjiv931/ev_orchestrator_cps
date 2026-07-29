import pytest

from ml.upi_simulator import confirm_payment, get_payment, initiate_payment


def test_initiate_payment_is_clearly_labeled_simulated():
    payment = initiate_payment(session_id="s1", amount_rupees=150.0)
    assert "SIMULATED" in payment.qr_payload.upper()
    assert payment.status == "pending"
    assert payment.reference.startswith("SIM-")


def test_qr_payload_encodes_the_correct_amount():
    payment = initiate_payment(session_id="s1", amount_rupees=187.5)
    assert "am=187.50" in payment.qr_payload


def test_confirm_payment_transitions_to_confirmed():
    payment = initiate_payment(session_id="s2", amount_rupees=99.0)
    confirmed = confirm_payment(payment.reference)
    assert confirmed.status == "confirmed"
    assert get_payment(payment.reference).status == "confirmed"


def test_confirm_unknown_reference_raises():
    with pytest.raises(KeyError):
        confirm_payment("SIM-DOES-NOT-EXIST")


def test_no_real_payment_network_is_ever_contacted():
    """A structural guard: this module must not import any HTTP/network
    client - it is a pure in-memory simulation, never a real integration."""
    import ml.upi_simulator as upi_module

    assert "requests" not in upi_module.__dict__
    assert "httpx" not in upi_module.__dict__
