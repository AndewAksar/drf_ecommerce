from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework.pagination import PageNumberPagination

from apps.profiles.models import Order, OrderItem, ShippingAddress
from apps.shop.models import Category, Product
from apps.shop.schema_examples import PRODUCT_PARAM_EXAMPLE
from apps.shop.filters import ProductFilter
from apps.shop.serializers import (OrderItemSerializer, ToggleCartItemSerializer,
                                   CheckoutSerializer, OrderSerializer,
                                   CategorySerializer, ProductSerializer,
                                   CheckItemOrderSerializer)
from apps.sellers.models import Seller
from apps.common.permissions import IsOwner
from apps.common.paginations import CustomPagination


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
        category = Category.objects.get_or_none(clug=kwargs['slug'])
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
        return Response(data=serializer.data, status=200)

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
