from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from .views import CreateOrderView, CancelOrderView, ListAccountDetailView, ListExchangeDetailView

app_name = 'orders'
urlpatterns = [
    path('orders', CreateOrderView.as_view(), name="create_order"),
    path('orders/<int:pk>/', CancelOrderView.as_view(), name="cancel_order"),
    path('exchanges/', ListExchangeDetailView.as_view(), name='exchange_with_accounts'),
    path('exchanges/accounts/', ListAccountDetailView.as_view(), name='exchange_accounts')
]

urlpatterns = format_suffix_patterns(urlpatterns)