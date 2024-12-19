import json
import logging
from decimal import Decimal
import time
from .exchange import Exchange
from order.models import Order, OrderStatus
from binance.spot import Spot


logger = logging.getLogger(__name__)


class BinanceExchange(Exchange):
    EXCHANGE = 'BINANCE'
    API_HOST = 'https://api.binance.com'

    def __init__(self, api_key, api_secret, pass_phrase=None):
        super().__init__(api_key, api_secret, pass_phrase)
        self.client = Spot(api_key=self.api_key, api_secret=self.api_secret)

    def get_trades(self, **kwargs):
        pass

    def place_oder(self, order):
        return self.client.new_order(**order)

    def cancel_order(self, order_id, symbol):
        return self.client.cancel_order(symbol, orderId=order_id)

    def get_order(self, order_id, symbol):
        resp = self.client.get_order(symbol, orderId=order_id)
        if not resp.get('orderId', None):
            return None
        order = self.parse_order(resp)
        return order

    def get_account_info(self, **kwargs):
        return self.client.account()

    def get_wallet_balance(self, **kwargs):
        return self.client.user_asset()

    @staticmethod
    def parse_order(data):
        status = OrderStatus.OPEN
        if data['status'] == 'FILLED':
            status = OrderStatus.FILLED
        elif data['status'] == 'CANCELED':
            status = OrderStatus.CANCELLED
        elif data['status'] == 'PARTIALLY_FILLED':
            status = OrderStatus.PARTIALLY_FILLED
        elif data['status'] == 'REJECTED':
            status = OrderStatus.REJECTED

        size = Decimal(data['executedQty'] or 0)
        price = Decimal(data['price'] or 0)
        amount = Decimal(data['cummulativeQuoteQty'] or 0)
        if data['type'] == 'MARKET':
           price = (amount / size).quantize(Decimal('0.00000001'))
        order = Order(
            order_id=data['orderId'],
            order_code=data['clientOrderId'],
            account_type='spot',
            size=size,
            amount=amount,
            price=price,
            time_in_force=True,
            iceberg=False,
            status=status,
            raw=json.dumps(data),
            order_time=data['workingTime'],
            update_time=data['updateTime']
        )
        return order
