import decimal
import time
import dataclasses
from .exchange import Exchange
from order.models import Order, OrderStatus

from pybit.unified_trading import HTTP

class BybitExchange(Exchange):
  EXCHANGE = 'BYBIT'
  API_HOST = 'https://api.bybit.com'

  def __init__(self, api_key, api_secret, pass_phrase=None):
    super().__init__(api_key, api_secret, pass_phrase)
    self.api_cli = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

  
  @staticmethod
  def parse_order(data):
    print(data)
    status = OrderStatus.OPEN
    if data['orderStatus'] == 'Filled':
      status = OrderStatus.FILLED
    elif data['orderStatus'] == 'Cancelled':
      status = OrderStatus.CANCELLED
    elif data['orderStatus'] == 'Rejected':
      status = OrderStatus.REJECTED
    elif data['orderStatus'] == 'PartiallyFilledCanceled':
      status = OrderStatus.PARTIALLY_FILLED_CANCELED
    elif data['orderStatus'] == 'PartiallyFilled':
      status = OrderStatus.PARTIALLY_FILLED
    amount = 0
    size = decimal.Decimal(data['cumExecQty'])
    if data['cumExecQty'] and data['avgPrice']:
      amount = decimal.Decimal(data['cumExecQty']) * decimal.Decimal(data['avgPrice'])
    price = decimal.Decimal(data['price'] or 0)
    if not price:
      price = decimal.Decimal(data['avgPrice'] or 0)
    order = Order(
      order_id=data['orderId'],
      order_code=data['orderLinkId'],
      price=price,
      size=size,
      side=data['side'].lower(),
      status=status,
      amount=amount,
      type=data['orderType'].lower(),
      time_in_force=data['timeInForce'].lower(),
      order_time=int(data['createdTime']),
      update_time=int(data['updatedTime'])
    )
    return order

  def place_oder(self, order):
    return self.api_cli.place_order(**order)

  def get_order(self, order_id, **kwargs):
    resp = self.api_cli.get_order_history(category="spot", limit=1, orderId=order_id, **kwargs)
    orders = resp.get('result', {}).get('list', [])
    if len(orders) > 0:
      order = self.parse_order(orders[0])
      return order
  
  def cancel_order(self, order_id, **kwargs):
    order_result = self.api_cli.cancel_order(category="spot",orderId=order_id, symbol=kwargs.get('currency_pair'))
    return order_result

  def get_trades(self, order_id, **kwargs):
    return self.api_cli.get_executions(category="spot",orderId=order_id)
  
  def get_unified_accounts(self, **kwargs):
    return self.api_cli.list_unified_accounts(**kwargs)
  
  def get_wallet_balance(self, **kwargs):
    return self.api_cli.get_wallet_balance(**kwargs)
  
  def get_account_info(self, **kwargs):
    return self.api_cli.get_api_key_information(**kwargs)
  
  def list_order_history(self, **kwargs):
    return self.api_cli.get_order_history(category="spot", **kwargs)
 