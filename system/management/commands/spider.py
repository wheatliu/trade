import asyncio
from asgiref.sync import sync_to_async
import websockets
from system.models import ExchangeAccount
from django_redis import get_redis_connection


class Spider:
    EXCHANGE = ""
    PING_INTERVAL = 20
    WSURL = ""
    SYMBOLS = []

    def __init__(self, account_name):
        self.account_name = account_name
        self.exchange_account = None
        self.redis = get_redis_connection("default")

    async def _get_exchange_account(self):
        if self.exchange_account is None:
            exchange_account = await ExchangeAccount.objects.select_related('exchange').filter(name=self.account_name).afirst()
            if exchange_account is None:
                raise Exception("Exchange Account Is Not Found.")
            return exchange_account
        return self.exchange_account
  
    def login(self):
      raise NotImplemented
    
    def subscription(self):
      raise NotImplemented
      
    async def handle_message():
      raise NotImplemented
    
    async def connect(self):
      async for websocket in websockets.connect(self.WSURL):
        try:
          self.websocket = websocket
          self.exchange_account = await self._get_exchange_account()
          await self.subscription()
          async for message in websocket:
            await self.handle_message(message)
        except websockets.ConnectionClosed:
           continue
     

    async def send(self, message):
       await self.websocket.ensure_open()
       return await self.websocket.send(message=message)
    
