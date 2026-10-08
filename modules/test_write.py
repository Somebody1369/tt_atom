"""
Test script: write one record to the Product model
"""
from load_django import *
from parser_app.models import *

product = Product.objects.create(full_name='test product', source='test')
print(f'Created: {product.id} {product.full_name}')