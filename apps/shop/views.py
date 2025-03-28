from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import NotFound, PermissionDenied
from django.db.models import Count
from django.utils.functional import cached_property

from apps.profiles.models import Order, OrderItem, ShippingAddress
from apps.shop.models import Review, Product, Category
from apps.shop.schema_examples import PRODUCT_PARAM_EXAMPLE
from apps.shop.filters import ProductFilter
from apps.shop.serializers import (OrderItemSerializer, ToggleCartItemSerializer,
                                   CheckoutSerializer, OrderSerializer,
                                   CategorySerializer, ProductSerializer,
                                   CheckItemOrderSerializer, ReviewSerializer,
                                   CreateReviewSerializer, UpdateReviewSerializer)
from apps.sellers.models import Seller
from apps.common.permissions import IsOwner
from apps.common.paginations import CustomPagination
from apps.common.utils import set_dict_attr
from apps.common.utils import calculate_avg_rating


tags = ['shop']

class CategoriesView(APIView):
    serializer_class = CategorySerializer

    @extend_schema(
        summary='Categories fetch',
        description='This endpoint returns all categories.',
        tags=tags,
    )
    def get(self, request, *args, **kwargs):
        self.permission_classes = [permissions.AllowAny]    # Разрешение для всех пользователей
        self.check_permissions(request)                     # Проверка пермишнов

        categories = Category.objects.all()
        serializer = self.serializer_class(categories, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary='Categories create',
        description='This endpoint creates a new category',
        tags=tags,
    )
    def post(self, request, *args, **kwargs):
        self.permission_classes = [permissions.IsAdminUser]     # Разрешение только для администраторов
        self.check_permissions(request)                         # Проверка пермишнов

        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            new_category = Category.objects.create(**serializer.validated_data)
            serializer = self.serializer_class(new_category)
            return Response(serializer.data, status=200)
        else:
            return Response(serializer.errors, status=400)

class ProductsByCategoryView(APIView):
    serializer_class = ProductSerializer

    @extend_schema(
        operation_id='products_by_category',
        summary='Category Products fetch',
        description='This endpoint returns all products by category.',
        tags=tags,
    )
    def get(self, request, *args, **kwargs):
        category = Category.objects.get_or_none(slug=kwargs['slug'])
        if not category:
            return Response(data={'massage': 'Category does not exist!'}, status=404)
        products = Product.objects.select_related("category", "seller", "seller__user").filter(category=category)
        serializer = self.serializer_class(products, many=True)
        return Response(data=serializer.data, status=200)

class ProductsView(APIView):
    serializer_class = ProductSerializer
    pagination_class = CustomPagination

    @extend_schema(
        operation_id='all_products',
        summary='Product fetch',
        description='This endpoint returns all products.',
        tags=tags,
        parameters=PRODUCT_PARAM_EXAMPLE,
    )
    def get(self, request, *args, **kwargs):
        products = Product.objects.select_related("category", "seller", "seller__user").all()
        filterset = ProductFilter(request.GET, queryset=products)
        if filterset.is_valid():
            queryset = filterset.qs
            paginator = self.pagination_class()
            paginated_queryset = paginator.paginate_queryset(queryset, request)
            serializer = self.serializer_class(paginated_queryset, many=True)
            return paginator.get_paginated_response(serializer.data)
        else:
            return Response(filterset.errors, status=400)

class ProductsBySellerView(APIView):
    serializer_class = ProductSerializer

    @extend_schema(
        summary='Seller Products fetch',
        description='This endpoint returns all products by seller.',
        tags=tags,
    )
    def get(self, request, *args, **kwargs):
        seller = Seller.objects.get_or_none(slug=kwargs['slug'])
        if not seller:
            return Response(data={'massage': 'Seller does not exist!'}, status=404)
        products = Product.objects.select_related("category", "seller", "seller__user").filter(seller=seller)
        serializer = self.serializer_class(products, many=True)
        return Response(data=serializer.data, status=200)

class ProductView(APIView):
    serializer_class = ProductSerializer

    def get_object(self, slug):
        product = Product.objects.get_or_none(slug=slug)
        return product

    @extend_schema(
        operation_id='product_detail',
        summary='Product Detail fetch',
        description='This endpoint returns the details for a product via the slug.',
        tags=tags,
    )
    def get(self, request, *args, **kwargs):
        product = self.get_object(kwargs['slug'])
        if not product:
            return Response(data={'massage': 'Product does not exist!'}, status=404)
        serializer = self.serializer_class(product)
        reviews = Review.objects.filter(product=product).all()
        average_rating = calculate_avg_rating(reviews)
        response_data = {
            'product_rating': {
                'rating': average_rating
            },
            'product': serializer.data
        }
        return Response(response_data, status=200)

