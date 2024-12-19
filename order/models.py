from django.db import models
from system.models import ExchangeAccount, Exchange, Traders

from gate_api import Order as GateIoOrder
from decimal import Decimal

class WalletType(models.TextChoices):
    SPOT = "spot", "Spot"
    MARGIN = "margin", "Margin"
    FUTURE = "future", "Future"
    SWAP = "swap", "Swap"

class OrderType(models.TextChoices):
    LIMIT = "limit", "Limit"
    MARKET = "market", "Market"
    IOC = "ioc", "Immediate Or Cancel"
    POST_ONLY = "post_only", "Post Only"
    ICEBERG = "iceberg", "Iceberg"


class OrderStatus(models.TextChoices):
    CREATED = "created", "Created"
    WAITING_FOR_CANCEL = "waiting_for_cancel", "Waiting For Cancel"
    CANCELLIING = "cancelling", "Cancelling"
    OPEN = "open", "Open"
    FILLED = "filled", "Filled"
    CANCELLED = "cancelled", "Cancelled"
    CLOSED = "closed", "Closed"
    ERROR = "error", "Error"
    REJECTED = "rejected", "Rejected"
    PARTIALLY_FILLED_CANCELED = "partially_filled_canceled", "Partially Filled Canceled"
    PARTIALLY_FILLED = "partially_filled", "Partially Filled"
    PARTIALLY_CANCELED = "partially_canceled", "Partially Canceled"
    MMP_CANCELLED = "mmp_cancelled", "MMP Cancelled"



class OrderSide(models.TextChoices):
    BUY = "buy", "Buy"
    SELL = "sell", "Sell"


class SymbolDelimiter(models.TextChoices):
    UNDERSCORE = "_", "_"
    SLASH = "/", "/"
    DASH = "-", "-"


class TimeInForce(models.TextChoices):
    GTC = "gtc", "(GTC) Good Till Cancelled"
    IOC = "ioc", "(IOC) Immediate Or Cancel"
    FOK = "fok", "(FOK) Fill Or Kill"
    POC = "poc", "(POC) Pending Or Cancelled"


