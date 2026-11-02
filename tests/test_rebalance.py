from decimal import Decimal as D

import pytest

from rebalance_by_deposit import Buy, Holding, plan_deposit


def test_three_categories_by_hand() -> None:
    holdings = [Holding("AAA3", "stocks", D("4"), D("100")),
                Holding("BBB11", "funds", D("3"), D("100")),
                Holding("TESOURO-X", "bonds", D("3"), D("100"))]
    plan = plan_deposit(holdings, {"stocks": D("50"), "funds": D("30"), "bonds": D("20")}, D("1000"))
    assert plan.buys == [Buy("AAA3", "stocks", D("6"), D("600.00")),
                         Buy("BBB11", "funds", D("3"), D("300.00")),
                         Buy("TESOURO-X", "bonds", D("1"), D("100.00"))]
    assert plan.allocation_before == {"stocks": D("40.00"), "funds": D("30.00"), "bonds": D("30.00")}
    assert plan.allocation_after == {"stocks": D("50.00"), "funds": D("30.00"), "bonds": D("20.00")}
    assert plan.spent == D("1000.00")
    assert plan.left_over == D("0.00")


def test_overweight_category_gets_nothing() -> None:
    holdings = [Holding("AAA3", "a", D("9"), D("100")),
                Holding("BBB11", "b", D("1"), D("100"))]
    plan = plan_deposit(holdings, {"a": D("50"), "b": D("50")}, D("200"))
    assert [buy.ticker for buy in plan.buys] == ["BBB11"]
    assert plan.buys[0].quantity == D("2")


def test_expensive_unit_redirects_leftover() -> None:
    holdings = [Holding("EXPENSIVE", "a", D("0"), D("1000")),
                Holding("CHEAP", "b", D("0"), D("10"))]
    plan = plan_deposit(holdings, {"a": D("80"), "b": D("20")}, D("100"))
    assert plan.buys == [Buy("CHEAP", "b", D("2"), D("20.00"))]
    # This category is already at its target, so the remaining cash stays cash.
    assert plan.left_over == D("80.00")
    plan = plan_deposit(holdings, {"a": D("55"), "b": D("45")}, D("100"))
    assert plan.buys == [Buy("CHEAP", "b", D("5"), D("50.00"))]
    assert plan.left_over == D("50.00")


def test_fractional_spends_leftover_and_merges_ticker() -> None:
    holdings = [Holding("AAA3", "a", D("0"), D("60")),
                Holding("COIN", "a", D("0"), D("1"), True)]
    plan = plan_deposit(holdings, {"a": D("100")}, D("100"))
    assert plan.buys == [Buy("COIN", "a", D("100.00000000"), D("100.00"))]
    assert plan.left_over == D("0.00")


@pytest.mark.parametrize("deposit", ["0.001", "0.01", "1", "19.99", "100", "1000.13", "10000"])
def test_cash_conservation_and_no_sales(deposit: str) -> None:
    holdings = [Holding("AAA3", "a", D("2"), D("17.31")),
                Holding("COIN", "b", D("0.15"), D("123.456789"), True)]
    plan = plan_deposit(holdings, {"a": D("60"), "b": D("40")}, D(deposit))
    assert plan.spent + plan.left_over == D(deposit)
    assert sum((buy.cost for buy in plan.buys), D("0")) == plan.spent
    assert plan.left_over >= D("0")
    assert all(buy.quantity > D("0") and buy.cost > D("0") for buy in plan.buys)
    assert all(buy.cost == (buy.quantity * next(h.price for h in holdings if h.ticker == buy.ticker)).quantize(D("0.01")) for buy in plan.buys)
    assert holdings[0].quantity == D("2")


def test_target_validation() -> None:
    holdings = [Holding("AAA3", "a", D("1"), D("10"))]
    with pytest.raises(ValueError, match="exactly 100"):
        plan_deposit(holdings, {"a": D("99.99")}, D("10"))
    with pytest.raises(ValueError, match="missing target.*a"):
        plan_deposit(holdings, {"b": D("100")}, D("10"))


@pytest.mark.parametrize("deposit", ["0", "-1"])
def test_invalid_deposit(deposit: str) -> None:
    with pytest.raises(ValueError, match="deposit"):
        plan_deposit([Holding("AAA3", "a", D("0"), D("1"))], {"a": D("100")}, D(deposit))


def test_empty_holdings() -> None:
    with pytest.raises(ValueError, match="empty"):
        plan_deposit([], {"a": D("100")}, D("1"))


def test_nonpositive_prices_ignored() -> None:
    plan = plan_deposit([Holding("ZERO", "a", D("0"), D("0")),
                         Holding("NEGATIVE", "a", D("0"), D("-1"))],
                        {"a": D("100")}, D("100"))
    assert plan.buys == []
    assert plan.left_over == D("100")


def test_equal_shares_and_ticker_order() -> None:
    plan = plan_deposit([Holding("ZZZ", "a", D("0"), D("10")),
                         Holding("AAA", "a", D("0"), D("20"))],
                        {"a": D("100")}, D("100"))
    assert plan.buys == [Buy("AAA", "a", D("2"), D("40.00")),
                         Buy("ZZZ", "a", D("6"), D("60.00"))]

