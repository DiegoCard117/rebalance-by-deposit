# rebalance-by-deposit

[Leia em português](README.pt-BR.md)

“I have X to invest today. What should I buy to move my portfolio toward its
targets without selling anything?”

Recurring deposits can rebalance a portfolio without selling positions and
triggering sale-related taxes or fees. This small Python 3.12+ library was
extracted from an application in production. It uses only the standard library,
has no runtime dependencies, and also calculates realized capital gains using FIFO.

## Install and run

From the repository root, with Python 3.12 or newer:

```sh
python -m venv .venv
# Activate: Windows PowerShell: .venv\Scripts\Activate.ps1
# Activate: macOS/Linux: source .venv/bin/activate
pip install -e .[dev]
pytest
mypy src
python examples/demo.py
```

The optional `dev` extra installs pytest and mypy. The package includes `py.typed`
and uses the `src` layout.

## Usage

```python
from decimal import Decimal as D
from rebalance_by_deposit import Holding, plan_deposit

holdings = [
    Holding("AAA3", "stocks", D("4"), D("100")),
    Holding("BBB11", "funds", D("3"), D("100")),
    Holding("TESOURO-X", "bonds", D("3"), D("100")),
]
plan = plan_deposit(
    holdings,
    {"stocks": D("50"), "funds": D("30"), "bonds": D("20")},
    D("1000"),
)
for buy in plan.buys:
    print(buy.ticker, buy.quantity, buy.cost)
assert plan.spent + plan.left_over == D("1000")
```

`Holding`, `Buy`, `Plan`, `Trade`, and `RealizedLot` are frozen dataclasses.
`Plan.buys` contains one row per ticker, sorted by ticker. Set
`Holding.fractional=True` to allow quantities with eight decimal places.
Repeated holdings for a ticker must agree on category, price, and fractional mode;
their existing quantities all contribute to the portfolio value.

## Algorithm

1. Validate that holdings are present, the deposit is positive, target percentages
   are nonnegative and sum to exactly 100, and every holding category has a target.
   Categories with no holdings are allowed, but cannot receive purchases.
2. Value holdings at their current prices. Set the new total to current value plus
   the entire deposit. For each category, calculate
   `gap = max(0, new_total * target / 100 - current_category_value)`.
3. Allocate the deposit in proportion to these gaps. If their sum is zero, use the
   target weights instead. Round category budgets down to cents to stay within cash.
4. Visit categories from largest gap to smallest. Divide each budget equally among
   its distinct eligible tickers, rounding shares down to cents. Ignore prices at or
   below zero for purchases. Buy whole units rounded down, or fractions rounded down
   to eight decimal places. Fees are not deducted for deposit purchases.
5. Recompute remaining gaps against the same new total. Find the category with the
   largest positive gap that can afford a purchase. Buy one unit of its cheapest
   eligible asset, or use the remaining cash for that asset if it is fractional.
   Repeat until no below-target category can buy. Fractional precision or cent
   rounding can leave a small amount of cash. A whole unit or spending all remaining
   cash on a fraction can take a category past its target.
6. Merge purchases by ticker. Purchase costs are rounded to cents with
   `ROUND_HALF_UP`, using the accumulated quantity per ticker. Always preserve
   `spent + left_over == deposit`. No sale is suggested.

Category ties use category name; equally cheap assets use ticker. Zero-cost
purchases after rounding are skipped so the leftover loop always makes progress.
Nonfinite numbers and negative quantities are rejected. Prices at or below zero
still enter the stated current-value calculation; callers should supply reliable
current prices for useful allocations.

For the example above, the current portfolio is 1,000, with 400 stocks, 300 funds,
and 300 bonds. A 1,000 deposit makes the new total 2,000:

| Category | Current | Target | Desired value | Gap / budget | Buy at 100 | Before | After |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stocks | 400 | 50% | 1,000 | 600 | 6 | 40% | 50% |
| Funds | 300 | 30% | 600 | 300 | 3 | 30% | 30% |
| Bonds | 300 | 20% | 400 | 100 | 1 | 30% | 20% |

All 1,000 is spent. When cash remains, `allocation_after` includes that cash in
the denominator but does not invent a cash category, so percentages may sum to
less than 100. Percentages are independently rounded to two decimal places;
an empty-valued portfolio reports zero percentages before the deposit.

## Why Decimal?

Binary floating point cannot represent many monetary amounts exactly. Pass
`Decimal` values constructed from strings, such as `D("19.99")`, never floats.
Prices, quantities, weights, costs, and calculations all use `Decimal`.
Money uses two decimal places; fractional purchase quantities use eight.
The library uses Python's current Decimal context (28 significant digits by
default); callers working with exceptionally large numbers can increase its precision.

## FIFO realized gains

```python
from datetime import date
from decimal import Decimal as D
from rebalance_by_deposit import Trade, realized_gains

rows = realized_gains([
    Trade("AAA3", date(2024, 1, 1), "buy", D("10"), D("10"), D("2")),
    Trade("AAA3", date(2025, 1, 1), "sell", D("4"), D("15"), D("1")),
])
assert rows[0].cost_basis == D("40.80")
assert rows[0].proceeds == D("59.00")
assert rows[0].gain == D("18.20")
assert rows[0].long_term
```

Trades are grouped internally by ticker and processed by date, with buys before
sells on the same day. Other same-day ties retain input order. Buys create FIFO
lots with unit cost `(quantity * price + fees) / quantity`. Sales use unit proceeds
`(quantity * price - fees) / quantity` and consume the oldest lots first, producing
one `RealizedLot` per consumed lot. Proceeds and cost basis are rounded independently
to cents with `ROUND_HALF_UP`; gain is their difference. Per-lot rounding can differ
by cents from rounding a whole sale at once. Quantities are not rounded by FIFO.
`holding_days` is the date difference and `long_term` means at least 365 days.
Selling more than the available position raises `ValueError`; no lot is invented.

## Limitations

This is not investment advice. The planner does not account for taxes, purchase
brokerage fees, minimum lots beyond one unit, liquidity, price changes, currency
conversion, or corporate actions. Supply values in one currency. FIFO calculates
gains, not tax owed; the 365-day flag is a fixed classification, not a jurisdiction's
tax rule. This is a deterministic heuristic, not an optimizer for exact target
weights. A category already at or above its target receives no leftover purchases.

MIT license, copyright 2026 DiegoCard117.
