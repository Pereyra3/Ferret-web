"""Role groups built from Django's default model permissions."""

from django.contrib.auth.models import Group, Permission

GROUP_CAJERO = "Cajero"
GROUP_ENCARGADO = "Encargado"
GROUP_GERENTE = "Gerente"

APP_LABELS = ("core", "warehouse", "sales")

# Codenames: app_label.codename
CAJERO_PERMISSIONS = (
    "sales.add_sale",
    "sales.change_sale",
    "sales.view_sale",
    "sales.add_saleline",
    "sales.change_saleline",
    "sales.view_saleline",
    "sales.add_quote",
    "sales.change_quote",
    "sales.view_quote",
    "sales.add_quoteline",
    "sales.change_quoteline",
    "sales.view_quoteline",
    "warehouse.view_product",
    "warehouse.view_stocklevel",
)

ENCARGADO_EXTRA_PERMISSIONS = (
    "warehouse.add_product",
    "warehouse.change_product",
    "warehouse.add_supplier",
    "warehouse.change_supplier",
    "warehouse.view_supplier",
    "warehouse.add_stocklevel",
    "warehouse.change_stocklevel",
    "warehouse.view_stockmovement",
    "warehouse.add_purchase",
    "warehouse.change_purchase",
    "warehouse.view_purchase",
    "warehouse.add_purchaseline",
    "warehouse.change_purchaseline",
    "warehouse.view_purchaseline",
    "warehouse.add_supplierpayment",
    "warehouse.change_supplierpayment",
    "warehouse.view_supplierpayment",
    "warehouse.add_stocktransfer",
    "warehouse.change_stocktransfer",
    "warehouse.view_stocktransfer",
    "warehouse.add_stocktransferline",
    "warehouse.view_stocktransferline",
    "core.view_store",
)

def _permissions_for_codenames(codenames):
    found = []
    missing = []
    for full in codenames:
        app_label, codename = full.split(".", 1)
        perm = Permission.objects.filter(
            content_type__app_label=app_label, codename=codename
        ).first()
        if perm:
            found.append(perm)
        else:
            missing.append(full)
    return found, missing


def _all_app_permissions():
    return Permission.objects.filter(content_type__app_label__in=APP_LABELS)


def sync_group(name: str, permissions):
    group, _ = Group.objects.get_or_create(name=name)
    group.permissions.set(permissions)
    return group


def setup_role_groups(stdout_write=None):
    """Create/update Cajero, Encargado, Gerente groups."""
    cajero_perms, missing = _permissions_for_codenames(CAJERO_PERMISSIONS)
    if missing and stdout_write:
        stdout_write(f"Advertencia: permisos no encontrados (Cajero): {missing}")

    encargado_codenames = tuple(CAJERO_PERMISSIONS) + tuple(ENCARGADO_EXTRA_PERMISSIONS)
    encargado_perms, missing_e = _permissions_for_codenames(encargado_codenames)
    if missing_e and stdout_write:
        stdout_write(f"Advertencia: permisos no encontrados (Encargado): {missing_e}")

    gerente_perms = list(_all_app_permissions())

    cajero = sync_group(GROUP_CAJERO, cajero_perms)
    encargado = sync_group(GROUP_ENCARGADO, encargado_perms)
    gerente = sync_group(GROUP_GERENTE, gerente_perms)

    return cajero, encargado, gerente
