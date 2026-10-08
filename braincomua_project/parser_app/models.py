from django.contrib.postgres.fields import ArrayField
from django.db import models


class Product(models.Model):
    # Main product data
    full_name = models.CharField(max_length=255, null=True)
    color = models.CharField(max_length=100, null=True)
    memory = models.CharField(max_length=50, null=True)
    manufacturer = models.CharField(max_length=100, null=True)
    price = models.IntegerField(null=True)
    sale_price = models.IntegerField(null=True)
    product_code = models.CharField(max_length=50, null=True)
    reviews_count = models.IntegerField(null=True)
    screen_diagonal = models.CharField(max_length=50, null=True)
    display_resolution = models.CharField(max_length=50, null=True)

    # Additional data: lists and nested structures
    photos = ArrayField(models.CharField(max_length=500, null=True), null=True)
    characteristics = models.JSONField(null=True)

    # Service fields
    link = models.URLField(max_length=500, null=True)
    source = models.CharField(max_length=20, null=True)  # bs4 / selenium / playwright

    def __str__(self):
        return self.full_name or f'Product {self.pk}'
