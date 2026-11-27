from datetime import datetime, timedelta

from django.core import management
from django.core.management.base import BaseCommand

from users.management.commands.today_transaction import create_purchases, delivery_boys_by_route


class Command(BaseCommand):
    help = ('Creates missing daily purchases for a date range (inclusive), then recalculates '
            'the balance of every affected customer once. Days/customers already billed are skipped.')

    def add_arguments(self, parser):
        parser.add_argument('start', type=str, help='YYYY-MM-DD')
        parser.add_argument('end', type=str, nargs='?', default=datetime.today().strftime('%Y-%m-%d'),
                            help='YYYY-MM-DD (default: today)')

    def handle(self, *args, **options):
        day = datetime.strptime(options['start'], '%Y-%m-%d').date()
        end = datetime.strptime(options['end'], '%Y-%m-%d').date()
        dboy_by_route = delivery_boys_by_route()

        touched = set()
        while day <= end:
            users = create_purchases(day, dboy_by_route)
            touched |= users
            self.stdout.write(f'{day}: created {len(users)} purchases')
            day += timedelta(days=1)

        self.stdout.write(f'Recalculating balances for {len(touched)} customers...')
        for i, user_id in enumerate(sorted(touched), 1):
            management.call_command('update_transactions_balance', str(user_id), verbosity=0)
            if i % 100 == 0:
                self.stdout.write(f'  {i}/{len(touched)}')
        self.stdout.write(self.style.SUCCESS('Done'))
