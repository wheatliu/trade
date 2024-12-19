import time
from gate_api import ApiClient, Configuration, Order, SpotApi, UnifiedApi, WalletApi, AccountApi
from .exchange import Exchange

class GateioExchange(Exchange):
  EXCHANGE = 'GATEIO'
  API_HOST = 'https://api.gateio.ws/api/v4'

  def __init__(self, api_key, api_secret, pass_phrase=None):
    super().__init__(api_key, api_secret, pass_phrase)
    config = Configuration(key=api_key, secret=api_secret, host=self.API_HOST)
    self.api_cli = ApiClient(config)
    self.spot_cli = SpotApi(self.api_cli)
    self.wallet_cli = WalletApi(self.api_cli)
    self.unified_cli = UnifiedApi(self.api_cli)
    self.account_cli = AccountApi(self.api_cli)

  
  def place_oder(self, order: Order):
    created = self.spot_cli.create_order(order)
    return created
  
  def get_order(self, order_id, **kwargs):
    order_result = self.spot_cli.get_order(order_id, currency_pair=kwargs.get('currency_pair'))
    return order_result
  
  def cancel_order(self, order_id, **kwargs):
    order_result = self.spot_cli.cancel_order(order_id, currency_pair=kwargs.get('currency_pair'))
    return order_result

  def get_trades(self, **kwargs):
    return self.spot_cli.list_my_trades(**kwargs)
  
  def get_unified_accounts(self, **kwargs):
    return self.unified_cli.list_unified_accounts(**kwargs)
  
  def get_wallet_balance(self, **kwargs):
    return self.spot_cli.list_spot_accounts(**kwargs)
  
  def get_account_info(self, **kwargs):
    return self.account_cli.get_account_detail(**kwargs)
  
  def list_order_history(self, **kwargs):
    return self.spot_cli.list_orders(**kwargs)
 