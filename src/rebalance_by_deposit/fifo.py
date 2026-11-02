"""Match sales to the oldest available acquisition lots."""

from collections import deque
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

CENT = Decimal("0.01")
ZERO = Decimal("0")


@dataclass(frozen=True)
class Trade:
    ticker: str
    day: date
    side: Literal["buy", "sell"]
    quantity: Decimal
    price: Decimal
    fees: Decimal = ZERO


@dataclass(frozen=True)
class RealizedLot:
    ticker: str
    sale_day: date
    acquired_day: date
    quantity: Decimal
    proceeds: Decimal
    cost_basis: Decimal
    gain: Decimal
    holding_days: int
    long_term: bool


@dataclass
class _Lot:
    day: date
    quantity: Decimal
    unit_cost: Decimal


def realized_gains(trades: list[Trade]) -> list[RealizedLot]:
    for trade in trades:
        if trade.side not in ("buy", "sell"):
            raise ValueError("trade side must be 'buy' or 'sell'")
        if not trade.quantity.is_finite() or trade.quantity <= ZERO:
            raise ValueError("trade quantity must be finite and greater than zero")
        if any(not value.is_finite() or value < ZERO for value in (trade.price, trade.fees)):
            raise ValueError("trade price and fees must be finite and nonnegative")

    inventory: dict[str, deque[_Lot]] = {}
    result: list[RealizedLot] = []
    # Same-day purchases are available to same-day sales; ties stay stable.
    for trade in sorted(trades, key=lambda trade: (trade.day, trade.side == "sell")):
        lots = inventory.setdefault(trade.ticker, deque())
        if trade.side == "buy":
            # Purchase fees belong to the acquisition cost.
            lots.append(_Lot(trade.day, trade.quantity,
                             (trade.quantity * trade.price + trade.fees) / trade.quantity))
            continue
        # Reject overselling before consuming any inventory for this sale.
        if trade.quantity > sum((lot.quantity for lot in lots), ZERO):
            raise ValueError(f"sale exceeds available position for {trade.ticker!r}")
        unit_proceeds = (trade.quantity * trade.price - trade.fees) / trade.quantity
        remaining = trade.quantity
        while remaining > ZERO:
            lot = lots[0]
            quantity = min(remaining, lot.quantity)
            proceeds = (quantity * unit_proceeds).quantize(CENT, ROUND_HALF_UP)
            cost = (quantity * lot.unit_cost).quantize(CENT, ROUND_HALF_UP)
            days = (trade.day - lot.day).days
            # One row per consumed lot preserves the holding period.
            result.append(RealizedLot(trade.ticker, trade.day, lot.day, quantity,
                                      proceeds, cost, proceeds - cost, days, days >= 365))
            lot.quantity -= quantity
            remaining -= quantity
            if lot.quantity == ZERO:
                lots.popleft()
    return result
