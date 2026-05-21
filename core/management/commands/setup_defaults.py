"""Create default store and demo staff user if missing."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from core.models import Store
from core.roles import GROUP_CAJERO, setup_role_groups


class Command(BaseCommand):
    help = "Ensure default Store and a demo login user exist."

    def handle(self, *args, **options):
        store_defaults = {
            "name": "Ferretería Central",
            "is_default": True,
            "location": "Av. Insurgentes Sur 123, Col. Del Valle, CDMX",
            "phone": "55 5555 1234",
            "rfc": "FER123456ABC",
        }
        store, created = Store.objects.get_or_create(
            code="principal",
            defaults=store_defaults,
        )
        if not created:
            updated = False
            for field, value in store_defaults.items():
                if field == "is_default":
                    continue
                if not getattr(store, field) and value:
                    setattr(store, field, value)
                    updated = True
            if updated:
                store.save()
        if not created and not store.is_default:
            store.is_default = True
            store.save(update_fields=["is_default"])

        setup_role_groups()
        cajero = Group.objects.get(name=GROUP_CAJERO)

        User = get_user_model()
        user, u_created = User.objects.get_or_create(
            username="demo",
            defaults={"is_staff": False},
        )
        user.groups.set([cajero])
        user.is_staff = False
        user.is_superuser = False
        if u_created or not user.has_usable_password():
            user.set_password("demo")
        user.save()
        store.assigned_users.add(user)
        if u_created:
            self.stdout.write(
                self.style.SUCCESS("Usuario demo / demo (grupo Cajero) creado.")
            )
        else:
            self.stdout.write("Usuario demo actualizado → grupo Cajero.")

        self.stdout.write(self.style.SUCCESS(f"Tienda: {store.name} ({store.code})"))
        self.stdout.write(
            "Roles: python manage.py setup_roles --demo-users "
            "(encargado/gerente con permisos ampliados)."
        )
