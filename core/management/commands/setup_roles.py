from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from core.models import Store
from core.roles import GROUP_CAJERO, GROUP_ENCARGADO, GROUP_GERENTE, setup_role_groups


class Command(BaseCommand):
    help = "Create Cajero, Encargado and Gerente groups with Django model permissions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--demo-users",
            action="store_true",
            help="Create demo / encargado / gerente users (password = username).",
        )

    def handle(self, *args, **options):
        cajero, encargado, gerente = setup_role_groups(stdout_write=self.stdout.write)
        self.stdout.write(
            self.style.SUCCESS(
                f"Grupos: {cajero.name} ({cajero.permissions.count()} permisos), "
                f"{encargado.name} ({encargado.permissions.count()}), "
                f"{gerente.name} ({gerente.permissions.count()})."
            )
        )

        if options["demo_users"]:
            self._ensure_demo_users()

    def _ensure_demo_users(self):
        User = get_user_model()
        specs = (
            ("demo", GROUP_CAJERO, False),
            ("encargado", GROUP_ENCARGADO, False),
            ("gerente", GROUP_GERENTE, True),
        )
        for username, group_name, is_staff in specs:
            group = Group.objects.get(name=group_name)
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"is_staff": is_staff},
            )
            user.groups.set([group])
            user.is_staff = is_staff
            user.is_superuser = False
            if created or not user.has_usable_password():
                user.set_password(username)
            user.save()
            default_store = Store.objects.filter(is_default=True).first() or Store.objects.first()
            if default_store:
                default_store.assigned_users.add(user)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Usuario {username} / {username} → {group_name}"
                    + (" (staff, acceso /admin/)" if is_staff else "")
                )
            )
