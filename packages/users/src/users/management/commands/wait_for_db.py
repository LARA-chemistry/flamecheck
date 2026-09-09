#!/usr/bin/python3
# waiting for the database to be available.
# Thanks to  Pina Merkert (pmk@ct.de, https://github.com/pinae/Nutria-DB )

import time

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    """Command to wait for the database to be available."""

    def handle(self, *args, **options):
        """Dispatcher based on command line arguments/options."""
        print("Checking the connection to the database.")
        database_connected = False
        while not database_connected:
            try:
                connection.ensure_connection()
                database_connected = True
            except OperationalError:
                print(self.style.ERROR("Database still unavailable."), end="")
                print(" Waiting 1 second.")
                time.sleep(1)
        print(self.style.SUCCESS("Database available!"))
