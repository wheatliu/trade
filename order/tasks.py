import uuid
from decimal import Decimal
from celery import shared_task
from django.conf import settings
from order.models import Order, Trade, OrderStatus, Wallet, WalletType, OrderType, OrderSide
from system.models import ExchangeAccount

from exchange import (
    GateioExchange, KuCoinExchange, BybitExchange,
    MexcExchange, OKXExchange, BinanceExchange
)
from gate_api.exceptions import ApiException
import logging
logger = logging.getLogger(__name__)


@shared_task
def get_gateio_account_detail(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'GATEIO':
            cli = GateioExchange(exchange_account.api_key,
                                 exchange_account.api_secret)
            result = cli.get_account_info()
            exchange_account.user_id = result.user_id
            exchange_account.save()
            get_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e)

@shared_task
def get_kucoin_account_detail(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'KUCOIN':
            cli = KuCoinExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                 pass_phrase=exchange_account.pass_phrase)
            if not exchange_account.user_id:
                exchange_account.user_id = cli.user_cli.return_unique_id
                exchange_account.save()
            get_kucoin_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e)

@shared_task
def sync_spot_account_balance():
    exchange_accounts = ExchangeAccount.objects.all()
    for exchange_account in exchange_accounts:
        if exchange_account.exchange.code == 'GATEIO':
            try:
                get_spot_account_info(exchange_account.id)
            except Exception as e:
                logger.error(e)

@shared_task
def sync_kucoin_spot_account_balance():
    exchange_accounts = ExchangeAccount.objects.all()
    for exchange_account in exchange_accounts:
        if exchange_account.exchange.code == 'KUCOIN':
            try:
                get_kucoin_spot_account_info(exchange_account.id)
            except Exception as e:
                logger.error(e)

@shared_task
def get_kucoin_spot_account_info(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'KUCOIN':
            cli = KuCoinExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                pass_phrase=exchange_account.pass_phrase)
            result = cli.get_wallet_balance()
            for item in result:
                if item['type'] == 'trade':
                    available = Decimal(item['available'])
                    locked = Decimal(item['holds'])
                    balance = Decimal(item['balance'])
                    Wallet.objects.update_or_create(
                        user_id=exchange_account.user_id,
                        exchange=exchange_account.exchange.code,
                        exchange_account=exchange_account,
                        currency=item['currency'],
                        type=WalletType.SPOT,
                        defaults={
                            'balance': balance,
                            'frozen': locked,
                            'available': available
                        },
                        create_defaults={
                            'balance': balance,
                            'frozen': locked,
                            'available': available
                        }
                    )
    except Exception as e:
        logger.error(e)


