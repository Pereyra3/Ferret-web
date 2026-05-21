from decimal import Decimal

from core.money import format_mxn, format_mxn_plain


class TestFormatMxn:
    def test_zero_and_cents(self):
        assert format_mxn(0) == "$0.00"
        assert format_mxn("10.5") == "$10.50"
        assert format_mxn(Decimal("1234.5")) == "$1,234.50"

    def test_thousands_and_negative(self):
        assert format_mxn(1234567.89) == "$1,234,567.89"
        assert format_mxn(-99.9) == "-$99.90"

    def test_plain_without_sign(self):
        assert format_mxn_plain(1000) == "1,000.00"
