"""Generate a personal barcode for a student."""

import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from users.models import StudentBarcode

User = get_user_model()


class Command(BaseCommand):
    """Create (or reset) the personal barcode for a student."""

    help = "Generate a unique personal barcode (FC-<user_id>-<uuid8>) for a student."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Username of the student.")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Regenerate and replace an existing barcode.",
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist:
            raise CommandError(f"User '{options['username']}' does not exist.") from None

        if not options["reset"]:
            existing = user.barcodes.filter(active=True).first()
            if existing is not None:
                self.stdout.write(self.style.SUCCESS(f"Barcode already exists: {existing.value}"))
                return

        barcode = StudentBarcode.objects.create(student=user, value=f"FC-{user.id}-{uuid.uuid4().hex[:8]}")
        self.stdout.write(self.style.SUCCESS(f"Created barcode: {barcode.value}"))