@shared_task
def get_spot_account_info(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'GATEIO':
            cli = GateioExchange(exchange_account.api_key,
                                 exchange_account.api_secret)
            result = cli.get_wallet_balance()
            for item in result:
                available = Decimal(item.available)
                locked = Decimal(item.locked)
                Wallet.objects.update_or_create(
                    user_id=exchange_account.user_id,
                    exchange=exchange_account.exchange.code,
                    exchange_account=exchange_account,
                    currency=item.currency,
                    type=WalletType.SPOT,
                    defaults={
                        'balance': available + locked,
                        'frozen': locked,
                        'available': available
                    },
                    create_defaults={
                        'balance': available + locked,
                        'frozen': locked,
                        'available': available
                    }
                )
    except Exception as e:
        logger.error(e)


@shared_task
def sync_spot_history_orders():
    exchange_accounts = ExchangeAccount.objects.prefetch_related(
        'currency_pairs').all()
    for exchange_account in exchange_accounts:
        if exchange_account.exchange.code == 'GATEIO':
            cli = GateioExchange(exchange_account.api_key,
                                 exchange_account.api_secret)
            currency_pairs = exchange_account.currency_pairs.all()
            for currency_pair in currency_pairs:
                for status in ['open', 'finished']:
                    try:
                        print(currency_pair.symbol, status)
                        orders = cli.list_order_history(
                            currency_pair=currency_pair.symbol,
                            status=status
                            )
                        for order in orders:
                            print(order)
                            size = Decimal(order.amount)
                            amount = Decimal(order.filled_total or 0)
                            price = Decimal(order.price or order.avg_deal_price)
                            if order.type == OrderType.MARKET:
                                if order.side == OrderSide.BUY:
                                    if order.status == OrderStatus.CLOSED:
                                        size = Decimal(order.filled_total) / Decimal(order.avg_deal_price)
                                        price = Decimal(order.avg_deal_price)
                                        amount = Decimal(order.filled_total)
                                    else:
                                        amount = Decimal(order.amount)
                                        size = Decimal(0)
                                        price = Decimal(order.avg_deal_price or 0)
                                else:
                                    if order.status == OrderStatus.CLOSED:
                                        amount = Decimal(order.filled_total)
                                        size = Decimal(order.filled_amount)
                                        price = Decimal(order.avg_deal_price or 0)
                                    else:
                                        amount = Decimal(0)
                                        size = size
                                        price = Decimal(order.avg_deal_price or 0)
                            Order.objects.update_or_create(
                                order_id=order.id,
                                exchange=exchange_account.exchange.code,
                                exchange_account=exchange_account,
                                defaults={
                                    'order_code': order.text,
                                    'symbol': order.currency_pair,
                                    'base_currency': order.currency_pair.split('_')[0],
                                    'quote_currency': order.currency_pair.split('_')[1],
                                    'type': order.type,
                                    'side': order.side,
                                    'size': size,
                                    'price': price,
                                    'amount': amount,
                                    'status': order.status,
                                    'order_time': order.create_time_ms,
                                    'update_time': order.update_time_ms,
                                    'fee': Decimal(order.fee),
                                    'fee_currency': order.fee_currency,
                                    'operator': exchange_account.operator
                                }
                            )
                    except Exception as e:
                        logger.error(e)


@shared_task
def place_order(order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if order.exchange == 'GATEIO':
            exchange_account = order.exchange_account
            cli = GateioExchange(exchange_account.api_key,
                                 exchange_account.api_secret)
            order_data = order.to_gateio_place_order()
            logger.info('#' * 50)
            logger.info(order_data)
            result = cli.place_oder(order_data)
            logger.info('#' * 50)
            logger.info(result)
            if result.status == "closed":
                order.status = OrderStatus.FILLED
            elif result.status == "open":
                order.status = OrderStatus.OPEN
            elif result.status == "cancelled":
                order.status = OrderStatus.CANCELLED
            logger.info(result)
            order.order_code = order_data.text
            order.order_id = result.id
            order.order_time = result.create_time_ms
            order.update_time = result.update_time_ms
            if order.type == OrderType.MARKET:
                if order.side == OrderSide.BUY:
                    order.size = Decimal(result.filled_total) / \
                        Decimal(result.avg_deal_price)
                    order.price = Decimal(result.avg_deal_price)
                else:
                    order.size = Decimal(result.amount)
                    order.price = Decimal(result.avg_deal_price)
            order.fee = result.fee
            order.fee_currency = result.fee_currency

            order.save()
    except Exception as e:
        logger.error(e)
        order.status = OrderStatus.ERROR
    finally:
        order.save()


@shared_task
def sync_order():
    try:
        open_orders = Order.objects.filter(status=OrderStatus.FILLED)
    except Exception as e:
        logger.error(e, stack_info=True)
    for order in open_orders:
        try:
            if order.exchange == "GATEIO":
                exchange_account = order.exchange_account
                cli = GateioExchange(
                    exchange_account.api_key, exchange_account.api_secret)
                result = cli.get_order(
                    order.order_id, currency_pair=order.exchange_symbol())
                if result.status == "closed":
                    order.is_trades_synced = True
                    order.status = OrderStatus.FILLED
                elif result.status == "open":
                    order.status = OrderStatus.OPEN
                elif result.status == "cancelled":
                    order.status = OrderStatus.CANCELLED
                    order.is_trades_synced = True
                if order.type == OrderType.MARKET:
                    if order.side == OrderSide.BUY:
                        order.size = Decimal(result.filled_total) / \
                            Decimal(result.avg_deal_price)
                        order.price = Decimal(result.avg_deal_price)
                    else:
                        order.size = Decimal(result.amount)
                        order.price = Decimal(result.avg_deal_price)
                order.fee = result.fee
                order.fee_currency = result.fee_currency
                order.update_time = result.update_time_ms

        except Exception as e:
            logger.error(e, stack_info=True)
        finally:
            order.save()


@shared_task
def cancel_order(order_id):
    try:
        order = Order.objects.get(id=order_id)
        if order.status in [OrderStatus.CANCELLED, OrderStatus.FILLED]:
            return
    except Exception as e:
        logger.error(e, stack_info=True)

    try:
        if order.exchange == "GATEIO":
            exchange_account = order.exchange_account
            cli = GateioExchange(exchange_account.api_key,
                                 exchange_account.api_secret)
            result = cli.cancel_order(
                order.order_id, currency_pair=order.exchange_symbol())
            print('#' * 50)
            print(result)
            if result.status == "closed":
                order.status = OrderStatus.FILLED
            elif result.status == "open":
                order.status = OrderStatus.OPEN
            elif result.status == "cancelled":
                order.status = OrderStatus.CANCELLED
            order.fee = result.fee
            order.fee_currency = result.fee_currency
    # except ApiException as
    except Exception as e:
        logger.error(e, stack_info=True)
    finally:
        order.save()


@shared_task
def sync_trades():
    try:
        open_orders = Order.objects.filter(is_trades_synced=False, status__in=[
                                           OrderStatus.FILLED, OrderStatus.CANCELLED])
    except Exception as e:
        logger.error(e, stack_info=True)
    try:
        for order in open_orders:
            exchange_account = order.exchange_account
            cli = GateioExchange(exchange_account.api_key,
                                 exchange_account.api_secret)
            trades = cli.get_trades(
                order_id=order.order_id, currency_pair=order.exchange_symbol())
            for trade in trades:
                print(trade)
                Trade.objects.get_or_create(
                    trade_id=trade.id,
                    order_id=order.order_id,
                    sys_order=order,
                    defaults={
                        'order_time': int(float(trade.create_time_ms)),
                        'side': trade.side,
                        'price': Decimal(trade.price),
                        'amount': Decimal(trade.amount),
                        'role': trade.role,
                        'fee': Decimal(trade.fee),
                        'fee_currency': trade.fee_currency,
                        'sequence_id': trade.sequence_id,
                        'operator': order.operator
                    }
                )
    except Exception as e:
        logger.error(e, stack_info=True)


@shared_task
def sync_kucoin_order(order_id):
    try:
        order = Order.objects.get(id = order_id)
    except Exception as e:
        logger.error(e, stack_info=True)
    try:
        exchange_account = order.exchange_account
        cli = KuCoinExchange(
            exchange_account.api_key, exchange_account.api_secret,
            pass_phrase=exchange_account.pass_phrase)
        result = cli.get_order(
            order.order_id)
        order.status = result.status
        order.size = result.size
        order.price = result.price
        order.amount = result.amount
        order.fee = result.fee
        order.raw = result.raw
        order.fee_currency = result.fee_currency
        order.update_time = result.update_time
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.PARTIALLY_FILLED_CANCELED]:
            order.is_trades_synced = True
    except Exception as e:
        logger.error(e, stack_info=True)
    finally:
        order.save()

@shared_task
def place_kubocin_order(order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if order.exchange == 'KUCOIN':
            exchange_account = order.exchange_account
            cli = KuCoinExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                 pass_phrase=exchange_account.pass_phrase)
            order_data = order.to_kucoin_place_order()
            logger.info(f'place order: {order_data}')
            result = cli.place_oder(order_data)
            logger.info(f'place order result: {result}')
            order.order_code = order_data['clientOid']
            order.order_id = result['orderId']
            order.status = OrderStatus.OPEN
            order.save()
            sync_kucoin_order(order.id)
            get_kucoin_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e, exc_info=True)
        order.status = OrderStatus.ERROR

