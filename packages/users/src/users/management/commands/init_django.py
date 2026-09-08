"""
_____________________________________________________________________.

:PROJECT: {{ project_name }}

* django project intitialisation*

:details: initialise django project (run this only once !)
          this file is highly inspired by
          https://gitlab.com/mayan-edms/mayan-edms/-/blob/master/mayan/apps/common/management/commands/initialsetup.py
________________________________________________________________________
"""

from ast import Interactive
import os
import errno
from pathlib import Path
import logging

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.core.management.utils import get_random_secret_key
from django.core.exceptions import ImproperlyConfigured
from django.core.management.color import color_style, no_style
from django.db import DEFAULT_DB_ALIAS, connections
from django.conf import settings

from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Command to initialise the django project with default settings.

    see https://docs.djangoproject.com/en/1.9/howto/custom-management-commands/ for more details
    using now new argparse mechanism of django > 1.8.
    """

    # logging.basicConfig(format='%(levelname)s| %(module)s.%(funcName)s:%(message)s',
    #                     level=logging.DEBUG)  # level=logging.ERROR

    help = "Initialise the django project with default settings - run only once."

    def add_arguments(self, parser):
        """Command line arguments. s. https://docs.python.org/2/library/argparse.html#module-argparse."""
        # defining named commandline arguments
        parser.add_argument("-c", "--collect-static", action="store_true", help="collect static files into static dir")
        parser.add_argument("-n", "--no-fixtures", action="store_true", help="do not load fixtures")
        parser.add_argument("-d", "--load-demo-data", action="store_true", help="load demo data")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force execution of the initialization process.",
        )
        parser.add_argument(
            "--make-all-migrations",
            action="store_true",
            help="make all migrations, but do not reset and initialise database",
        )

    def handle(self, *args, **options):
        """Dispatcher based on command line arguments/options."""
        # check if database is initialised (i.e. auth_user table exists)
        connection = connections[DEFAULT_DB_ALIAS]
        db_initialised = "auth_group" in connection.introspection.table_names()

        logger.info(f"Django db initialised: {db_initialised}")

        if options["make_all_migrations"]:
            self.make_app_migrations(options)
        else:
            logger.info("initialising django project database....")

            if db_initialised and not options.get("force", False):
                logger.info("database already initialised, waiting for db....")
                call_command("wait_for_db")
                return
            else:
                self.initialise_django(force=options.get("force", False))

        if options["collect_static"]:
            call_command("collectstatic", "--noinput")  # interactive=False

        if not options["no_fixtures"] and not db_initialised:
            self.load_fixtures(options)

            # now create the admin / superuser
            call_command("init_admin")

        if options["load_demo_data"]:
            self.load_demo_data()

    def initialise_django(self, force=False):
        """
        Initialise django.

        :param force: force overwriting of all files, defaults to False
        :type force: bool, optional
        """
        # s. mayan
        # system_path = os.path.join(settings.MEDIA_ROOT, SYSTEM_DIR)
        # settings_path = os.path.join(settings.MEDIA_ROOT, 'hellodjango_settings')
        # secret_key_file_path = os.path.join(system_path, SECRET_KEY_FILENAME)

        call_command("wait_for_db")

        call_command("makemigrations")

        if self.num_migrations() > 0:
            logger.debug(f"unresolved {self.num_migrations()} migrations found")
            self.make_app_migrations()

        call_command("migrate")

    def num_migrations(self):
        """
        Return number of migrations.

        :param options:
        """
        from django.db.migrations.executor import MigrationExecutor

        try:
            executor = MigrationExecutor(connections[DEFAULT_DB_ALIAS])
        except ImproperlyConfigured:
            # No databases are configured (or the dummy one)
            return

        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            return len(plan)
        else:
            return 0

    def make_app_migrations(self, options=None):
        """
        Make individual app migrations.

        s. https://docs.djangoproject.com/en/2.0/ref/django-admin/
        :param options:
        """
        for app in settings.LOCAL_APPS:
            logger.debug(f"migrating : {app}")
            call_command("makemigrations", app)
        call_command("migrate")

    def load_fixtures(self, options=None):
        """
        Load fixtures the LOCAL database.

        :param options:
        """
        logger.info("initialising database with fixtures....")
        for fixture in settings.FIXTURES:
            call_command("loaddata", fixture)

    def load_demo_data(self, options=None):
        """
        Load demo data into the  database.

        :param options:
        """
        logger.info("loading demo data....")
        # if settings.DEMO_DATA is not None:
        #     for fixture in settings.DEMO_DATA:
        #         call_command("loaddata", fixture)
