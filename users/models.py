from django.db import models
from django import forms


PAYMENT_TYPES =(
    ("prepaid", "Prepaid"),
    ("postpaid", "Postpaid")
)


#user types model
class UserType(models.Model):

    id = models.AutoField(primary_key=True)

    name = models.CharField(max_length=30)

    price_variation = models.DecimalField(max_digits=20, decimal_places=2, null=True)

    payment_type = models.CharField(max_length=50, blank=True, null=True, choices = PAYMENT_TYPES)

    suspend = models.BooleanField()

    def __str__(self):
        return self.name



# area model
class Area(models.Model):

    id = models.AutoField(primary_key=True)

    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name



#routes model
class Route(models.Model):

    id = models.AutoField(primary_key=True)

    name = models.CharField(max_length=30)

    code = models.CharField(max_length=20)

    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        verbose_name="route area",
        null=True
    )

    def __str__(self):
        return self.name


ADDRESS_TYPES = [
    ("house", "House"),
    ("apartment", "Apartment")
]

PAYMENT_MODES = [
    ("online", "Online"),
    ("cash", "Cash")
]

STATUS_MODES = [
    ("cleared", "Cleared"),
    ("not cleared", "Not Cleared")
]


#user model
class User(models.Model):

    id = models.AutoField(primary_key=True)

    name = models.CharField(max_length=255)

    mobile = models.CharField(max_length=255)

    user_type = models.ForeignKey(
        UserType,
        on_delete=models.CASCADE,
        verbose_name="customer type",
    )

    address_type = models.CharField(max_length=50, blank=True, null=True, choices = ADDRESS_TYPES)

    house_name = models.CharField(max_length=255, blank=True, null=True)

    house_no = models.CharField(max_length=255, blank=True, null=True)

    street = models.CharField(max_length=255, blank=True, null=True)

    landmark = models.TextField(blank=True, null=True)

    apartment_name = models.CharField(max_length=255, blank=True, null=True)

    tower = models.CharField(max_length=255, blank=True, null=True)

    floor = models.CharField(max_length=255, blank=True, null=True)

    door = models.CharField(max_length=255, blank=True, null=True)

    location = models.CharField(max_length=255, blank=True, null=True)

    delivery_name = models.CharField(max_length=255)

    route_order = models.IntegerField()

    payment_mode = models.CharField(max_length=50, default='cleared', choices = PAYMENT_MODES)

    email = models.CharField(max_length=255, blank=True, null=True)

    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        verbose_name="delivery route",
        blank=True,
        null=True
    )

    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        verbose_name="delivery area",
        blank=True,
        null=True
    )

    status = models.CharField(max_length=50, blank=True, null=True, choices = STATUS_MODES)

    bill_send_date = models.DateTimeField(blank=True, null=True)

    last_transaction = models.IntegerField(default=0)

    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    def __str__(self):
        return self.name + ' ' + self.delivery_name


VEHICLE_CHOICES = [
    ("bike", "Bike"),
    ("scooter", "Scooter")
]


# staffs model
class Staff(models.Model):

    id = models.AutoField(primary_key=True)

    name = models.CharField(max_length=30)

    uname = models.CharField(max_length=30)

    password = models.CharField(max_length=250)

    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        verbose_name="delivery route",
        blank=True, 
        null=True
    )

    delivery = models.BooleanField()

    dispatch = models.BooleanField()

    cash_collection = models.BooleanField()

    follow_up = models.BooleanField()

    billing = models.BooleanField()

    admin = models.BooleanField()

    vendor = models.BooleanField()

    vehicle = models.CharField(max_length=50, blank=True, null=True, choices = VEHICLE_CHOICES)

    km = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)

    ip = models.CharField(max_length=50, blank=True, null=True, choices = VEHICLE_CHOICES)

    def __str__(self):
        return self.name


# managers model
class Manager(models.Model):

    id = models.AutoField(primary_key=True)

    name = models.CharField(max_length=30)

    uname = models.CharField(max_length=30)

    password = models.CharField(max_length=250)

    routes = models.ManyToManyField(Route)

    def __str__(self):
        return self.name