@shared_task
def sync_kucoin_orders():
    try:
        orders = Order.objects.filter(
            is_trades_synced = False, exchange='KUCOIN')
        for order in orders:
            try:
                sync_kucoin_order(order.id)
            except Exception as se:
                logger.error(se, exc_info=True)
    except Exception as e:
        logger.error(e, exc_info=True)

@shared_task
def cancel_kucoin_order(order_id):
    try:
        order = Order.objects.get(id=order_id, status=OrderStatus.WAITING_FOR_CANCEL)
    except Exception as e:
        logger.error(e, stack_info=True)

    try:
        exchange_account = order.exchange_account
        cli = KuCoinExchange(exchange_account.api_key,
                                exchange_account.api_secret,
                                pass_phrase=exchange_account.pass_phrase)
        result = cli.cancel_order(
            order.order_id)
        logger.info(f'{order.order_id} cancel result: {result}')
        order.status = OrderStatus.CANCELLIING
        order.save()
        sync_kucoin_order(order.id)
        get_kucoin_spot_account_info(exchange_account.id)
    # except ApiException as
    except Exception as e:
        logger.error(e, stack_info=True)
    finally:
        order.save()


@shared_task
def sync_bybit_order(order_id):
    try:
        order = Order.objects.get(id = order_id)
    except Exception as e:
        logger.error(e, stack_info=True)

    try:
        exchange_account = order.exchange_account
        cli = BybitExchange(
            exchange_account.api_key, exchange_account.api_secret,
            pass_phrase=exchange_account.pass_phrase)
        result = cli.get_order(
            order.order_id)
        order.status = result.status
        order.size = result.size
        order.price = result.price
        order.amount = result.amount
        order.raw = result.raw
        order.order_time = result.order_time
        order.update_time = result.update_time

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.PARTIALLY_FILLED_CANCELED]:
            order.is_trades_synced = True
    except Exception as e:
        logger.error(e, stack_info=True)
    finally:
        order.save()

