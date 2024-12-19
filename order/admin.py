from collections import defaultdict
from typing import Any, Dict
from decimal import Decimal, ROUND_DOWN
from django.contrib import admin
from django.http import HttpRequest
from django.utils.safestring import mark_safe
from django.template.response import TemplateResponse
from unfold.decorators import action, display
from import_export.admin import ImportExportModelAdmin
from unfold.contrib.import_export.forms import ExportForm
from import_export import resources


from django.utils.translation import gettext_lazy as _


from unfold.admin import ModelAdmin
# Register your models here.
from .models import Order, OrderStatus, OrderSide, Wallet

from system.models import ExchangeAccount, Exchange
from amm.admin import customAdminSite

admin.site = customAdminSite
# @admin.register(Order)
class ExchangeAdmin(ModelAdmin):
    list_display = ('id','exchange', 'display_exchange_account', 'order_id', 'order_code', 'display_side', 'symbol', 'type', 'display_price', 'display_size', 'display_amount', 'display_status', 'action')
    # fields = ('exchange', 'exchange_account', 'symbol', 'type', 'side', 'size', 'amount', 'price', 'time_in_force', 'iceberg', 'status', 'fee', 'fee_currency', 'raw', 'order_time', 'is_trades_synced', 'operator')
    # readonly_fields = ('exchange', 'exchange_account', 'symbol', 'type', 'side', 'size', 'amount', 'price', 'time_in_force', 'iceberg', 'status', 'fee', 'fee_currency', 'raw', 'order_time', 'is_trades_synced', 'operator')
    change_list_template = "admin/orders.html"
    list_per_page = 15
    list_filter_submit = False
    list_filter = ('exchange', 'exchange_account', 'symbol', 'type', 'side', 'status')

    @display(description=_("Exchange Account"))
    def display_exchange_account(self, obj):
        return obj.exchange_account.name
    
    @display(description=_("Price"))
    def display_price(self, obj):
        if obj.price is not None:
            return f"{obj.price.quantize(Decimal('.0000000001'), rounding=ROUND_DOWN)}"
    
    @display(description=_("Size"))
    def display_size(self, obj):
        return f"{obj.size.quantize(Decimal('.01'), rounding=ROUND_DOWN)}"
    
    @display(description=_("Amount"))
    def display_amount(self, obj):
        return f"{obj.amount.quantize(Decimal('.01'), rounding=ROUND_DOWN)}"
    
    @display(
        description=_("Status"),
        label={
            OrderStatus.CANCELLED: "danger",
            OrderStatus.FILLED: "success",
            OrderStatus.ERROR: "danger",
            OrderStatus.OPEN: "info",
        },
    )
    def display_status(self, instance):
        if instance.status:
            return instance.status
        return None

    @display(
            description=_("Side"),
            label={
                OrderSide.BUY: "success",
                OrderSide.SELL: "danger",
            },)
    def display_side(self, obj):
        return obj.side

    def action(self, obj):
        if obj.status == "open":
            return mark_safe(f'<button type="button" class="p-1 text-white text-xs shadow-sm rounded" style="background-color: #f2495e;" x-on:click="cancelOrder({obj.id})">Cancel</button>')
    
    def has_change_permission(self, request: HttpRequest, obj: Any | None = ...) -> bool:
        return False
    
    def has_delete_permission(self, request: HttpRequest, obj: Any | None = ...) -> bool:
        return False
    
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    # def changelist_view(self, request: HttpRequest, extra_context: Dict[str, str] | None = None) -> TemplateResponse:
    #     accounts = ExchangeAccount.objects.prefetch_related('exchange').all()
    #     market_prices = 3156.43
    #     symbol_mapping = defaultdict(list)
    #     exchanges = {}
    #     for account in accounts:
    #         currency_pairs = account.currency_pairs.all()
    #         symbols = [currency_pair.symbol for currency_pair in currency_pairs]
    #         symbol_mapping[account] = symbols
    #         if account.exchange.code not in exchanges:
    #             exchanges[account.exchange.code] = {'name':account.exchange.name, 'value': account.exchange.code}
    #     extra_context = {
    #         "title": "Order Management",
    #         "market_prices": market_prices,
    #         "symbol_mapping": symbol_mapping,
    #         "exchanges": list(exchanges.values())
    #     }
    #     return super().changelist_view(request, extra_context)

admin.site.register(Order, ExchangeAdmin)

class WalletResource(resources.ModelResource):
    class Meta:
        model = Wallet
        fields = ['id', 'exchange', 'exchange_account', 'currency', 'balance', 'frozen', 'available', 'update_time']

# @admin.register(Wallet)
class WalletAdmin(ModelAdmin, ImportExportModelAdmin):
    resource_classes = [WalletResource]
    skip_export_form = True
    list_display = ('id', 'exchange', 'exchange_account', 'currency', 'balance', 'frozen', 'available')

    def has_change_permission(self, request: HttpRequest, obj: Any | None = ...) -> bool:
        return False
    
    def has_delete_permission(self, request: HttpRequest, obj: Any | None = ...) -> bool:
        return False
    
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

admin.site.register(Wallet, WalletAdmin)