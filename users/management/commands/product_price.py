from django.core.management.base import BaseCommand, CommandError

from users.models import Product


class Command(BaseCommand):
    help = "List products, or set a product's price: product_price [<id> <new_price>]"

    def add_arguments(self, parser):
        parser.add_argument('product_id', nargs='?', type=int)
        parser.add_argument('price', nargs='?')

    def handle(self, *args, **options):
        pid, price = options['product_id'], options['price']
        if pid is None:
            for p in Product.objects.order_by('id'):
                self.stdout.write(f"{p.id}\t{p.name}\t{p.uom}\t{p.price}")
            return
        if price is None:
            raise CommandError("Give new price: product_price <id> <new_price>")
        try:
            p = Product.objects.get(id=pid)
        except Product.DoesNotExist:
            raise CommandError(f"No product with id {pid}")
        old = p.price
        p.price = price
        p.save()
        self.stdout.write(self.style.SUCCESS(f"{p.name}: {old} -> {p.price}"))
