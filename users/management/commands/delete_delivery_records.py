"""
Delete a day's (or several days') delivery records, optionally for one route.

Replaces the manual pgAdmin SQL:

    DELETE FROM users_purchase p USING users_user u
        WHERE u.id = p.user_id AND date(p.date) = '...' AND u.route_id = N
    DELETE FROM delivery_deliverydata WHERE date(date) = '...' AND route_id = N
    DELETE FROM users_delivery       WHERE date(date) = '...' AND route_id = N
    DELETE FROM users_dispatch       WHERE date(date) = '...'   (all routes only)

Usage (dry run by default, nothing is deleted until --apply):

    python3 manage.py delete_delivery_records 2025-06-21
    python3 manage.py delete_delivery_records 2025-06-21 2025-06-22 --route 4
    python3 manage.py delete_delivery_records 2025-06-21 --route "Route name"
    python3 manage.py delete_delivery_records 2025-06-21 --route 4 --apply
    python3 manage.py delete_delivery_records 2025-06-21 --apply --recalc-balance
"""
from datetime import datetime

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from delivery.models import DeliveryData
from users.models import Delivery, Dispatch, Purchase, Route


class Command(BaseCommand):
    help = "Delete purchases, delivery data, deliveries (and dispatches) for given date(s), optionally for one route"

    def add_arguments(self, parser):
        parser.add_argument('dates', nargs='+', help='One or more dates, YYYY-MM-DD')
        parser.add_argument('--route', help='Route id or route name. Omit to delete for ALL routes')
        parser.add_argument('--apply', action='store_true', help='Actually delete (default is dry run)')
        parser.add_argument('--recalc-balance', action='store_true',
                            help='After deleting, run run_all_customers_balance')
        parser.add_argument('--yes', action='store_true', help='Skip the confirmation prompt')

    def handle(self, *args, **options):
        try:
            dates = [datetime.strptime(d, '%Y-%m-%d').date() for d in options['dates']]
        except ValueError as e:
            raise CommandError(f'Bad date: {e}')

        route = None
        if options['route']:
            r = options['route']
            qs = Route.objects.filter(id=r) if r.isdigit() else Route.objects.filter(name=r)
            route = qs.first()
            if route is None:
                raise CommandError(f'Route not found: {r}')

        purchases = Purchase.objects.filter(date__date__in=dates)
        delivery_data = DeliveryData.objects.filter(date__in=dates)
        deliveries = Delivery.objects.filter(date__in=dates)
        dispatches = Dispatch.objects.filter(date__in=dates)

        if route:
            purchases = purchases.filter(user__route=route)
            delivery_data = delivery_data.filter(route=route)
            deliveries = deliveries.filter(route=route)
            dispatches = Dispatch.objects.none()  # dispatch has no route, only wiped for all-route runs

        targets = [
            ('users_purchase', purchases),
            ('delivery_deliverydata', delivery_data),
            ('users_delivery', deliveries),
            ('users_dispatch', dispatches),
        ]

        scope = f'route "{route}" (id {route.id})' if route else 'ALL routes'
        self.stdout.write(f'Dates : {", ".join(str(d) for d in dates)}')
        self.stdout.write(f'Scope : {scope}')
        for name, qs in targets:
            self.stdout.write(f'  {name:<24} {qs.count():>8} rows')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('DRY RUN. Re-run with --apply to delete.'))
            return

        if not options['yes']:
            reply = input("Type 'delete' to continue: ")
            if reply.strip() != 'delete':
                self.stdout.write('aborted.')
                return

        with transaction.atomic():
            for name, qs in targets:
                deleted, _ = qs.delete()
                self.stdout.write(self.style.SUCCESS(f'  deleted {deleted} from {name}'))

        if options['recalc_balance']:
            self.stdout.write('Recalculating all customer balances...')
            call_command('run_all_customers_balance')
