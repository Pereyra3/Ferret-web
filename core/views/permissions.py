"""Permission mixins for ferreteria CBVs."""

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.views import redirect_to_login


class FerreteriaPermissionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Login redirect first; 403 only when logged in but missing permission."""

    login_url = "login"
    raise_exception = True

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect_to_login(
                self.request.get_full_path(),
                self.get_login_url(),
                self.get_redirect_field_name(),
            )
        return PermissionRequiredMixin.handle_no_permission(self)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not self.has_permission():
            return self.handle_no_permission()
        return super(PermissionRequiredMixin, self).dispatch(request, *args, **kwargs)


class CanViewSalesMixin(FerreteriaPermissionMixin):
    permission_required = "sales.view_sale"


class CanAddSaleMixin(FerreteriaPermissionMixin):
    permission_required = "sales.add_sale"


class CanChangeSaleMixin(FerreteriaPermissionMixin):
    permission_required = "sales.change_sale"


class CanRunEodMixin(FerreteriaPermissionMixin):
    permission_required = "sales.add_dayclose"


class CanViewQuotesMixin(FerreteriaPermissionMixin):
    permission_required = "sales.view_quote"


class CanAddQuoteMixin(FerreteriaPermissionMixin):
    permission_required = "sales.add_quote"


class CanChangeQuoteMixin(FerreteriaPermissionMixin):
    permission_required = "sales.change_quote"


class CanConvertQuoteToSaleMixin(FerreteriaPermissionMixin):
    permission_required = ("sales.add_sale", "sales.view_quote")


class CanViewProductsMixin(FerreteriaPermissionMixin):
    permission_required = "warehouse.view_product"


class CanChangeProductMixin(FerreteriaPermissionMixin):
    permission_required = "warehouse.change_product"


class CanAddProductMixin(FerreteriaPermissionMixin):
    permission_required = "warehouse.add_product"


class CanViewStockMixin(FerreteriaPermissionMixin):
    permission_required = "warehouse.view_stocklevel"


class CanChangeStockMixin(FerreteriaPermissionMixin):
    permission_required = "warehouse.change_stocklevel"


class CanAddPurchaseMixin(FerreteriaPermissionMixin):
    permission_required = "warehouse.add_purchase"


class CanAddSupplierPaymentMixin(FerreteriaPermissionMixin):
    permission_required = "warehouse.add_supplierpayment"


class CanViewDashboardMixin(FerreteriaPermissionMixin):
    permission_required = (
        "sales.view_sale",
        "warehouse.view_supplierpayment",
    )


class CanChangeStoreScopeMixin(FerreteriaPermissionMixin):
    permission_required = "core.change_store"


class CanAddStockTransferMixin(FerreteriaPermissionMixin):
    permission_required = "warehouse.add_stocktransfer"


class CanViewStockTransferMixin(FerreteriaPermissionMixin):
    permission_required = "warehouse.view_stocktransfer"


class CanChangeStockTransferMixin(FerreteriaPermissionMixin):
    permission_required = "warehouse.change_stocktransfer"
