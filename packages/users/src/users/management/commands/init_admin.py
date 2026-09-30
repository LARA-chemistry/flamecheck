#!/usr/bin/python3
# Create a Django admin user if no users exist.
# Thanks to  Pina Merkert (pmk@ct.de, https://github.com/pinae/Nutria-DB )

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Command to initialise the django admin user."""

    def handle(self, *args, **options):
        """Dispatcher based on command line arguments/options."""
        if get_user_model().objects.count() == 0:
            new_admin = get_user_model().objects.create_superuser(
                username=os.getenv("DJANGO_SUPERUSER_USERNAME", "admin"),
                email=os.getenv("DJANGO_SUPERUSER_MAIL", "admin@example.com"),
                password=os.getenv("DJANGO_SUPERUSER_PASSWORD", "yxcv4321"),
            )
            new_admin.save()
            # Debug (do NOT print the password):
            # print(f"created superuser: {os.getenv('DJANGO_SUPERUSER', 'admin')}")
            print("Django Admin/Superuser account created")
        else:
            print("Admin accounts can only be initialized if no Accounts exist")
