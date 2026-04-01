"""Transaction validators."""

from typing import Tuple


def validate_transfer(
    from_id: int,
    to_id: int,
    amount: int,
    balance: int
) -> Tuple[bool, str]:
    """Validate a transfer.

    Args:
        from_id: Sender ID.
        to_id: Recipient ID.
        amount: Amount.
        balance: Sender's balance.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if from_id == to_id:
        return False, "Cannot transfer to yourself"
    if amount <= 0:
        return False, "Amount must be positive"
    if balance < amount:
        return False, "Insufficient balance"
    return True, ""


def validate_amount(
    amount: int,
    min_amount: int = 1,
    max_amount: int = 1000000
) -> Tuple[bool, str]:
    """Validate an amount.

    Args:
        amount: The amount.
        min_amount: Minimum allowed.
        max_amount: Maximum allowed.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if amount < min_amount:
        return False, f"Amount must be at least {min_amount}"
    if amount > max_amount:
        return False, f"Amount cannot exceed {max_amount}"
    return True, ""