# Create your models here.
class Order(models.Model):
    order_id = models.CharField(max_length=100, default="")
    order_code = models.CharField(max_length=28, default="")
    exchange = models.CharField(max_length=32)
    exchange_account = models.ForeignKey(ExchangeAccount, on_delete=models.DO_NOTHING)
    symbol = models.CharField(max_length=16)
    symbol_delimiter = models.CharField(choices=SymbolDelimiter.choices, max_length=16, default=SymbolDelimiter.DASH)
    type = models.CharField(choices=OrderType.choices, max_length=16)
    account_type = models.CharField(max_length=32, blank=True, null=True)
    base_currency = models.CharField(max_length=8)
    quote_currency = models.CharField(max_length=8)
    side = models.CharField(choices=OrderSide.choices, max_length=16)
    size = models.DecimalField(max_digits=32, decimal_places=8, blank=True, null=True)
    amount = models.DecimalField(max_digits=32, decimal_places=12, blank=True, null=True)
    price = models.DecimalField(max_digits=32, decimal_places=12, blank=True, null=True)
    time_in_force = models.CharField(
        choices=TimeInForce.choices, default=TimeInForce.GTC, max_length=32
    )
    iceberg = models.BooleanField(default=False)
    status = models.CharField(
        choices=OrderStatus.choices, max_length=100, default=OrderStatus.CREATED
    )
    fee = models.DecimalField(max_digits=32, decimal_places=8, blank=True, null=True)
    fee_currency = models.CharField(max_length=8, blank=True, null=True)
    raw = models.JSONField(blank=True, null=True)
    order_time = models.BigIntegerField(blank=True, null=True)
    update_time = models.BigIntegerField(default=0)
    is_trades_synced = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    operator = models.ForeignKey(Traders, on_delete=models.DO_NOTHING, blank=True, null=True)

    def __str__(self):
        return self.order_code
    
    def save(self, *args, **kwargs):
        self.exchange = self.exchange_account.exchange.code
        self.symbol_delimiter = self.exchange_account.exchange.symbol_delimiter
        super().save(*args, **kwargs)
    
    def exchange_symbol(self):
        if self.exchange == 'BYBIT':
            return f'{self.base_currency}{self.quote_currency}'
        return f'{self.base_currency}{self.symbol_delimiter}{self.quote_currency}'
    
    def to_kucoin_place_order(self):
        order_code = f't-kapi-{self.exchange_account_id}-{self.id}'
        order = {
            "clientOid": order_code,
            "symbol": self.exchange_symbol(),
            "type": self.type,
            "side": self.side,
            "timeInForce": self.time_in_force.upper(),
            "iceberg": self.iceberg,
        }

        if self.type == OrderType.LIMIT:
            order['price'] = self.price.to_eng_string()
            order['size'] = self.size.to_eng_string()
        else:
            if self.side == OrderSide.BUY:
                order['funds'] = self.amount.to_eng_string()
            else:
                order['size'] = self.size.to_eng_string()
        return order

    def to_bybit_place_order(self):
        order_code = f't-bapi-{self.exchange_account_id}-{self.id}'
        order = {
            "category": "spot",
            "orderLinkId": order_code,
            "symbol": self.exchange_symbol(),
            "side": self.side.capitalize(),
            "orderType": self.type.capitalize(),
            "timeInForce": self.time_in_force.upper(),
            'orderFilter': 'Order'
        }

        if self.type == OrderType.LIMIT:
            order['qty'] = self.size.to_eng_string()
            order['price'] = self.price.to_eng_string()
        else:
            if self.side == OrderSide.BUY:
                order['qty'] = self.amount.to_eng_string()
            else:
                order['qty'] = self.size.to_eng_string()
        return order

    def to_gateio_place_order(self):
        order_code = f't-apiv4-{self.exchange_account_id}-{self.id}'
        order = GateIoOrder(
            text=order_code,
            currency_pair=f'{self.base_currency}{self.symbol_delimiter}{self.quote_currency}',
            type=self.type,
            account="spot",
            side=self.side,
            iceberg="1" if self.iceberg else "0",
            amount="",
            price="",
            time_in_force=self.time_in_force,
        )

        if self.type == OrderType.LIMIT:
            order.amount = self.size.to_eng_string()
            order.price = self.price.to_eng_string()
        else:
            if self.side == OrderSide.BUY:
                order.amount = self.amount.to_eng_string()
            else:
                order.amount = self.size.to_eng_string()
        return order
    
    def to_mexc_place_order(self):
        order_code = f't-mapi-{self.exchange_account_id}-{self.id}'
        order = {
            "symbol": f'{self.base_currency}{self.quote_currency}',
            'side': self.side.upper(),
            'order_type': self.type.upper(),
            'options': {
                'timeInForce': self.time_in_force.upper(),
                'newClientOrderId': order_code,
            }
        }
        if self.type == OrderType.LIMIT:
            order['options']['price'] = self.price.to_eng_string()
            order['options']['quantity'] = self.size.to_eng_string()
        else:
            if self.side == OrderSide.BUY:
                order['options']['quoteOrderQty'] = self.amount.to_eng_string()
            else:
                order['options']['quantity'] = self.size.to_eng_string()

        return order
    
    def to_okx_place_order(self):
        order_code = f'txapix{self.exchange_account_id}x{self.id}'
        order = {
            "clOrdId": order_code,
            "instId": f'{self.base_currency}-{self.quote_currency}',
            "tdMode": "cash",
            "ordType": self.type,
            "side": self.side,
        }
        if self.type == OrderType.LIMIT:
            order['sz'] = self.size.to_eng_string()
            order['px'] = self.price.to_eng_string()
        else:
            if self.side == OrderSide.BUY:
                order['sz'] = self.amount.to_eng_string()
            else:
                order['sz'] = self.size.to_eng_string()
        return order
    
    def to_binance_place_order(self):
        order_code = f't-bapi-{self.exchange_account_id}-{self.id}'
        order = {
            "symbol": f'{self.base_currency}{self.quote_currency}',
            'side': self.side.upper(),
            'type': self.type.upper(),
            'newClientOrderId': order_code,
        }
        if self.side == OrderSide.BUY and self.type == OrderType.LIMIT:
            order['timeInForce'] = self.time_in_force.upper(),
        if self.type == OrderType.LIMIT:
            order['price'] = self.price.normalize() + Decimal('0')
            order['quantity'] = self.size.normalize() + Decimal('0')
        else:
            if self.side == OrderSide.BUY:
                order['quoteOrderQty'] = self.amount.normalize() + Decimal('0')
            else:
                order['quantity'] = self.size.normalize() + Decimal('0')
        return order
    class Meta:
        ordering = ['-created_at']
        db_table = 'orders'


class Trade(models.Model):
    trade_id = models.CharField(max_length=100, null=False, blank=False, default=0)
    order_id = models.CharField(max_length=100, null=False, blank=False, default=0)
    sys_order = models.ForeignKey(Order, on_delete=models.DO_NOTHING)
    order_time = models.CharField(max_length=32)
    side = models.CharField(choices=OrderSide.choices, max_length=16)
    role = models.CharField(max_length=8)
    amount = models.DecimalField(max_digits=32, decimal_places=8, blank=True, null=True)
    price = models.DecimalField(max_digits=32, decimal_places=8, blank=True, null=True)
    fee = models.DecimalField(max_digits=32, decimal_places=8, blank=True, null=True)
    fee_currency = models.CharField(max_length=8)
    sequence_id = models.CharField(max_length=32,null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    operator = models.ForeignKey(Traders, on_delete=models.DO_NOTHING, blank=True, null=True)

    class Meta:
        ordering = ['-order_time']
        db_table = 'trades'
        unique_together = ['trade_id', 'order_id', 'sys_order']


class Wallet(models.Model):
    user_id = models.CharField(max_length=100)
    exchange = models.CharField(max_length=32)
    exchange_account = models.ForeignKey(ExchangeAccount, on_delete=models.DO_NOTHING, related_name='wallets')
    type = models.CharField(choices=WalletType.choices, default=WalletType.SPOT, max_length=16)
    currency = models.CharField(max_length=8)
    balance = models.DecimalField(max_digits=32, decimal_places=12, blank=True, null=True)
    frozen = models.DecimalField(max_digits=32, decimal_places=12, blank=True, null=True)
    available = models.DecimalField(max_digits=32, decimal_places=12, blank=True, null=True)
    update_time = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'wallets'