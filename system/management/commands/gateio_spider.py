import dataclasses
from .spider import Spider
from decimal import Decimal
import hmac, hashlib, json, time
from system.models import CurrencyPair
from order.models import Wallet, WalletType, Order, Trade
from django.core.cache import cache

import logging
logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ChannelReq:
    channel: str
    event: str
    timestamp: int
    payload: any = None
    auth: str = ""

    def alias_key(self, key):
        if key == "timestamp":
            return "time"
        return key

    def to_json(self):
        data = dataclasses.asdict(
            self,
            dict_factory=lambda fields: {
                self.alias_key(key): value
                for (key, value) in fields
                if value is not None or value != ""
            },
        )
        return json.dumps(data)


class GateSider(Spider):
    EXCHANGE = "GATEIO"
    WSURL = "wss://api.gateio.ws/ws/v4/"
    SYMBOLS = []

    def _sign(self, auth):
        print(self.exchange_account)
        msg = "channel=%s&event=%s&time=%d" % (auth.channel, auth.event, auth.timestamp)

        sign = hmac.new(
            self.exchange_account.api_secret.encode("utf-8"),
            msg.encode("utf-8"),
            hashlib.sha512,
        ).hexdigest()
        return {"method": "api_key", "KEY": self.exchange_account.api_key, "SIGN": sign}

    async def _get_exchange_account_symbols(self):
        if len(self.SYMBOLS) > 0:
            return self.SYMBOLS
        symbols = []
        async for entry in CurrencyPair.objects.filter(exchange_account=self.exchange_account):
            symbols.append(entry.symbol)
        self.SYMBOLS = symbols

    async def subscription(self):
        await self._get_exchange_account_symbols()
        channels = ["spot.orders", "spot.usertrades", "spot.tickers", "spot.balances"]

        for channel in channels:
            request = ChannelReq(
                channel=channel,
                timestamp=int(time.time()),
                event="subscribe",
                payload=self.SYMBOLS,
            )
            request.auth = self._sign(request)
            logger.info("channel subscribe request: %s", channel)
            resp = await self.send(request.to_json())
            logger.info("channel subscribe response: %s", resp)

    async def handle_message(self, raw_message):
        message = json.loads(raw_message)
        # logger.info("message: %s", message)
        channel = message.get("channel")
        event = message.get("event")
        if event == "update":
            handler = getattr(self, f"handle_{channel.replace('.', '_')}", None)
            if handler is not None:
                await handler(message)

    async def handle_spot_balances(self, message):
        logger.info('handle spot balances: %s', message)
        for entry in message.get('result', []):
            update_time = int(float(entry['timestamp_ms']))
            wallet, created = await Wallet.objects.aget_or_create(
                user_id = entry['user'],
                exchange=self.exchange_account.exchange.code,
                exchange_account=self.exchange_account,
                currency=entry['currency'],
                type=WalletType.SPOT,
                defaults={
                    'balance': Decimal(entry['total']),
                    'frozen': Decimal(entry['freeze']),
                    'available': Decimal(entry['available']),
                    'update_time': update_time
                }
            )
            if not created and wallet is not None:
                if update_time >= wallet.update_time:
                    wallet.balance = Decimal(entry['total'])
                    wallet.frozen = Decimal(entry['freeze'])
                    wallet.available = Decimal(entry['available'])
                    wallet.update_time = update_time
                    await wallet.asave()

    async def handle_spot_tickers(self, message):
        result = message.get('result')
        logger.info("handle spot tickers, currency_pair: %s, last: %s", result.get('currency_pair'), result.get('last'))
        ticker_key = f"{self.EXCHANGE}:tickers".lower()
        self.redis.hset(ticker_key, result.get('currency_pair'), result.get('last'))

    async def handle_spot_usertrades(self, message):
        # message: {"time":1714729020,"time_ms":1714729020195,"channel":"spot.usertrades","event":"update","result":[{"id":8900430811,"user_id":15531692,"order_id":"575707647866","currency_pair":"PEPE_USDT","create_time":1714729020,"create_time_ms":"1714729020184.131","side":"buy","amount":"449755.846826","role":"taker","price":"0.000007782","fee":"449.755846826","fee_currency":"PEPE","point_fee":"0","gt_fee":"0","text":"t-apiv4-1-18","amend_text":"-","biz_info":"-"}]}
        logger.info('handle spot usertrades: %s', message)
        for entry in message.get('result', []):
            order = await Order.objects.select_related('operator').filter(order_id=entry['order_id']).afirst()
            if order is None:
                continue
            await Trade.objects.aget_or_create(
                    trade_id=entry['id'],
                    order_id=entry['order_id'],
                    sys_order=order,
                defaults={
                    'order_time': int(float(entry['create_time_ms'])),
                    'side': entry['side'],
                    'price': Decimal(entry['price']),
                    'amount': Decimal(entry['amount']),
                    'role': entry['role'],
                    'fee': Decimal(entry['fee']),
                    'fee_currency': entry['fee_currency'],
                    'sequence_id': entry.get('sequence_id'),
                    'operator': order.operator
                }
        )
 
    async def handle_spot_orders(self, message):
        # message: {"time":1714729020,"time_ms":1714729020209,"channel":"spot.orders","event":"update","result":[{"id":"575707647866","text":"t-apiv4-1-18","create_time":"1714729020","update_time":"1714729020","currency_pair":"PEPE_USDT","type":"market","account":"spot","side":"buy","amount":"3.5","price":"0","time_in_force":"fok","left":"3.5","filled_total":"0","avg_deal_price":"0","fee":"0","fee_currency":"PEPE","point_fee":"0","gt_fee":"0","rebated_fee":"0","rebated_fee_currency":"PEPE","create_time_ms":"1714729020184","update_time_ms":"1714729020184","user":15531692,"event":"put","stp_id":0,"stp_act":"-","finish_as":"open","biz_info":"-","amend_text":"-"}]}
        logger.info('handle spot orders: %s', message)
        for entry in message.get('result', []):
            order = await Order.objects.filter(order_id=entry['id']).afirst()
            if order is not None:
                if order.status == 'open' and entry['finish_as'] != order.status:
                    order.status = entry['finish_as']
                    order.update_time = int(float(entry['update_time_ms']))
                    await order.asave()

# message: {"time":1712565853,"time_ms":1712565853837,"channel":"spot.usertrades","event":"subscribe","payload":["QTCON_USDT"],"result":{"status":"success"},"requestId":"ed1d6bf120401196eabfd2eff0753e9d"}
# message: {"time":1712565853,"time_ms":1712565853925,"channel":"spot.tickers","event":"subscribe","payload":["QTCON_USDT"],"result":{"status":"success"},"requestId":"c5409303be34f4f655d6260169fb7c94"}
# message: {"time":1712565853,"time_ms":1712565853926,"channel":"spot.balances","event":"subscribe","payload":["QTCON_USDT"],"result":{"status":"success"},"requestId":"f513e3771ac741fbafcae1fca1526998"}