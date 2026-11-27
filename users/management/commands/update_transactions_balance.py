from django.core.management.base import BaseCommand
from django.db import transaction

from users.models import Purchase, User, Payment, Refund, Extra


class Command(BaseCommand):
    help = 'Recalculates the running balance of every transaction of a customer'

    def add_arguments(self, parser):
        parser.add_argument('id', type=int)

    def handle(self, *args, **options):
        user = User.objects.get(id=options['id'])

        groups = {
            Purchase: list(Purchase.objects.filter(user=user)),
            Payment: list(Payment.objects.filter(user=user, paid=True)),
            Refund: list(Refund.objects.filter(user=user)),
            Extra: list(Extra.objects.filter(user=user)),
        }
        transaction_data = sorted(
            (t for rows in groups.values() for t in rows), key=lambda k: k.date
        )

        balance = 0
        transaction_id = 0
        changed = {model: [] for model in groups}

        for t in transaction_data:
            transaction_id += 1
            kind = t.get_transaction_type()
            if kind in ('payment', 'refund'):
                balance += t.amount
            elif kind in ('purchase', 'extra'):
                balance -= t.amount
            if t.transaction_id != transaction_id or t.balance != balance:
                t.transaction_id = transaction_id
                t.balance = balance
                changed[type(t)].append(t)

        # Only write the rows whose values actually changed, in bulk.
        with transaction.atomic():
            for model, rows in changed.items():
                if rows:
                    model.objects.bulk_update(rows, ['transaction_id', 'balance'], batch_size=500)
            user.balance = balance
            user.last_transaction = transaction_id
            user.save(update_fields=['balance', 'last_transaction'])