@shared_task
def place_bybit_order(order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if order.exchange == 'BYBIT':
            exchange_account = order.exchange_account
            cli = BybitExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                 pass_phrase=exchange_account.pass_phrase)
            order_data = order.to_bybit_place_order()
            logger.info('#' * 50)
            logger.info(order_data)
            resp = cli.place_oder(order_data)
            logger.info('#' * 50)
            logger.info(resp)
            result = resp.get('result', {})
            order.order_code = result['orderLinkId']
            order.order_id = result['orderId']
            order.status = OrderStatus.OPEN
            order.save()
            sync_bybit_order(order.id)
            get_bybit_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e, exc_info=True)
        order.status = OrderStatus.ERROR

@shared_task
def sync_bybit_orders():
    try:
        orders = Order.objects.filter(is_trades_synced=False, exchange='BYBIT')
    except Exception as e:
        logger.error(e, stack_info=True)
    for order in orders:
        try:
            sync_bybit_order(order.id)
        except Exception as e:
            logger.error(e, stack_info=True)

@shared_task
def cancel_bybit_order(order_id):
    try:
        order = Order.objects.get(id=order_id, status=OrderStatus.WAITING_FOR_CANCEL)
    except Exception as e:
        logger.error(e, stack_info=True)

    try:
        exchange_account = order.exchange_account
        cli = BybitExchange(exchange_account.api_key,
                                exchange_account.api_secret,
                                pass_phrase=exchange_account.pass_phrase)
        result = cli.cancel_order(
            order.order_id)
        print('#' * 50)
        print(result)
        order.status = OrderStatus.CANCELLIING
        order.save()
        sync_bybit_order(order_id)
        get_bybit_spot_account_info(exchange_account.id)
    # except ApiException as
    except Exception as e:
        logger.error(e, stack_info=True)
    finally:
        order.save()

