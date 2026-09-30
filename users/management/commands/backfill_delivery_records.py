"""
Re-create a day's delivery records for one route after delete_delivery_records.

There is no backup, so rows are regenerated from subscriptions / vacations /
extraless for that date (same logic as today_transaction and
generate_delivery_data). Current route assignments and balances are used,
so the result can differ slightly from what was originally there.

Recreates:
    users_purchase          one per customer with packets that day (skips users who already have one)
    delivery_deliverydata   the route's delivery list (skipped if the route already has rows that day)
    users_delivery          the delivery boy's run for that day, without start/end times
                            (skipped if one already exists)

Usage (dry run by default, nothing is written until --apply):

    python3 manage.py backfill_delivery_records 2026-09-28 --route 4
    python3 manage.py backfill_delivery_records 2026-09-28 --route "Route name" --apply
"""
from datetime import datetime, time, timezone as dt_timezone

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from delivery.models import DeliveryData
from delivery.views import getDeliveryListByDate
from farmfills_admin.business import daily_delivery_query
from users.models import Delivery, Purchase, Route, Staff


class Command(BaseCommand):
    help = "Re-create purchases, delivery data and delivery for given date(s) and route"

    def add_arguments(self, parser):
        parser.add_argument('dates', nargs='+', help='One or more dates, YYYY-MM-DD')
        parser.add_argument('--route', required=True, help='Route id or route name')
        parser.add_argument('--apply', action='store_true', help='Actually write (default is dry run)')
        parser.add_argument('--yes', action='store_true', help='Skip the confirmation prompt')

    def handle(self, *args, **options):
        try:
            dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in options['dates']]
        except ValueError as e:
            raise CommandError(f'Bad date: {e}')

        r = options['route']
        route = (Route.objects.filter(id=r) if r.isdigit() else Route.objects.filter(name=r)).first()
        if route is None:
            raise CommandError(f'Route not found: {r}')

        dboy = Staff.objects.filter(delivery=True, route=route).first()
        if dboy is None:
            self.stdout.write(self.style.WARNING(f'No delivery boy for route {route}, purchases will have no delivered_by and no delivery row is created'))

        plans = [self.plan(d, route, dboy) for d in dates]

        self.stdout.write(f'Route : "{route}" (id {route.id})')
        for p in plans:
            self.stdout.write(f'{p["date"]}:')
            self.stdout.write(f'  users_purchase           {len(p["purchases"]):>8} to create ({p["skipped"]} customers already have one)')
            self.stdout.write(f'  delivery_deliverydata    {len(p["delivery_data"]):>8} to create'
                              + ('  (skipped, rows exist)' if p['delivery_data_exists'] else ''))
            self.stdout.write(f'  users_delivery           {1 if p["delivery"] else 0:>8} to create ({p["packets"]} packets)')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('DRY RUN. Re-run with --apply to write.'))
            return

        if not options['yes']:
            reply = input("Type 'backfill' to continue: ")
            if reply.strip() != 'backfill':
                self.stdout.write('aborted.')
                return

        user_ids = set()
        with transaction.atomic():
            for p in plans:
                Purchase.objects.bulk_create(p['purchases'])
                user_ids.update(x.user_id for x in p['purchases'])

                created = DeliveryData.objects.bulk_create(p['delivery_data'])
                # date is auto_now_add, so it was set to today; move it to the backfilled date
                DeliveryData.objects.filter(id__in=[d.id for d in created]).update(date=p['date'])

                if p['delivery']:
                    p['delivery'].save()

                self.stdout.write(self.style.SUCCESS(
                    f'  {p["date"]}: created {len(p["purchases"])} purchases, '
                    f'{len(created)} delivery data, {1 if p["delivery"] else 0} delivery'))

        self.stdout.write(f'Recalculating balance for {len(user_ids)} customers...')
        for user_id in user_ids:
            call_command('update_transactions_balance', str(user_id), verbosity=0)
        self.stdout.write(self.style.SUCCESS('Done.'))

    def plan(self, date, route, dboy):
        date_str = date.strftime('%Y-%m-%d')
        purchase_datetime = datetime.combine(date, time.min).replace(tzinfo=dt_timezone.utc)

        purchases, skipped = [], 0
        for row in daily_delivery_query(date_str, route.id):
            (user_id, _, _, user_type_id, _, _, _, _, _, packets, cost) = row
            if Purchase.objects.filter(user_id=user_id, date__date=date).exists():
                skipped += 1
                continue
            purchases.append(Purchase(
                date=purchase_datetime, quantity=packets / 2, amount=cost * (packets / 2), balance=0,
                product_id=1, user_id=user_id, delivered_by=None if user_type_id == 8 else dboy,
            ))

        delivery_list = getDeliveryListByDate(route, date_str)
        delivery_data_exists = DeliveryData.objects.filter(route=route, date=date).exists()
        delivery_data = []
        if not delivery_data_exists:
            for idx, l in enumerate(delivery_list['list']):
                delivery_data.append(DeliveryData(user=l['user'], packet=l['packet'], order=idx, route=route))
            for idx, l in enumerate(delivery_list['assigned']):
                delivery_data.append(DeliveryData(user=l['user'], packet=l['packet'], order=idx, is_extra=True, route=route))

        delivery = None
        if dboy and not Delivery.objects.filter(route=route, date=date).exists():
            delivery = Delivery(date=date, route=route, packets=delivery_list['total'], delivery_boy=dboy, km=dboy.km)

        return {
            'date': date, 'purchases': purchases, 'skipped': skipped,
            'delivery_data': delivery_data, 'delivery_data_exists': delivery_data_exists,
            'delivery': delivery, 'packets': delivery_list['total'],
        }
