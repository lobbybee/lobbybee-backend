from decimal import Decimal

from django.test import SimpleTestCase

from .services_invoice import resolve_gst, compute_totals

SLABS = [
    {'id': 1, 'max_rate': 1000, 'gst_value': 0},
    {'id': 2, 'max_rate': 7500, 'gst_value': 5},
    {'id': 3, 'max_rate': None, 'gst_value': 18},
]


class ResolveGstTests(SimpleTestCase):
    def test_slab_boundaries_and_open_top(self):
        self.assertEqual(resolve_gst(800, SLABS), Decimal('0'))
        self.assertEqual(resolve_gst(1000, SLABS), Decimal('0'))   # ceiling inclusive
        self.assertEqual(resolve_gst(1001, SLABS), Decimal('5'))
        self.assertEqual(resolve_gst(7500, SLABS), Decimal('5'))
        self.assertEqual(resolve_gst(8000, SLABS), Decimal('18'))  # open-ended top tier
        self.assertEqual(resolve_gst(5000, []), Decimal('0'))      # no slabs -> no GST


class ComputeTotalsTests(SimpleTestCase):
    def _lines(self):
        return [
            {'rate': Decimal('5000'), 'amount': Decimal('5000')},   # -> 5% slab
            {'rate': Decimal('10000'), 'amount': Decimal('10000')},  # -> 18% slab
        ]

    def test_mixed_slabs_no_discount(self):
        subtotal, gst, total = compute_totals(self._lines(), 0, SLABS)
        self.assertEqual(subtotal, Decimal('15000.00'))
        self.assertEqual(gst, Decimal('2050.00'))   # 250 + 1800
        self.assertEqual(total, Decimal('17050.00'))

    def test_discount_split_pro_rata_pre_tax(self):
        subtotal, gst, total = compute_totals(self._lines(), Decimal('1500'), SLABS)
        # shares: 500 / 1000 -> taxable 4500 (gst 225) + 9000 (gst 1620)
        self.assertEqual(gst, Decimal('1845.00'))
        self.assertEqual(total, Decimal('15345.00'))  # 15000 - 1500 + 1845

    def test_flat_gst_override(self):
        subtotal, gst, total = compute_totals(self._lines(), 0, SLABS, gst_override=Decimal('12'))
        self.assertEqual(gst, Decimal('1800.00'))   # 600 + 1200, slab ignored
        self.assertEqual(total, Decimal('16800.00'))