@shared_task
def get_bybit_account_detail(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'BYBIT':
            cli = BybitExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                 pass_phrase=exchange_account.pass_phrase)
            resp = cli.get_account_info()
            result = resp.get('result', {})
            exchange_account.user_id = result.get('userID')
            exchange_account.save()
            get_bybit_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e)

@shared_task
def sync_bybit_spot_account_balance():
    exchange_accounts = ExchangeAccount.objects.all()
    for exchange_account in exchange_accounts:
        if exchange_account.exchange.code == 'BYBIT':
            try:
                get_bybit_spot_account_info(exchange_account.id)
            except Exception as e:
                logger.error(e)

@shared_task
def get_bybit_spot_account_info(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'BYBIT':
            cli = BybitExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                pass_phrase=exchange_account.pass_phrase)
            resp = cli.get_wallet_balance(accountType='SPOT')
            print('#' * 50)
            print(resp)
            results = resp.get('result', {}).get('list', [])
            if len(results) > 0:
                result = results[0]
                coins = result.get('coin', [])
                for item in coins:
                    available = Decimal(item['free'])
                    locked = Decimal(item['locked'])
                    balance = Decimal(item['walletBalance'])
                    Wallet.objects.update_or_create(
                        user_id=exchange_account.user_id,
                        exchange=exchange_account.exchange.code,
                        exchange_account=exchange_account,
                        currency=item['coin'],
                        type=WalletType.SPOT,
                        defaults={
                            'balance': balance,
                            'frozen': locked,
                            'available': available
                        },
                        create_defaults={
                            'balance': balance,
                            'frozen': locked,
                            'available': available
                        }
                    )
    except Exception as e:
        logger.error(e)








@shared_task
def sync_mexc_order(order_id):
    try:
        order = Order.objects.get(id = order_id)
    except Exception as e:
        logger.error(e, stack_info=True)

    try:
        exchange_account = order.exchange_account
        cli = MexcExchange(
            exchange_account.api_key, exchange_account.api_secret,
            pass_phrase=exchange_account.pass_phrase)
        symbol = f'{order.base_currency}{order.quote_currency}'
        result = cli.get_order(
            order.order_id, symbol)
        order.status = result.status
        order.size = result.size
        order.price = result.price
        order.amount = result.amount
        order.raw = result.raw
        order.order_time = result.order_time
        order.update_time = result.update_time

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.PARTIALLY_CANCELED]:
            order.is_trades_synced = True
        order.save()
    except Exception as e:
        logger.error(e, stack_info=True)

@shared_task
def place_mexc_order(order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if order.exchange == 'MEXC':
            exchange_account = order.exchange_account
            cli = MexcExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                 pass_phrase=exchange_account.pass_phrase)
            order_data = order.to_mexc_place_order()
            logger.info('#' * 50)
            logger.info(order_data)
            result = cli.place_oder(order_data)
            logger.info('#' * 50)
            logger.info(result)
            order.order_id = result['orderId']
            order.order_code = order_data['options']['newClientOrderId']
            order.status = OrderStatus.OPEN
            order.order_time = result['transactTime']
            order.save()
            sync_mexc_order(order.id)
            get_mexc_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e, exc_info=True)
        order.status = OrderStatus.ERROR

@shared_task
def sync_mexc_orders():
    try:
        orders = Order.objects.filter(is_trades_synced=False, exchange='MEXC')
    except Exception as e:
        logger.error(e, stack_info=True)
    for order in orders:
        try:
            symbol = f'{order.base_currency}{order.quote_currency}'
            sync_mexc_order(order.id, symbol)
        except Exception as e:
            logger.error(e, stack_info=True)

