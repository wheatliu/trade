from django.contrib.admin.apps import AdminConfig


class AmmAdminConfig(AdminConfig):
    default_site = "amm.admin.CustomAdminSite"