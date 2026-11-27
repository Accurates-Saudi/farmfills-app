from datetime import datetime, time, timezone as dt_timezone
from decimal import Decimal

from django.core import management
from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Staff, Purchase, Payment, Refund, Extra, User
from farmfills_admin.business import daily_delivery_query


def create_purchases(selected_date, dboy_by_route):
    """Create the missing purchases for one day without touching balances.
    Returns the set of user ids that got a new purchase."""
    purchase_datetime = datetime.combine(selected_date, time.min).replace(tzinfo=dt_timezone.utc)
    already_billed = set(
        Purchase.objects.filter(date__date=selected_date).values_list('user_id', flat=True)
    )
    new_rows = []
    for row in daily_delivery_query(selected_date.strftime('%Y-%m-%d')):
        (user_id, _, _, user_type_id, _, _, route_id, _, _, packets, cost) = row
        if user_id in already_billed:
            continue
        already_billed.add(user_id)
        dboy = None if user_type_id == 8 else dboy_by_route.get(route_id)
        new_rows.append(Purchase(date=purchase_datetime, quantity=packets/2,
                                 amount=Decimal(str(cost * (packets / 2))), balance=0,
                                 product_id=1, user_id=user_id, delivered_by=dboy))
    Purchase.objects.bulk_create(new_rows, batch_size=500)
    return {p.user_id for p in new_rows}


def delivery_boys_by_route():
    dboy_by_route = {}
    for staff in Staff.objects.filter(delivery=True).exclude(route_id=None):
        dboy_by_route.setdefault(staff.route_id, staff)
    return dboy_by_route


class Command(BaseCommand):
    help = 'Creates daily transacion for all customers'

    def add_arguments(self, parser):
        parser.add_argument('date', type=str, nargs='?', default=datetime.today().strftime('%Y-%m-%d'))
        parser.add_argument(
            '--recalculate',
            action='store_true',
            help='Recalculate the whole transaction history of every affected customer '
                 '(slow). By default only the new purchase is appended to the running balance.',
        )

    def handle(self, *args, **options):
        recalculate = options['recalculate']
        result = daily_delivery_query(options['date'])
        selected_date = datetime.strptime(options['date'], "%Y-%m-%d")
        purchase_datetime = datetime.combine(selected_date, time.min).replace(tzinfo=dt_timezone.utc)

        # One query each instead of one per customer.
        already_billed = set(
            Purchase.objects.filter(date__date=selected_date).values_list('user_id', flat=True)
        )
        dboy_by_route = {}
        for staff in Staff.objects.filter(delivery=True).exclude(route_id=None):
            dboy_by_route.setdefault(staff.route_id, staff)

        # Customers with any transaction after the new purchase need a full recalculation,
        # because the purchase is inserted in the middle of their history (e.g. backfills).
        needs_full = set()
        if not recalculate:
            for model, extra_filter in ((Purchase, {}), (Payment, {'paid': True}), (Refund, {}), (Extra, {})):
                needs_full.update(
                    model.objects.filter(date__gt=purchase_datetime, **extra_filter)
                    .values_list('user_id', flat=True)
                )

        created = 0
        for row in result:
            (user_id, _, _, user_type_id, _, _, route_id, _, _, packets, cost) = row
            if user_id in already_billed:
                continue
            already_billed.add(user_id)

            amount = Decimal(str(cost * (packets / 2)))
            dboy = None
            if user_type_id != 8:
                dboy = dboy_by_route.get(route_id)
                if dboy is None:
                    print("Staff not found for route id: ", route_id)

            with transaction.atomic():
                purchase = Purchase(date=purchase_datetime, quantity=packets/2, amount=amount,
                                    balance=0, product_id=1, user_id=user_id, delivered_by=dboy)

                if recalculate or user_id in needs_full:
                    purchase.save()
                    management.call_command('update_transactions_balance', str(user_id), verbosity=0)
                else:
                    user = User.objects.select_for_update().get(id=user_id)
                    user.balance = user.balance - amount
                    user.last_transaction += 1
                    purchase.balance = user.balance
                    purchase.transaction_id = user.last_transaction
                    purchase.save()
                    user.save(update_fields=['balance', 'last_transaction'])
            created += 1

        print(selected_date.strftime('%d %b, %Y') + f': Successfully created {created} daily transactions')
