import json
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import generics

from system.models import ExchangeAccount, Exchange
from .serializers import AccountDetailSerializer, CreateOrderSerializer, CancelOrderSerializer, ExchangeDetailSerializer

from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import APIException
from django.core.cache import cache
from django_redis import get_redis_connection


from .models import Order, OrderStatus
from .tasks import (
    place_order, place_kubocin_order,
    place_bybit_order, place_mexc_order,
    place_okx_order,
    cancel_order, cancel_kucoin_order,
    cancel_bybit_order, cancel_mexc_order,
    cancel_okx_order,
    place_binance_order, cancel_binance_order
)

class CreateOrderView(generics.CreateAPIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = CreateOrderSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save(serializer.validated_data, operator=request.user)
        if order.exchange == 'BYBIT':
            place_bybit_order.delay(order.id)
        if order.exchange == 'KUCOIN':
            place_kubocin_order.delay(order.id)
        if order.exchange == 'GATEIO':
            place_order.delay(order.id)
        if order.exchange == 'MEXC':
            place_mexc_order.delay(order.id)
        if order.exchange == 'OKX':
            place_okx_order.delay(order.id)
        if order.exchange == 'BINANCE':
            place_binance_order.delay(order.id)
        return Response('{"OK": True}', status=201)

class OrderIsFilledException(APIException):
    status_code = 400
    default_detail = 'Order has been filled'
    default_code = 'order_filled'

class OrderIsCancelledException(APIException):
    status_code = 400
    default_detail = 'Order has been cancelled'
    default_code = 'order_cancelled'

class CancelOrderView(generics.DestroyAPIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    queryset = Order.objects.all()

    def get_object(self):
        obj = super().get_object()
        if obj.status == OrderStatus.FILLED:
            raise OrderIsFilledException()
        if obj.status == OrderStatus.CANCELLED:
            raise OrderIsCancelledException()
        return obj
    
    def perform_destroy(self, instance):
        instance.status = OrderStatus.WAITING_FOR_CANCEL
        instance.save()
        if instance.exchange == 'BYBIT':
            cancel_bybit_order.delay(instance.id)
        if instance.exchange == 'KUCOIN':
           cancel_kucoin_order.delay(instance.id)
        if instance.exchange == 'GATEIO':
            cancel_order.delay(instance.id)
        if instance.exchange == 'MEXC':
            cancel_mexc_order.delay(instance.id)
        if instance.exchange == 'OKX':
            cancel_okx_order.delay(instance.id)
        if instance.exchange == 'BINANCE':
            cancel_binance_order.delay(instance.id)
        

class ListAccountDetailView(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = AccountDetailSerializer
    
    def get(self, request, format=None):
        accounts = ExchangeAccount.objects.filter(is_active=True)
        serializer = self.serializer_class(accounts, many=True)
        return Response(serializer.data, status=200)


class ListExchangeDetailView(APIView):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = ExchangeDetailSerializer
    
    def get(self, request, format=None):
        exchanges = Exchange.objects.filter(is_active=True)
        price_mapping = self._get_last_price_mapping(exchanges)
        serializer = self.serializer_class(exchanges, many=True, context={'price_mapping': price_mapping})
        return Response(serializer.data, status=200)
    
    def _get_last_price_mapping(self, exchanges):
        conn = get_redis_connection()
        keys = [f"gateio:tickers".lower() for exchange in exchanges]
        pipe = conn.pipeline()
        for key in keys:
            pipe.hgetall(key)
        results = pipe.execute()
        price_mapping = {}
        for idx, result in enumerate(results):
            price_mapping[exchanges[idx].code] = result
        return price_mapping