@shared_task
def cancel_mexc_order(order_id):
    try:
        order = Order.objects.get(id=order_id, status=OrderStatus.WAITING_FOR_CANCEL)
    except Exception as e:
        logger.error(e, stack_info=True)

    try:
        exchange_account = order.exchange_account
        cli = MexcExchange(exchange_account.api_key,
                                exchange_account.api_secret,
                                pass_phrase=exchange_account.pass_phrase)
        symbol = f'{order.base_currency}{order.quote_currency}'
        result = cli.cancel_order(
            order.order_id, symbol)
        print('#' * 50)
        print(result)
        order.status = OrderStatus.CANCELLIING
        order.save()
        sync_mexc_order(order_id)
        get_mexc_spot_account_info(exchange_account.id)
    # except ApiException as
    except Exception as e:
        logger.error(e, stack_info=True)
    finally:
        order.save()

@shared_task
def get_mexc_account_detail(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'MEXC':
            if not exchange_account.user_id:
                exchange_account.user_id = uuid.uuid4().hex
                exchange_account.save()
            get_mexc_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e)

@shared_task
def sync_mexc_spot_account_balance():
    exchange_accounts = ExchangeAccount.objects.all()
    for exchange_account in exchange_accounts:
        if exchange_account.exchange.code == 'MEXC':
            try:
                get_mexc_spot_account_info(exchange_account.id)
            except Exception as e:
                logger.error(e)

@shared_task
def get_mexc_spot_account_info(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'MEXC':
            cli = MexcExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                pass_phrase=exchange_account.pass_phrase)
            resp = cli.get_wallet_balance()
            print('#' * 50)
            print(resp)
            balances = resp.get('balances', [])
      
            for item in balances:
                available = Decimal(item['free'])
                locked = Decimal(item['locked'])
                balance = available + locked
                Wallet.objects.update_or_create(
                    user_id=exchange_account.user_id,
                    exchange=exchange_account.exchange.code,
                    exchange_account=exchange_account,
                    currency=item['asset'],
                    type=WalletType.SPOT,
                    defaults={
                        'balance': balance,
                        'frozen': locked,
                        'available': available
                    },
                    create_defaults={
                        'balance': balance,
                        'frozen': locked,
                        'available': available
                    }
                )
    except Exception as e:
        logger.error(e)






@shared_task
def sync_okx_order(order_id):
    try:
        order = Order.objects.get(id = order_id)
    except Exception as e:
        logger.error(e, stack_info=True)

    try:
        exchange_account = order.exchange_account
        cli = OKXExchange(
            exchange_account.api_key, exchange_account.api_secret,
            pass_phrase=exchange_account.pass_phrase)
        result = cli.get_order(
            order.order_id, order.symbol)
        order.status = result.status
        order.size = result.size
        order.price = result.price
        order.amount = result.amount
        order.raw = result.raw
        order.order_time = result.order_time
        order.update_time = result.update_time

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            order.is_trades_synced = True
    except Exception as e:
        logger.error(e, stack_info=True)
    finally:
        order.save()

@shared_task
def place_okx_order(order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if order.exchange == 'OKX':
            exchange_account = order.exchange_account
            cli = OKXExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                 pass_phrase=exchange_account.pass_phrase)
            order_data = order.to_okx_place_order()
            logger.info('#' * 50)
            logger.info(order_data)
            resp = cli.place_oder(order_data)
            logger.info('#' * 50)
            logger.info(resp)
            result = resp.get('data', [])
            data = result[0]
            if data.get('sCode') == '0':
                order.order_id = data['ordId']
                order.order_code = data['clOrdId']
                order.status = OrderStatus.OPEN
            else:
                order.status = OrderStatus.ERROR
            order.save()
            sync_okx_order(order.id)
            get_okx_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e, exc_info=True)
        order.status = OrderStatus.ERROR