# products model
class Product(models.Model):

    id = models.AutoField(primary_key=True)

    name = models.CharField(max_length=30)

    uom = models.CharField(max_length=30)

    price = models.DecimalField(max_digits=20, decimal_places=2)

    def __str__(self):
        return self.name


PAYMENT_MODES =(
    ("online", "Online"),
    ("cash", "Cash"),
    ("bank transfer", "Bank Transfer")
)


# payments model
class Payment(models.Model):

    id = models.AutoField(primary_key=True)

    transaction_id = models.IntegerField(default=0)

    date = models.DateTimeField()

    amount = models.DecimalField(max_digits=20, decimal_places=2)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="payment user",
    )

    mode = models.CharField(max_length=50, blank=True, null=True, choices = PAYMENT_MODES)

    order_id = models.CharField(max_length=50, blank=True, null=True)

    payment_id = models.CharField(max_length=50, blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    paid = models.BooleanField()

    balance = models.DecimalField(max_digits=20, decimal_places=2)

    def get_transaction_type(self):
        transaction_type = 'payment'
        return transaction_type


REFUND_REASONS =(
    ("not delivered", "Not delivered"),
    ("leaked", "Leaked"),
    ("Spoiled", "Spoiled")
)


# refund model
class Refund(models.Model):

    id = models.AutoField(primary_key=True)

    transaction_id = models.IntegerField(default=0)

    date = models.DateTimeField()

    amount = models.DecimalField(max_digits=20, decimal_places=2)

    quantity = models.DecimalField(max_digits=20, decimal_places=2)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="refund user",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name="extra product",
    )

    reason = models.CharField(max_length=50, blank=True, null=True, choices = REFUND_REASONS)

    balance = models.DecimalField(max_digits=20, decimal_places=2)

    def get_transaction_type(self):
        transaction_type = 'refund'
        return transaction_type


# extra
class Extra(models.Model):

    id = models.AutoField(primary_key=True)

    transaction_id = models.IntegerField(default=0)

    date = models.DateTimeField()

    amount = models.DecimalField(max_digits=20, decimal_places=2)

    quantity = models.DecimalField(max_digits=20, decimal_places=2)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="extra user",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name="extra product",
    )

    note = models.TextField(blank=True, null=True)

    balance = models.DecimalField(max_digits=20, decimal_places=2)

    def get_transaction_type(self):
        transaction_type = 'extra'
        return transaction_type


# purchase model
class Purchase(models.Model):

    id = models.AutoField(primary_key=True)

    transaction_id = models.IntegerField(default=0)

    date = models.DateTimeField()

    amount = models.DecimalField(max_digits=20, decimal_places=2)

    quantity = models.DecimalField(max_digits=20, decimal_places=2)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="purchase user",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name="purchase product",
    )

    delivered_by = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        verbose_name="delivery boy",
        blank=True, 
        null=True
    )

    balance = models.DecimalField(max_digits=20, decimal_places=2)

    def get_transaction_type(self):
        transaction_type = 'purchase'
        return transaction_type


SUB_TYPES =(
    ("daily", "Daily"),
    ("alternate", "Alternate"),
    ("weekly", "Weekly"),
    ("custom", "Custom Interval")
)

CREATED_BY_CHOICES = [
    ("customer", "Customer"),
    ("admin", "Admin"),
    ("manager", "Manager")
]

# subscription model
class Subscription(models.Model):

    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="subscription user",
    )

    start_date = models.DateField()

    end_date = models.DateField(null=True, blank=True)

    sub_type = models.CharField(max_length=50, choices = SUB_TYPES)

    daily_day1 = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    daily_day2 = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    alternate_quantity = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    custom_quantity = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    custom_interval = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    weekly_mon = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    weekly_tue = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    weekly_wed = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    weekly_thu = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    weekly_fri = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    weekly_sat = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    weekly_sun = models.DecimalField(blank=True, null=True, max_digits=20, decimal_places=2)

    created_by = models.CharField(max_length=50, choices=CREATED_BY_CHOICES, null=True, blank=True)

    edited_by = models.CharField(max_length=50, choices=CREATED_BY_CHOICES, null=True, blank=True)
    
    def __str__(self):
        if self.end_date is None:
            return self.user.delivery_name + ' ' + self.sub_type + ' from ' + self.start_date.strftime("%b %d, %Y")
        else:
            return self.user.delivery_name + ' ' + self.sub_type + ' from ' + self.start_date.strftime("%b %d, %Y") + ' to ' + self.end_date.strftime("%b %d, %Y")


