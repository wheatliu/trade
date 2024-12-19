import decimal
import time
import json
from .exchange import Exchange
from kucoin.client import User, Trade
from order.models import Order, OrderStatus

import logging
logger = logging.getLogger(__name__)

class KuCoinExchange(Exchange):
    EXCHANGE = 'KUCOIN'
    API_HOST = 'https://api.bybit.com'

    def __init__(self, api_key, api_secret, pass_phrase=None):
        super().__init__(api_key, api_secret, )
        self.user_cli = User(api_key, api_secret, pass_phrase)
        self.trade_cli = Trade(api_key, api_secret, pass_phrase)

    def place_oder(self, order):
        if order['type'] == 'limit':
            return self._place_limit_order(order)
        elif order['type'] == 'market':
            return self._place_market_order(order)
        else:
            raise ValueError("Invalid order type")

    def _place_limit_order(self, order):
        return self.trade_cli.create_limit_order(**order)

    def _place_market_order(self, order):
        return self.trade_cli.create_market_order(**order)

    @staticmethod
    def parse_order(data):
        is_order_open = data.get('isActive', False)
        cancleExist = data.get('cancelExist', False)
        is_order_closed = not is_order_open
        status = OrderStatus.OPEN
        if is_order_closed:
            if cancleExist:
                status = OrderStatus.CANCELLED
            else:
                status = OrderStatus.FILLED
        price = decimal.Decimal(data['price'])
        size = decimal.Decimal(data['size'])
        if data.get('type') == 'market':
            deal_funds = decimal.Decimal(data.get('dealFunds', 0))
            deal_size = decimal.Decimal(data.get('dealSize', 0))
            if deal_funds > 0 and deal_size > 0:
                size = deal_size
                price = deal_funds / deal_size
        trade = Order(
            order_id=data['id'],
            order_code=data['clientOid'],
            symbol=data['symbol'],
            symbol_delimiter='-',
            type=data['type'],
            account_type='spot',
            base_currency=data['symbol'].split('-')[0],
            quote_currency=data['symbol'].split('-')[1],
            side=data['side'],
            size=size,
            amount=data['dealFunds'],
            price=price,
            time_in_force=data['timeInForce'],
            iceberg=data['iceberg'],
            status=status,
            fee=data['fee'],
            fee_currency=data['feeCurrency'],
            raw=json.dumps(data),
            order_time=data['createdAt'],
            update_time=int(time.time()*1000)
        )
        return trade

    def get_order(self, order_id, **kwargs):
        order_result = self.trade_cli.get_order_details(order_id)
        order = self.parse_order(order_result)
        return order

    def cancel_order(self, order_id, **kwargs):
        order_result = self.trade_cli.cancel_order(order_id)
        return order_result

    def get_trades(self, order_id, **kwargs):
        return self.api_cli.get_executions(category="spot", order_id=order_id)

    def get_unified_accounts(self, **kwargs):
        return self.unified_cli.list_unified_accounts(**kwargs)

    def get_wallet_balance(self, **kwargs):
        return self.user_cli.get_account_list()

    def get_account_info(self, **kwargs):
        return self.user_cli.get_account_summary_info()

    def list_order_history(self, **kwargs):
        return self.trade_cli.get_order_list()
