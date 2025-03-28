from django.db import models
import uuid
from autoslug import AutoSlugField
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.common.models import BaseModel, IsDeletedModel
from apps.sellers.models import Seller
from apps.accounts.models import User


class Category(BaseModel):
    """
    Represents a product category.

    Attributes:
        name (str): The category name, unique for each instance.
        slug (str): The slug generated from the name, used in URLs.
        image (ImageField): An image representing the category.

    Methods:
        __str__():
            Returns the string representation of the category name.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = AutoSlugField(populate_from="name", unique=True, always_update=True)
    image = models.ImageField(upload_to='category_images/')

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

class Product(IsDeletedModel):
    """
    Represents a product listed for sale.

    Attributes:
        seller (ForeignKey): The user who is selling the product.
        name (str): The name of the product.
        slug (str): The slug generated from the name, used in URLs.
        desc (str): A description of the product.
        price_old (Decimal): The original price of the product.
        price_current (Decimal): The current price of the product.
        category (ForeignKey): The category to which the product belongs.
        in_stock (int): The quantity of the product in stock.
        image1 (ImageField): The first image of the product.
        image2 (ImageField): The second image of the product.
        image3 (ImageField): The third image of the product.
    """
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='products', null=True)
    name = models.CharField(max_length=100)
    slug = AutoSlugField(populate_from="name", unique=True, db_index=True)
    desc = models.TextField()
    price_old = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    price_current = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    in_stock = models.IntegerField(default=5)

    # Only 3 images are allowed
    image1 = models.ImageField(upload_to='product_images/')
    image2 = models.ImageField(upload_to='product_images/', blank=True)
    image3 = models.ImageField(upload_to='product_images/', blank=True)

    def __str__(self):
        return str(self.name)

class Review(IsDeletedModel):
    """
    Represents a review for a product.

    Attributes:
        user (ForeignKey): The user who wrote the review.
        product (ForeignKey): The product being reviewed.
        rating (int): The rating given by the user.
        text (str): The content of the review.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(default=0, validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField(max_length=200)

    def __str__(self):
        return f"Review by {self.user.full_name} for {self.product.name}"