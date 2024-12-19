import asyncio
from django.core.management.base import BaseCommand

from system.management.commands.gateio_spider import GateSider


class Command(BaseCommand):
    help = 'Run Spider'

    def add_arguments(self, parser):
        parser.add_argument('exchange', type=str, help='Please provide exchange name')
        parser.add_argument('account_name', type=str, help='Please provide account name')

    def handle(self, *args, **options):
        account_name = options['account_name']
        if options['exchange'] == 'gateio':
            spider = GateSider(account_name)
            asyncio.run(spider.connect())