# otp model
class Otp(models.Model):

    id = models.AutoField(primary_key=True)

    mobile = models.CharField(max_length=30)

    otp = models.CharField(max_length=20)

    ip = models.CharField(max_length=20)

    def __str__(self):
        return self.mobile + ' - ' + self.otp


# vacation model
class Vacation(models.Model):

    id = models.AutoField(primary_key=True)

    start_date = models.DateField()

    end_date = models.DateField(null=True, blank=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="vacation user",
    )

    created_by = models.CharField(max_length=50, choices=CREATED_BY_CHOICES, null=True, blank=True)

    edited_by = models.CharField(max_length=50, choices=CREATED_BY_CHOICES, null=True, blank=True)

    def __str__(self):
        if self.end_date is None:
            return self.user.delivery_name + ' from ' + self.start_date.strftime("%b %d, %Y")
        else:
            return self.user.delivery_name + ' from ' + self.start_date.strftime("%b %d, %Y") + ' to ' + self.end_date.strftime("%b %d, %Y")


# extra\less model
class ExtraLess(models.Model):

    id = models.AutoField(primary_key=True)

    start_date = models.DateField()

    end_date = models.DateField(null=True, blank=True)

    quantity = models.DecimalField(max_digits=20, decimal_places=2)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="extraless user",
    )

    created_by = models.CharField(max_length=50, choices=CREATED_BY_CHOICES, null=True, blank=True)

    edited_by = models.CharField(max_length=50, choices=CREATED_BY_CHOICES, null=True, blank=True)

    def __str__(self):
        return self.user.delivery_name + ' from ' + self.start_date.strftime("%b %d, %Y") + ' to ' + self.end_date.strftime("%b %d, %Y") 


# delivery model
class Delivery(models.Model):

    id = models.AutoField(primary_key=True)

    start_time = models.TimeField(null=True, blank=True)

    end_time = models.TimeField(null=True, blank=True)

    dispatch_start_time = models.TimeField(null=True, blank=True)

    dispatch_end_time = models.TimeField(null=True, blank=True)

    date = models.DateField()

    delivery_boy = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        verbose_name="delivery boy",
        related_name="+"
    )

    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        verbose_name="delivery route",
        null=True
    )

    packets = models.DecimalField(max_digits=20, decimal_places=2)
    packets_variation = models.DecimalField(max_digits=20, decimal_places=2, null=True)

    km = models.DecimalField(max_digits=20, decimal_places=2, null=True)
    km_variation = models.DecimalField(max_digits=20, decimal_places=2, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['delivery_boy', 'date'], name='unique_delivery_per_boy_per_day'),
        ]


# dispatch model
class Dispatch(models.Model):
    id = models.AutoField(primary_key=True)

    start_time = models.TimeField(null=True)

    end_time = models.TimeField(null=True)

    date = models.DateField()

    packets = models.DecimalField(max_digits=20, decimal_places=2)

    packets_variation = models.DecimalField(max_digits=20, decimal_places=2, null=True)


# route assigning
class RouteAssign(models.Model):
    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="assigned user",
    )

    from_route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        verbose_name="assigned from route",
        related_name="+",
        null=True
    )

    to_route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        verbose_name="assigned to route",
        related_name="+",
        null=True
    )


# follow up
class FollowUp(models.Model):
    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="assigned user",
    )

    note = models.TextField(null=True, blank=True)

    admin_note = models.TextField(null=True, blank=True)

    last_date = models.DateField(null=True, blank=True)

    next_date = models.DateField(null=True, blank=True)


# message
class Message(models.Model):
    id = models.AutoField(primary_key=True)

    title = models.CharField(max_length=30)

    content = models.TextField()

    created_date = models.DateTimeField(auto_now_add=True)


# message sent record
class MessageRecord(models.Model):
    id = models.AutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="messaged user",
    )

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        verbose_name="message sent",
    )

    send_date = models.DateTimeField(auto_now_add=True)