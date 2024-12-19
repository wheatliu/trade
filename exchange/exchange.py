import requests
from abc import ABC, abstractmethod

class Exchange(ABC):
    EXCHANGE = ""
    API_HOST = ""

    def __init__(self, api_key, api_secret, pass_phrase=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.pass_phrase = pass_phrase
  
    @abstractmethod
    def place_oder(self, *args):
        raise NotImplementedError("subclass should implement this")

    @abstractmethod
    def get_order(self, order_id, **kwargs):
        raise NotImplementedError("subclass should implement this")
    
    @abstractmethod
    def cancel_order(self, order_id, **kwargs):
        raise NotImplementedError("subclass should implement this")

    @abstractmethod
    def get_trades(self, **kwargs):
        raise NotImplementedError("subclass should implement this")
