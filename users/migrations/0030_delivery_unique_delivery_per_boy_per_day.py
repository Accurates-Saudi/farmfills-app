from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0029_user_balance'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='delivery',
            constraint=models.UniqueConstraint(fields=('delivery_boy', 'date'), name='unique_delivery_per_boy_per_day'),
        ),
    ]