@shared_task
def sync_okx_orders():
    try:
        orders = Order.objects.filter(is_trades_synced=False, exchange='OKX')
    except Exception as e:
        logger.error(e, stack_info=True)
    for order in orders:
        try:
            sync_okx_order(order.id)
        except Exception as e:
            logger.error(e, stack_info=True)

@shared_task
def cancel_okx_order(order_id):
    try:
        order = Order.objects.get(id=order_id, status=OrderStatus.WAITING_FOR_CANCEL)
    except Exception as e:
        logger.error(e, stack_info=True)

    try:
        exchange_account = order.exchange_account
        cli = OKXExchange(exchange_account.api_key,
                                exchange_account.api_secret,
                                pass_phrase=exchange_account.pass_phrase)
        result = cli.cancel_order(
            order.order_id, order.symbol)
        print('#' * 50)
        print(result)
        order.status = OrderStatus.CANCELLIING
        order.save()
        sync_okx_order(order_id)
        get_okx_spot_account_info(exchange_account.id)
    # except ApiException as
    except Exception as e:
        logger.error(e, stack_info=True)
    finally:
        order.save()

@shared_task
def get_okx_account_detail(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'OKX':
            cli = OKXExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                 pass_phrase=exchange_account.pass_phrase)
            resp = cli.get_account_info()
            logger.info('#' * 50)
            logger.info(resp)
            result = resp.get('data', [])
            account_info = result[0]
            exchange_account.user_id = account_info.get('uid')
            exchange_account.save()
            get_okx_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e)

@shared_task
def sync_okx_spot_account_balance():
    exchange_accounts = ExchangeAccount.objects.all()
    for exchange_account in exchange_accounts:
        if exchange_account.exchange.code == 'OKX':
            try:
                get_okx_spot_account_info(exchange_account.id)
            except Exception as e:
                logger.error(e)

@shared_task
def get_okx_spot_account_info(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'OKX':
            cli = OKXExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                pass_phrase=exchange_account.pass_phrase)
            resp = cli.get_wallet_balance()
            print('#' * 50)
            print(resp)
            results = resp.get('data', [])
            details = results[0].get('details', [])

            if len(results) > 0:
                for item in details:
                    available = Decimal(item['availBal'])
                    locked = Decimal(item['frozenBal'])
                    balance = Decimal(item['cashBal'])
                    Wallet.objects.update_or_create(
                        user_id=exchange_account.user_id,
                        exchange=exchange_account.exchange.code,
                        exchange_account=exchange_account,
                        currency=item['ccy'],
                        type=WalletType.SPOT,
                        defaults={
                            'balance': balance,
                            'frozen': locked,
                            'available': available
                        },
                        create_defaults={
                            'balance': balance,
                            'frozen': locked,
                            'available': available
                        }
                    )
    except Exception as e:
        logger.error(e)


@shared_task
def sync_binance_order(order_id):
    try:
        order = Order.objects.get(id = order_id)
    except Exception as e:
        logger.error(e, stack_info=True)

    try:
        exchange_account = order.exchange_account
        cli = BinanceExchange(
            exchange_account.api_key, exchange_account.api_secret,
            pass_phrase=exchange_account.pass_phrase)
        symbol = f'{order.base_currency}{order.quote_currency}'
        print('#' * 50)
        print(symbol, order.order_id)
        result = cli.get_order(
            order.order_id, symbol)
        print(result)
        order.status = result.status
        order.size = result.size
        order.price = result.price
        order.amount = result.amount
        order.raw = result.raw
        order.order_time = result.order_time
        order.update_time = result.update_time

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            order.is_trades_synced = True
    except Exception as e:
        print(e)
        logger.error(e, stack_info=True)
    finally:
        order.save()

