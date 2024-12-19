import json
import logging
from decimal import Decimal
from okx import Account, Trade
from .exchange import Exchange
from order.models import Order, OrderStatus


logger = logging.getLogger(__name__)

class OKXExchange(Exchange):
    EXCHANGE = 'OKX'
    API_HOST = 'https://www.okex.com'

    def __init__(self, api_key, api_secret, pass_phrase=None):
        super().__init__(api_key, api_secret, pass_phrase)
        self.account_cli = Account.AccountAPI(api_key, api_secret, pass_phrase, flag='0')
        self.trade_cli = Trade.TradeAPI(api_key, api_secret, pass_phrase, flag='0')

    def get_trades(self, **kwargs):
        pass
    
    def place_oder(self, order):
        return self.trade_cli.place_order(**order)
    
    def cancel_order(self, order_id, inst_id):
        return self.trade_cli.cancel_order(inst_id, ordId=order_id)
    
    def get_order(self, order_id, inst_id):
        resp = self.trade_cli.get_order(inst_id, ordId=order_id)
        if resp.get('code') != '0':
            return None
        result = resp.get('data', [])
        if not result:
            return None
        data = result[0]
        order = self.parse_order(data)
        return order
    
    def get_account_info(self, **kwargs):
        return self.account_cli.get_account_config(**kwargs)
 
    def get_wallet_balance(self, **kwargs):
        return self.account_cli.get_account_balance(**kwargs)
    
    @staticmethod
    def parse_order(data):
        status = OrderStatus.OPEN
        if data['state'] == 'filled':
            status = OrderStatus.FILLED
        elif data['state'] == 'canceled':
            status = OrderStatus.CANCELLED
        elif data['state'] == 'partially_filled':
            status = OrderStatus.PARTIALLY_FILLED
        elif data['state'] == 'mmp_canceled':
            status = OrderStatus.MMP_CANCELLED

        size = Decimal(data['fillSz'] or data['sz'] or 0)
        price = Decimal(data['avgPx'] or data['px'] or 0)
        amount = price * size
        order = Order(
            order_id=data['ordId'],
            order_code=data['clOrdId'],
            symbol=data['instId'],
            symbol_delimiter='-',
            type=data['ordType'],
            account_type='spot',
            base_currency=data['instId'].split('-')[0],
            quote_currency=data['instId'].split('-')[1],
            side=data['side'].lower(),
            size=size,
            amount=amount,
            price=price,
            time_in_force=True,
            iceberg=False,
            status=status,
            fee=data['fee'],
            fee_currency=data['feeCcy'],
            raw=json.dumps(data),
            order_time=data['cTime'],
            update_time=data['uTime']
        )
        return order
