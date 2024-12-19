from django.db import models
from pgcrypto import fields
from django.contrib.auth.models import PermissionsMixin,AbstractUser
from django.utils.translation import gettext_lazy as _

class ExchangeCodeChoices(models.TextChoices):
    BINANCE = "BINANCE", "BINANCE"
    OKX = "OKX", "OKX"
    GATEIO = "GATEIO", "GATEIO"
    BYBIT = "BYBIT", "BYBIT"
    KUCOIN = "KUCOIN", "KUCOIN"
    MEXC = "MEXC", "MEXC"
    NONE = "", "None"


class SymbolDelimiter(models.TextChoices):
    UNDERSCORE = "_", "_"
    SLASH = "/", "/"
    DASH = "-", "-"
    NONE = "", ""

# Create your models here.
class Traders(AbstractUser, PermissionsMixin):
    is_trader = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = _("Traders")
        verbose_name_plural = _("Traders")
        db_table = "traders"

# Create your models here.
class Project(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    operator = models.ForeignKey(Traders, on_delete=models.DO_NOTHING, blank=True, null=True, default=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'projects'
  
class Exchange(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=100, unique=True, choices=ExchangeCodeChoices.choices, default=ExchangeCodeChoices.NONE)
    symbol_delimiter = models.CharField(max_length=2,choices=SymbolDelimiter.choices, default=SymbolDelimiter.DASH)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    operator = models.ForeignKey(Traders, on_delete=models.DO_NOTHING, blank=True, null=True, default=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'exchanges'
        unique_together = ['code']

class ExchangeAccount(models.Model):
    name = models.CharField(max_length=100, unique=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    exchange = models.ForeignKey(Exchange, on_delete=models.DO_NOTHING, related_name='exchange_accounts')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, default=None)
    api_key = fields.TextPGPPublicKeyField()
    api_secret = fields.TextPGPPublicKeyField()
    pass_phrase = fields.TextPGPPublicKeyField(null=True, blank=True)
    user_id = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    enable_sync = models.BooleanField(default=False)
    operator = models.ForeignKey(Traders, on_delete=models.DO_NOTHING, blank=True, null=True, default=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']
        db_table = 'exchange_accounts'
        unique_together = ['project', 'exchange', 'name']

class CurrencyPair(models.Model):
    exchange_account = models.ForeignKey(ExchangeAccount, on_delete=models.DO_NOTHING, related_name='currency_pairs')
    base_currency = models.CharField(max_length=8)
    quote_currency = models.CharField(max_length=8)
    symbol = models.CharField(max_length=16, blank=True)
    symbol_delimiter = models.CharField(max_length=2, choices=SymbolDelimiter.choices, default=SymbolDelimiter.NONE)
    base_min_size = models.DecimalField(max_digits=32, decimal_places=8, blank=True)
    quote_min_size = models.DecimalField(max_digits=32, decimal_places=8, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.symbol
    
    class Meta:
        ordering = ['symbol']
        db_table = 'currency_pairs'
        unique_together = ['exchange_account', 'symbol']