@shared_task
def place_binance_order(order_id):
    try:
        order = Order.objects.get(id=order_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if order.exchange == 'BINANCE':
            exchange_account = order.exchange_account
            cli = BinanceExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                 pass_phrase=exchange_account.pass_phrase)
            order_data = order.to_binance_place_order()
            logger.info('#' * 50)
            logger.info(order_data)
            resp = cli.place_oder(order_data)
            logger.info('#' * 50)
            logger.info(resp)
            if resp.get("orderId"):
                order.order_id = resp['orderId']
                order.order_code = resp['clientOrderId']
                order.status = OrderStatus.OPEN
            else:
                order.status = OrderStatus.ERROR
            order.save()
            sync_binance_order(order.id)
            get_binance_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e, exc_info=True)
        order.status = OrderStatus.ERROR

@shared_task
def sync_binance_orders():
    try:
        orders = Order.objects.filter(is_trades_synced=False, exchange='BINANCE')
    except Exception as e:
        logger.error(e, stack_info=True)
    for order in orders:
        try:
            sync_binance_order(order.id)
        except Exception as e:
            logger.error(e, stack_info=True)

@shared_task
def cancel_binance_order(order_id):
    try:
        order = Order.objects.get(id=order_id, status=OrderStatus.WAITING_FOR_CANCEL)
    except Exception as e:
        logger.error(e, stack_info=True)

    try:
        exchange_account = order.exchange_account
        cli = BinanceExchange(exchange_account.api_key,
                                exchange_account.api_secret,
                                pass_phrase=exchange_account.pass_phrase)
        symbol = f'{order.base_currency}{order.quote_currency}'
        result = cli.cancel_order(
            order.order_id, symbol)
        print('#' * 50)
        print(result)
        order.status = OrderStatus.CANCELLIING
        order.save()
        sync_binance_order(order_id)
        get_binance_spot_account_info(exchange_account.id)
    # except ApiException as
    except Exception as e:
        logger.error(e, stack_info=True)
    finally:
        order.save()

@shared_task
def get_binance_account_detail(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'BINANCE':
            cli = BinanceExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                 pass_phrase=exchange_account.pass_phrase)
            resp = cli.get_account_info()
            logger.info('#' * 50)
            logger.info(resp)
            uid = resp.get('uid')
            exchange_account.user_id = uid
            exchange_account.save()
            get_binance_spot_account_info(exchange_account.id)
    except Exception as e:
        logger.error(e)

@shared_task
def sync_binance_spot_account_balance():
    exchange_accounts = ExchangeAccount.objects.all()
    for exchange_account in exchange_accounts:
        if exchange_account.exchange.code == 'BINANCE':
            try:
                get_binance_spot_account_info(exchange_account.id)
            except Exception as e:
                logger.error(e)

@shared_task
def get_binance_spot_account_info(exchange_account_id):
    try:
        exchange_account = ExchangeAccount.objects.get(id=exchange_account_id)
    except Exception as e:
        logger.error(e)
        return
    try:
        if exchange_account.exchange.code == 'BINANCE':
            cli = BinanceExchange(exchange_account.api_key,
                                 exchange_account.api_secret,
                                pass_phrase=exchange_account.pass_phrase)
            results = cli.get_wallet_balance()
            print('#' * 50)
            print(results)
            if len(results) > 0:
                for item in results:
                    available = Decimal(item['free'])
                    locked = Decimal(item['locked'])
                    balance = available + locked
                    Wallet.objects.update_or_create(
                        user_id=exchange_account.user_id,
                        exchange=exchange_account.exchange.code,
                        exchange_account=exchange_account,
                        currency=item['asset'],
                        type=WalletType.SPOT,
                        defaults={
                            'balance': balance,
                            'frozen': locked,
                            'available': available
                        },
                        create_defaults={
                            'balance': balance,
                            'frozen': locked,
                            'available': available
                        }
                    )
    except Exception as e:
        logger.error(e)