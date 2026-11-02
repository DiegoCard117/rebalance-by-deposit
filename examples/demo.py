"""Run after installing the package with pip install -e .[dev]."""

from decimal import Decimal as D

from rebalance_by_deposit import Holding, plan_deposit


def main() -> None:
    holdings = [
        Holding("AAA3", "Stocks", D("10"), D("30")),
        Holding("BBB11", "Funds", D("4"), D("100")),
        Holding("TESOURO-X", "Bonds", D("1"), D("500"), fractional=True),
        Holding("COIN", "Crypto", D("0.002"), D("50000"), fractional=True),
    ]
    targets = {"Stocks": D("35"), "Funds": D("25"), "Bonds": D("35"), "Crypto": D("5")}
    plan = plan_deposit(holdings, targets, D("1000"))
    print(f"{'Ticker':<14} {'Quantity':>16} {'Cost':>12}")
    for buy in plan.buys:
        print(f"{buy.ticker:<14} {buy.quantity:>16f} {buy.cost:>12.2f}")
    print(f"Spent: {plan.spent:.2f} | Cash left: {plan.left_over:.2f}")
    print(f"\n{'Category':<14} {'Before %':>12} {'After %':>12}")
    for category in targets:
        print(f"{category:<14} {plan.allocation_before[category]:>12.2f} {plan.allocation_after[category]:>12.2f}")


if __name__ == "__main__":
    main()