class CartView(APIView):
    serializer_class = OrderItemSerializer  # Указание сериализатора для сериализации элемента заказа
    permission_classes = [IsOwner]          # Использование класса IsOwner для проверки прав доступа

    """
    Получение конкретного объекта (в данном случае, элемента корзины) 
    и проверка прав доступа к этому объекту
    """
    def get_object(self, user, orderitem_id):
        orderitem = OrderItem.objects.get_or_none(user=user, id=orderitem_id)
        if orderitem is None:
            return None
        self.check_object_permissions(self.request, orderitem)
        return orderitem

    @extend_schema(
        summary='Cart Items fetch',
        description='This endpoint returns all cart items.',
        tags=tags,
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        oderitems = OrderItem.objects.filter(user=user, order=None).select_related(
            'product',
            'product__seller',
            'product__seller__user'
        )
        serializer = self.serializer_class(oderitems, many=True)
        return Response(data=serializer.data, status=200)

    @extend_schema(
        summary='Toggle Item in cart',
        description='''
            This endpoint allows a user or guest to add/update/remove an item in cart.
            If quantity is 0, the item is removed from cart.''',
        tags=tags,
    )
    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = ToggleCartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        quantity = data["quantity"]

        product = Product.objects.select_related('seller', 'seller__user').get_or_none(slug=data['slug'])
        if not product:
            return Response({'massage': 'Product doesn`t exist!'}, status=404)
        orderitem, created = OrderItem.objects.update_or_create(
            user=user,
            order_id=None,
            product=product,
            defaults={'quantity': quantity},
        )
        resp_message_substring = 'Updated in'
        status_code = 200
        if created:
            status_code = 201
            resp_message_substring = 'Added to'
        if orderitem.quantity == 0:
            resp_message_substring = 'Removed from'
            orderitem.delete()
            data = None
        if resp_message_substring != 'Removed from':
            orderitem.product = product
            serializer = self.serializer_class(orderitem)
            data = serializer.data
        return Response({'massage': f'Item{resp_message_substring} cart', 'item': data}, status=status_code)

class CheckoutView(APIView):
    serializer_class = CheckoutSerializer
    permission_classes = [IsOwner]

    def get_order_item(self, user, orderitem_id):
        orderitem = OrderItem.objects.get_or_none(user=user, id=orderitem_id)
        if orderitem is not None:
            self.check_object_permissions(self.request, orderitem)
        return orderitem

    def get_shipping_address(self, user, shipping_id):
        shipping_address = ShippingAddress.objects.get_or_none(user=user, id=shipping_id)
        if shipping_address is not None:
            self.check_object_permissions(self.request, shipping_address)
        return shipping_address

    @extend_schema(
        summary='Checkout',
        description='''
            This endpoint allows a user to create an order through which payment can then be made through.''',
        tags=tags,
    )
    def post(self, request, *args, **kwargs):
        user = request.user
        orderitems = OrderItem.objects.filter(user=user, order=None)
        if not orderitems:
            return Response({'message': 'No Items in Cart'}, status=404)

        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        shipping_id = data.get('shipping_id')
        if shipping_id:
            shipping = ShippingAddress.objects.get_or_none(id=shipping_id)
            if not shipping:
                return Response({'message': 'No shipping address with that ID'}, status=404)
        def append_shipping_details(shipping):
            fields_to_update = [
                'full_name',
                'email',
                'phone',
                'address',
                'city',
                'country',
                'zipcode',
            ]
            data = {}
            for field in fields_to_update:
                value = getattr(shipping, field)
                data[field] = value
            return data

        order = Order.objects.create(user=user, **append_shipping_details(shipping))
        orderitems.update(order=order)

        serializer = OrderSerializer(order)
        return Response({'message': 'Checkout Successful', 'order': serializer.data}, status=201)

class OrdersView(APIView):
    serializer_class = OrderSerializer
    permission_classes = [IsOwner]

    @extend_schema(
        operation_id='order_view',
        summary='Order Fetch',
        description='This endpoint returns all orders for a user.',
        tags=tags
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        orders = (
            Order.objects.filter(user=user)
            .prefetch_related('orderitems', 'orderitems__product')
            .order_by('-created_at')
        )
        serializer = self.serializer_class(orders, many=True)
        return Response(data=serializer.data, status=200)

class OrderItemView(APIView):
    serializer_class = CheckItemOrderSerializer
    permission_classes = [IsOwner]

    @extend_schema(
        operation_id='orders_items_view',
        summary='Item Orders Fetch',
        description='This endpoint returns all items orders for a particular user.',
        tags=tags,
    )
    def get(self, request, **kwargs):
        order = Order.objects.get_or_none(tx_ref=kwargs['tx_ref'])
        if not order or order.user != request.user:
            return Response(data={'massage': 'This order does not exist!'}, status=404)
        order_items = OrderItem.objects.filter(order=order)
        serializer = self.serializer_class(order_items, many=True)
        return Response(data=serializer.data, status=200)

class ReviewsView(APIView):
    """
    Реализация получения всех отзывов о продукте, оставленных разными пользователями.
    Получение данных продукта осуществляется по слагу.
    """
    serializer_class = ReviewSerializer
    pagination_class = CustomPagination

    @extend_schema(
        operation_id='reviews_by_products',
        summary='Reviews fetch',
        description='This endpoint returns all reviews of product.',
        tags=tags,
        parameters=PRODUCT_PARAM_EXAMPLE,
    )
    def get(self, request, *args, **kwargs):
        product = Product.objects.get_or_none(slug=kwargs["slug"])
        if not product:
            return Response(data={'massage': 'Product does not exist!'}, status=404)
        else:
            reviews = Review.objects.filter(product=product)
            if not reviews:
                return Response(data={'message': 'No reviews for this product yet.'}, status=404)
            else:
                average_rating = calculate_avg_rating(reviews)
                paginator = self.pagination_class()
                paginated_reviews = paginator.paginate_queryset(reviews, request)
                serializer = self.serializer_class(paginated_reviews, many=True)
                response_data = {
                    'product': {
                        'name': product.name,
                        'rating': average_rating
                    },
                    'reviews': serializer.data
                }
                return paginator.get_paginated_response(response_data)

class ReviewItemView(APIView):
    """
    Реализация получения, изменения и удаления конкретного отзыва о продукте от одного пользователя,
    прошедшего проверку на права доступа.
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsOwner]

    # Метод для получения отзыва о продукте от пользователя
    @extend_schema(
        operation_id='review_by_user',
        summary='Reviews by User',
        description='This endpoint returns all reviews for a particular user.',
        tags=tags,
    )
    def get(self, request, **kwargs):
        user = request.user
        product = Product.objects.get_or_none(slug=kwargs["slug"])
        if not product:
            return Response(data={'message': 'Product does not exist!'}, status=404)
        else:
            review = Review.objects.get(product=product, user=user, id=kwargs["uuid"])
            if not review:
                return Response(data={'message': 'No reviews from this user yet.'}, status=404)
            else:
                serializer = self.serializer_class(review)
                return Response(data={'message': 'Review retrieved successfully.', 'review': serializer.data}, status=200)

    # Метод для удаления отзыва о продукте от пользователя
    @extend_schema(
        operation_id='review_delete',
        summary='Delete Review',
        description='This endpoint deletes a review of a product via user.',
        tags=tags,
    )
    def delete(self, request, **kwargs):
        user = request.user
        product = Product.objects.get_or_none(slug=kwargs["slug"])
        if not product:
            return Response(data={'message': 'Delete is impossible, product does not exist!'}, status=404)
        else:
            review = Review.objects.get(product=product, user=user, id=kwargs["uuid"])
            if not review:
                return Response(data={'message': 'Delete is impossible, no reviews for this product yet.'}, status=404)
            else:
                review.delete()
                return Response(data={'massage': 'Reviews deleted successfully.'}, status=200)

    # Метод для обновления отзыва о продукте от пользователя
    @extend_schema(
        operation_id='review_update',
        summary='Update Review',
        description='This endpoint updates a review of a product via user.',
        tags=tags,
    )
    def put(self, request, **kwargs):
        user = request.user
        product = Product.objects.get_or_none(slug=kwargs["slug"])
        review = Review.objects.get_or_none(product=product, user=user, id=kwargs["uuid"])

        if not product:
            return Response(data={'message': 'Change is impossible, product does not exist!'}, status=404)

        if not review:
            return Response(data={'message': 'Change is impossible, no reviews for this product yet.'}, status=404)

        serializer = UpdateReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        review = set_dict_attr(review, data)
        review.save()
        serializer = self.serializer_class(review)
        return Response(data=serializer.data, status=200)

class CreateReviewView(APIView):
    """
    Реализация создания отзыва о продукте от одного пользователя,
    прошедшего проверку на права доступа.
    """
    serializer_class = CreateReviewSerializer
    permission_classes = [IsOwner]

    # Метод для создания отзыва о продукте от пользователя
    @extend_schema(
        operation_id='review_create',
        summary='Create Review',
        description='This endpoint creates a new review of a product.',
        tags=tags,
    )
    def post(self, request, **kwargs):
        user = request.user
        product = Product.objects.get_or_none(slug=kwargs["slug"])
        if not product:
            return Response(data={'message': 'Create is impossible, product does not exist!'}, status=404)
        else:
            if product.reviews.filter(user=request.user).exists():
                return Response({'message': 'Review already exists!'}, status=400)
            else:
                serializer = self.serializer_class(data=request.data)
                if serializer.is_valid():
                    new_review = Review.objects.create(user=user, product=product, **serializer.validated_data)
                    serializer = self.serializer_class(new_review)
                    return Response(data=serializer.data, status=201)
                else:
                    return Response(data=serializer.errors, status=400)