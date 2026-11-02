"""Allocate new money without selling existing positions."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP, ROUND_UP

ZERO = Decimal("0")
CENT = Decimal("0.01")
FRACTION = Decimal("0.00000001")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class Holding:
    ticker: str
    category: str
    quantity: Decimal
    price: Decimal
    fractional: bool = False


@dataclass(frozen=True)
class Buy:
    ticker: str
    category: str
    quantity: Decimal
    cost: Decimal


@dataclass(frozen=True)
class Plan:
    buys: list[Buy]
    spent: Decimal
    left_over: Decimal
    allocation_before: dict[str, Decimal]
    allocation_after: dict[str, Decimal]


def _allocation(values: dict[str, Decimal], total: Decimal) -> dict[str, Decimal]:
    return {
        category: (value / total * HUNDRED).quantize(CENT, ROUND_HALF_UP)
        if total else ZERO.quantize(CENT)
        for category, value in values.items()
    }


def plan_deposit(
    holdings: list[Holding], targets: dict[str, Decimal], deposit: Decimal,
) -> Plan:
    # Invalid targets or cash would make the allocation meaningless.
    if not holdings:
        raise ValueError("holdings must not be empty")
    if not deposit.is_finite() or deposit <= ZERO:
        raise ValueError("deposit must be finite and greater than zero")
    if any(not weight.is_finite() or weight < ZERO for weight in targets.values()):
        raise ValueError("target percentages must be finite and nonnegative")
    if sum(targets.values(), ZERO) != HUNDRED:
        raise ValueError("target percentages must sum to exactly 100")

    assets: dict[str, Holding] = {}
    values = dict.fromkeys(targets, ZERO)
    for holding in holdings:
        if holding.category not in targets:
            raise ValueError(f"missing target for category {holding.category!r}")
        if not holding.quantity.is_finite() or holding.quantity < ZERO:
            raise ValueError("holding quantity must be finite and nonnegative")
        if not holding.price.is_finite():
            raise ValueError("holding price must be finite")
        previous = assets.get(holding.ticker)
        if previous is not None and (
            previous.category, previous.price, previous.fractional
        ) != (holding.category, holding.price, holding.fractional):
            raise ValueError(f"inconsistent holdings for ticker {holding.ticker!r}")
        assets[holding.ticker] = holding
        values[holding.category] += holding.quantity * holding.price

    total = sum(values.values(), ZERO)
    new_total = total + deposit
    # Targets use the whole deposit, including money that may remain in cash.
    gaps = {
        category: max(ZERO, new_total * weight / HUNDRED - values[category])
        for category, weight in targets.items()
    }
    gap_total = sum(gaps.values(), ZERO)
    # Rounding budgets down prevents cent rounding from overspending cash.
    budgets = {
        category: (deposit * (gaps[category] / gap_total if gap_total else
                              weight / HUNDRED)).quantize(CENT, ROUND_DOWN)
        for category, weight in targets.items()
    }
    simulated = values.copy()
    purchases: dict[str, Buy] = {}
    remaining = deposit

    def cost_for(asset: Holding, quantity: Decimal) -> Decimal:
        previous = purchases.get(asset.ticker)
        old_quantity = previous.quantity if previous else ZERO
        old_cost = previous.cost if previous else ZERO
        return ((old_quantity + quantity) * asset.price).quantize(CENT, ROUND_HALF_UP) - old_cost

    def quantity_for(asset: Holding, budget: Decimal) -> Decimal:
        unit = FRACTION if asset.fractional else Decimal("1")
        budget = budget.quantize(CENT, ROUND_DOWN)
        quantity = (budget / asset.price).quantize(unit, ROUND_DOWN)
        cost = cost_for(asset, quantity)
        if cost > budget:
            quantity -= ((cost - budget) / asset.price).quantize(unit, ROUND_UP)
            cost = cost_for(asset, quantity)
        return quantity if quantity > ZERO and cost > ZERO else ZERO

    def purchase(asset: Holding, quantity: Decimal) -> None:
        nonlocal remaining
        if quantity <= ZERO:
            return
        previous = purchases.get(asset.ticker)
        total_quantity = quantity + (previous.quantity if previous else ZERO)
        total_cost = (total_quantity * asset.price).quantize(CENT, ROUND_HALF_UP)
        cost = total_cost - (previous.cost if previous else ZERO)
        # One entry per ticker keeps repeated leftover purchases readable.
        purchases[asset.ticker] = Buy(
            asset.ticker, asset.category,
            total_quantity, total_cost,
        )
        remaining -= cost
        simulated[asset.category] += quantity * asset.price

    # Nonpositive prices cannot produce a meaningful purchase quantity.
    eligible = {
        category: sorted(
            (asset for asset in assets.values()
             if asset.category == category and asset.price > ZERO),
            key=lambda asset: (asset.price, asset.ticker),
        )
        for category in targets
    }
    # Largest gaps go first; equal shares avoid favoring a category's ticker.
    for category in sorted(targets, key=lambda category: (-gaps[category], category)):
        members = eligible[category]
        if members:
            share = (budgets[category] / Decimal(len(members))).quantize(CENT, ROUND_DOWN)
            for asset in members:
                purchase(asset, quantity_for(asset, min(share, remaining)))

    # Recompute gaps after each buy so cash follows the current shortfall.
    while remaining > ZERO:
        remaining_gaps = {
            category: new_total * targets[category] / HUNDRED - simulated[category]
            for category in targets
        }
        selected: Holding | None = None
        quantity = ZERO
        for category in sorted(targets, key=lambda category: (-remaining_gaps[category], category)):
            if remaining_gaps[category] <= ZERO:
                continue
            for asset in eligible[category]:
                candidate = quantity_for(asset, remaining) if asset.fractional else Decimal("1")
                if (candidate > ZERO and (asset.fractional or asset.price <= remaining)
                        and ZERO < cost_for(asset, candidate) <= remaining):
                    selected, quantity = asset, candidate
                    break
            if selected is not None:
                break
        if selected is None:
            break
        purchase(selected, quantity)

    # Cash stays in the denominator, so invested category weights may sum below 100%.
    return Plan(
        sorted(purchases.values(), key=lambda buy: buy.ticker),
        deposit - remaining, remaining,
        _allocation(values, total), _allocation(simulated, new_total),
    )
