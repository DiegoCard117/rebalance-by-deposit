from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from rebalance_by_deposit import Trade, realized_gains


def test_partial_sale_crosses_two_lots() -> None:
    trades = [Trade("AAA3", date(2025, 3, 1), "sell", D("12"), D("30")),
              Trade("AAA3", date(2025, 2, 1), "buy", D("5"), D("20")),
              Trade("AAA3", date(2025, 1, 1), "buy", D("10"), D("10"))]
    rows = realized_gains(trades)
    assert [row.quantity for row in rows] == [D("10"), D("2")]
    assert [row.cost_basis for row in rows] == [D("100.00"), D("40.00")]
    assert [row.proceeds for row in rows] == [D("300.00"), D("60.00")]
    assert [row.gain for row in rows] == [D("200.00"), D("20.00")]
    assert rows[0].acquired_day == date(2025, 1, 1)
    assert rows[1].acquired_day == date(2025, 2, 1)
    rows = realized_gains(trades + [Trade("AAA3", date(2025, 4, 1), "sell", D("3"), D("25"))])
    assert rows[-1].cost_basis == D("60.00")


def test_fees() -> None:
    rows = realized_gains([Trade("AAA3", date(2025, 1, 1), "buy", D("10"), D("10"), D("2")),
                           Trade("AAA3", date(2025, 2, 1), "sell", D("4"), D("15"), D("1"))])
    assert rows[0].proceeds == D("59.00")
    assert rows[0].cost_basis == D("40.80")
    assert rows[0].gain == D("18.20")


@pytest.mark.parametrize("days, long_term", [(364, False), (365, True), (366, True)])
def test_long_term_boundary(days: int, long_term: bool) -> None:
    acquired = date(2024, 1, 1)
    row = realized_gains([Trade("AAA3", acquired, "buy", D("1"), D("10")),
                          Trade("AAA3", acquired + timedelta(days=days), "sell", D("1"), D("11"))])[0]
    assert row.holding_days == days
    assert row.long_term is long_term


def test_overselling() -> None:
    with pytest.raises(ValueError, match="exceeds.*AAA3"):
        realized_gains([Trade("AAA3", date(2025, 1, 1), "buy", D("1"), D("10")),
                        Trade("AAA3", date(2025, 2, 1), "sell", D("2"), D("20"))])


def test_separate_tickers_and_same_day_order() -> None:
    day = date(2025, 1, 1)
    rows = realized_gains([Trade("AAA3", day, "sell", D("1"), D("20")),
                           Trade("BBB11", day, "buy", D("1"), D("99")),
                           Trade("AAA3", day, "buy", D("2"), D("10")),
                           Trade("BBB11", day, "sell", D("1"), D("100"))])
    assert [(row.ticker, row.gain) for row in rows] == [("AAA3", D("10.00")), ("BBB11", D("1.00"))]
    assert rows[0].holding_days == 0


def test_empty_trades() -> None:
    assert realized_gains([]) == []

