import json
import logging
from mexc_sdk import Spot
from exchange.exchange import Exchange
from order.models import Order, OrderStatus

logger = logging.getLogger(__name__)

class MexcExchange(Exchange):
    EXCHANGE = 'MEXC'
    API_HOST = 'https://api.mexc.com'

    def __init__(self, api_key, api_secret, pass_phrase=None):
        super().__init__(api_key, api_secret, pass_phrase)
        self.cli = Spot(api_key, api_secret)

    def place_oder(self, order):
        return self.cli.new_order(**order)

    @staticmethod
    def parse_order(data):
        status = OrderStatus.OPEN
        if data['status'] == 'FILLED':
            status = OrderStatus.FILLED
        elif data['status'] == 'CANCELED':
            status = OrderStatus.CANCELLED
        elif data['status'] == 'PARTIALLY_FILLED':
            status = OrderStatus.PARTIALLY_FILLED
        elif data['status'] == 'PARTIALLY_CANCELED':
            status = OrderStatus.PARTIALLY_CANCELED
        logger.info(f"parse_order: {data}")
        quote_currency = 'USDT'
        order = Order(
            order_id=data['orderId'],
            order_code=data['clientOrderId'],
            symbol=data['symbol'],
            symbol_delimiter='-',
            type=data['type'].lower(),
            account_type='spot',
            base_currency=data['symbol'].split(quote_currency)[0],
            quote_currency='USDT',
            side=data['side'].lower(),
            size=data['origQty'],
            amount=data['origQuoteOrderQty'],
            price=data['price'],
            time_in_force=data['timeInForce'].lower(),
            iceberg=False,
            status=status,
            fee='0.0',
            fee_currency='None',
            raw=json.dumps(data),
            order_time=data['time'],
            update_time=data['updateTime']
        )
        return order

    def get_order(self, order_id, symbol):
        resp = self.cli.query_order(symbol=symbol, options={'orderId': order_id})
        order = self.parse_order(resp)
        return order
    
    def cancel_order(self, order_id, symbol):
        return self.cli.cancel_order(symbol=symbol, options={'orderId': order_id})
    
    def get_wallet_balance(self):
        return self.cli.account_info()
    
    def get_trades(self, **kwargs):
        pass