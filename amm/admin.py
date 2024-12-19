from typing import Optional
from django.http import HttpRequest
from django_otp.admin import OTPAdminAuthenticationForm
from unfold.sites import UnfoldAdminSite
from unfold.widgets import BASE_INPUT_CLASSES



class CustomLoginForm(OTPAdminAuthenticationForm):
    def __init__(
        self,
        request: Optional[HttpRequest] = None,        *args,
        **kwargs,
    ) -> None:
        super().__init__(request, *args, **kwargs)

        self.fields["username"].widget.attrs["class"] = " ".join(BASE_INPUT_CLASSES)
        self.fields["password"].widget.attrs["class"] = " ".join(BASE_INPUT_CLASSES)
        self.fields["otp_device"].widget.attrs["class"] = " ".join(BASE_INPUT_CLASSES)
        self.fields["otp_token"].widget.attrs["class"] = " ".join(BASE_INPUT_CLASSES)


class CustomAdminSite(UnfoldAdminSite):
    login_form = CustomLoginForm

    def __init__(self, name='admin'):
        print("CustomAdminSite")
        super().__init__(name)

    def has_permission(self, request):
        """
        In addition to the default requirements, this only allows access to
        users who have been verified by a registered OTP device.
        """
        return super().has_permission(request) and request.user.is_verified()

customAdminSite = CustomAdminSite()