"""
Test script: read all records from the Product model and print them
"""
from load_django import *
from parser_app.models import *

for product in Product.objects.all():
    print(product.id, product.full_name, product.source)