from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import ugettext_lazy as _
from .managers import CustomUserManager
from django.contrib.auth import get_user_model
# from django.core.validators import FileExtensionValidator


class CustomUser(AbstractUser):
    username = None
    email = models.EmailField(_('email address'), unique=True,)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['password']
    objects = CustomUserManager()

    profile = models.TextField(default="Blank")
    position = models.CharField(max_length=25, default="Должность не указана")
    share_points = models.CharField(max_length=10, default=0)
    personal_points = models.CharField(max_length=10, default=0)
    is_teamlead = models.BooleanField(default=0)
    image = models.ImageField(upload_to='images/avatars', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


    # REQUIRED_FIELDS = ['first_name', 'last_name', "status", "is_staff", "points", "profile"]

class Category(models.Model):
    name = models.CharField(max_length=64, unique=True)
    values = models.CharField(max_length=64, default='1,2,3,4,5,6,7,8,9,10')


class Transaction(models.Model):

    # ignore when delete not cascade!
    from_user = models.ForeignKey(to=get_user_model(), on_delete=models.CASCADE, related_name="from_user")
    to_user = models.ForeignKey(to=get_user_model(), on_delete=models.CASCADE, related_name="to_user")
    category = models.ForeignKey(to=Category, on_delete=models.CASCADE)
    comment = models.TextField(default="")
    amount = models.CharField(max_length=10)
    created_at = models.DateTimeField(auto_now_add=True)


class Product(models.Model):
    name = models.CharField(max_length=64)
    description = models.TextField(default="")
    price = models.CharField(max_length=8)
    quantity = models.CharField(max_length=8)
    in_stock = models.BooleanField(default=1)
    image = models.ImageField('Изображение', upload_to='images/products')


# class ProductImage(models.Model):
#     product = models.ForeignKey(Product, verbose_name='Товар', related_name='images', on_delete=models.CASCADE)
#     image = models.ImageField('Изображение', upload_to='images')


class FeedbackMessage(models.Model):
    topic = models.CharField(max_length=64)
    text = models.TextField()
    author = models.ForeignKey(to=get_user_model(), on_delete=models.CASCADE)
    closed = models.BooleanField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class Order(models.Model):
    customer = models.ForeignKey(to=get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=1)
    total = models.CharField(max_length=8)



class OrderProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

    class Meta:
        unique_together = ('order', 'product')

class UserBadge(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    badge = models.CharField(max_length=64)

    class Meta:
        unique_together = ('user', 'badge')