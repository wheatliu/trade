# Register your models here.
from collections.abc import Callable, Sequence
from typing import Any
from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _

from unfold.admin import ModelAdmin
from guardian.admin import GuardedModelAdmin
from unfold.decorators import action, display
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from system.models import Project, Exchange, ExchangeAccount, CurrencyPair, Traders

from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from unfold.forms import UserCreationForm
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp.plugins.otp_totp.admin import TOTPDeviceAdmin


from order.tasks import (
    get_gateio_account_detail, get_kucoin_account_detail,
    get_bybit_account_detail, get_mexc_account_detail,
    get_okx_account_detail)


from django_celery_beat.models import (
    ClockedSchedule,
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
    SolarSchedule,
)

from amm.admin import customAdminSite


admin.site.unregister(PeriodicTask)
admin.site.unregister(IntervalSchedule)
admin.site.unregister(CrontabSchedule)
admin.site.unregister(SolarSchedule)
admin.site.unregister(ClockedSchedule)
admin.site.unregister(Group)
# admin.site.unregister(User)

admin.site = customAdminSite


# @admin.register(PeriodicTask)
class PeriodicTaskAdmin(ModelAdmin):
    pass

admin.site.register(PeriodicTask, PeriodicTaskAdmin)

# @admin.register(IntervalSchedule)
class IntervalScheduleAdmin(ModelAdmin):
    pass

admin.site.register(IntervalSchedule, IntervalScheduleAdmin)

# @admin.register(CrontabSchedule)
class CrontabScheduleAdmin(ModelAdmin):
    pass

admin.site.register(CrontabSchedule, CrontabScheduleAdmin)

# @admin.register(SolarSchedule)
class SolarScheduleAdmin(ModelAdmin):
    pass

admin.site.register(SolarSchedule, SolarScheduleAdmin)

# @admin.register(ClockedSchedule)
class ClockedScheduleAdmin(ModelAdmin):
    pass

admin.site.register(ClockedSchedule, ClockedScheduleAdmin)

class CreateTraderForm(UserCreationForm):
    class Meta:
        model = Traders
        fields = ("email", "is_trader")
    
# @admin.register(Traders)
class TradersAdmin(BaseUserAdmin, ModelAdmin):
    add_form = CreateTraderForm
    model = Traders
    list_display = ("username", "email", "is_active", "date_joined", "is_trader")
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username", "email", "password1", "password2", "is_trader", "is_superuser",
                "is_active",
            )}
        ),
    )

admin.site.register(Traders, TradersAdmin)

# @admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    pass

admin.site.register(Group, GroupAdmin)

# @admin.register(Project)
class ProjectAdmin(ModelAdmin):
    list_display = ['name', 'description', 'start_date', 'end_date', 'is_active']

admin.site.register(Project, ProjectAdmin)

# @admin.register(Exchange)
class ExchangeAdmin(ModelAdmin):
    list_display = ['name', 'code',  'description', 'symbol_delimiter']

admin.site.register(Exchange, ExchangeAdmin)

class CurrencyPairInline(TabularInline):
    model = CurrencyPair
    fields = ["base_currency", "quote_currency", "symbol", "symbol_delimiter", "base_min_size", "quote_min_size", "is_active"]
    extra = 0
    max_num = 10

# @admin.register(ExchangeAccount)
class ExchangeAccountAdmin(ModelAdmin, GuardedModelAdmin):
    list_display = ['name', 'exchange', 'project', 'display_api_key',  'is_active']
    create_fields = ['name', 'exchange', 'project', 'api_key', 'api_secret', 'pass_phrase', 'is_active']
    view_fields = ['name', 'exchange', 'project', 'api_key', 'is_active']
    inlines = [CurrencyPairInline]

    def has_delete_permission(self, request: HttpRequest, obj: Any | None = ...) -> bool:
        return False

    def get_fields(self, request: HttpRequest, obj: Any | None = ...) -> Sequence[Callable[..., Any] | str]:
        if obj is None:
            return self.create_fields
        return self.view_fields
    
    @display(description=_("API Key"))
    def display_api_key(self, obj):
        api_key = obj.api_key
        return f"{api_key[:8]}{'*' * (len(api_key) - 12)}{api_key[-4:]}"
    

    def response_change(self, request, obj):
        if obj.exchange.code == 'BYBIT':
            get_bybit_account_detail.delay(obj.id)
        if obj.exchange.code == 'KUCOIN':
            get_kucoin_account_detail.delay(obj.id)
        elif obj.exchange.code == 'GATEIO':
            get_gateio_account_detail.delay(obj.id)
        elif obj.exchange.code == 'MEXC':
            get_mexc_account_detail.delay(obj.id)
        elif obj.exchange.code == 'OKX':
            get_okx_account_detail.delay(obj.id)
        return super().response_add(request, obj)

admin.site.register(ExchangeAccount, ExchangeAccountAdmin)

class CustomTOTPDeviceAdmin(TOTPDeviceAdmin, ModelAdmin):
    pass

# admin.site.unregister(TOTPDevice)
admin.site.register(TOTPDevice, CustomTOTPDeviceAdmin)