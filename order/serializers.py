from rest_framework import serializers

from system.models import CurrencyPair, ExchangeAccount, Exchange
from .models import Order, OrderStatus, Wallet, TimeInForce, OrderSide, OrderType

class CreateOrderSerializer(serializers.Serializer):
    exchange_account_id = serializers.IntegerField()
    side = serializers.ChoiceField(choices=OrderSide.choices)
    type = serializers.ChoiceField(choices=OrderType.choices)
    symbol = serializers.CharField()
    price = serializers.DecimalField(max_digits=32, decimal_places=12, required=False)
    size = serializers.DecimalField(max_digits=32, decimal_places=8, required=False)
    amount = serializers.DecimalField(max_digits=32, decimal_places=12, required=False)
    base_currency = serializers.CharField(allow_blank=True)
    quote_currency = serializers.CharField(allow_blank=True)
    time_in_force = serializers.ChoiceField(choices=TimeInForce.choices, default=TimeInForce.GTC, required=False)

    def save(self, validated_data, operator):
        currency_pair = validated_data['symbol'].split('-')
        validated_data['base_currency'] = currency_pair[0]
        validated_data['quote_currency'] = currency_pair[1]
        if validated_data['type'] == OrderType.MARKET:
            validated_data['time_in_force'] = TimeInForce.FOK
        return Order.objects.create(**validated_data,operator=operator)
    
class CancelOrderSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()

    def validate_order_id(self, order_id):
        try:
            order = Order.objects.get(id=order_id)
            if order.status == OrderStatus.FILLED:
                raise serializers.ValidationError("Order has been filled")
            if order.status == OrderStatus.CANCELLED:
                raise serializers.ValidationError("Order has been cancelled")
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order does not exist")
        return order_id


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['currency', 'available']


class CurrencyPairSerializer(serializers.ModelSerializer):
    last_price = serializers.SerializerMethodField("_get_last_price")

    def _get_last_price(self, obj):
        price_mapping = self.context.get('price_mapping', {})
        prices = price_mapping.get(obj.exchange_account.exchange.code, {})
        return prices.get(obj.symbol, 0)

    class Meta:
        model = CurrencyPair
        fields = ['base_currency', 'quote_currency', 'symbol', 'base_min_size', 'quote_min_size', 'last_price']

class AccountDetailSerializer(serializers.ModelSerializer):
    wallets = WalletSerializer(many=True)
    currency_pairs = CurrencyPairSerializer(many=True)
    
    class Meta:
        model = ExchangeAccount
        fields = ['id', 'name', 'wallets', 'currency_pairs']

class ExchangeDetailSerializer(serializers.ModelSerializer):
    exchange_accounts = AccountDetailSerializer(many=True)

    class Meta:
        model = Exchange
        fields = ['name', 'code', 'symbol_delimiter', 'exchange_accounts']