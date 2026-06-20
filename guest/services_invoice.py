"""Invoice billing logic — fresh implementation (does not reuse calculate_stay_billing).

GST is resolved per room line from the hotel's slab table (or a flat override), since the
Indian slab depends on the per-night room rate. Discount is split pro-rata across lines pre-tax.
"""
from decimal import Decimal, ROUND_HALF_UP
import math

from django.db import transaction

from .models import Invoice, Guest
from .serializers import _hotel_local_iso

CENTS = Decimal('0.01')


def _money(value):
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


def _nights(stay):
    """Whole nights for a stay, minimum 1 (24h units)."""
    start = stay.actual_check_in or stay.check_in_date
    end = stay.actual_check_out or stay.check_out_date
    seconds = (end - start).total_seconds()
    return max(1, math.ceil(seconds / 86400))


def build_invoice_lines(booking, custom_rates=None):
    """custom_rates maps room CATEGORY id (str) -> nightly rate override. Missing -> base_price.

    Each line carries the room/category/date detail so the invoice renders without extra calls.
    """
    custom_rates = custom_rates or {}
    hotel = booking.hotel
    lines = []
    for stay in booking.stays.select_related('room__category', 'guest').all():
        if not stay.room:
            continue
        cat = stay.room.category
        rate = Decimal(str(custom_rates.get(str(cat.id), cat.base_price)))
        nights = _nights(stay)
        lines.append({
            'stay_id': stay.id,
            'room_id': stay.room.id,
            'room_number': stay.room.room_number,
            'category_id': cat.id,
            'room_type': cat.name,
            'base_price': _money(cat.base_price),
            'nights': nights,
            'rate': _money(rate),
            'amount': _money(rate * nights),
            'guest_names': stay.guest_names,
            'number_of_guests': stay.number_of_guests,
            'check_in_date': _hotel_local_iso(stay.check_in_date, hotel),
            'check_out_date': _hotel_local_iso(stay.check_out_date, hotel),
            'actual_check_in': _hotel_local_iso(stay.actual_check_in, hotel),
            'actual_check_out': _hotel_local_iso(stay.actual_check_out, hotel),
        })
    return lines


def invoice_booking_context(booking):
    """Header data for an invoice: hotel, primary guest, accompanying guests, booking dates."""
    hotel = booking.hotel
    primary = booking.primary_guest
    acc_ids = booking.accompanying_guest_ids or []
    accompanying = list(
        Guest.objects.filter(id__in=acc_ids).values(
            'id', 'full_name', 'whatsapp_number', 'nationality'
        )
    ) if acc_ids else []
    return {
        'hotel': {
            'id': str(hotel.id), 'name': hotel.name, 'logo_url': hotel.get_logo_url(),
            'address': hotel.address, 'city': hotel.city, 'state': hotel.state,
            'country': hotel.country, 'pincode': hotel.pincode,
            'phone': hotel.phone, 'email': hotel.email,
        },
        'guest': {
            'id': primary.id, 'full_name': primary.full_name,
            'whatsapp_number': primary.whatsapp_number, 'email': primary.email,
            'nationality': primary.nationality,
        },
        'accompanying_guests': accompanying,
        'status': booking.status,
        'booking_date': _hotel_local_iso(booking.booking_date, hotel),
        'check_in_date': _hotel_local_iso(booking.check_in_date, hotel),
        'check_out_date': _hotel_local_iso(booking.check_out_date, hotel),
    }


def resolve_gst(rate, slabs):
    """Pick GST% for a nightly rate. Ascending by max_rate; open-ended (null) tier sorts last."""
    rate = Decimal(str(rate))
    for s in sorted(slabs, key=lambda s: (s['max_rate'] is None, s['max_rate'] or 0)):
        if s['max_rate'] is None or rate <= Decimal(str(s['max_rate'])):
            return Decimal(str(s['gst_value']))
    return Decimal('0')  # no slab matched -> no GST


def compute_totals(lines, discount, slabs, gst_override=None):
    """Mutates each line with gst_rate/gst_amount. Returns (subtotal, gst_total, total)."""
    discount = Decimal(str(discount or 0))
    if gst_override is not None:
        gst_override = Decimal(str(gst_override))

    subtotal = sum((Decimal(str(l['amount'])) for l in lines), Decimal('0'))
    gst_total = Decimal('0')
    for l in lines:
        amount = Decimal(str(l['amount']))
        share = (amount / subtotal * discount) if subtotal else Decimal('0')
        taxable = amount - share
        gst_rate = gst_override if gst_override is not None else resolve_gst(l['rate'], slabs)
        gst_amt = _money(taxable * gst_rate / 100)
        l['gst_rate'] = gst_rate
        l['gst_amount'] = gst_amt
        gst_total += gst_amt

    subtotal = _money(subtotal)
    gst_total = _money(gst_total)
    total = _money(subtotal - discount + gst_total)
    return subtotal, gst_total, total


def next_invoice_number(hotel):
    """Sequential per-hotel invoice number. Call inside an atomic block."""
    n = Invoice.objects.select_for_update().filter(hotel=hotel).count() + 1
    return f"INV-{n:06d}"
