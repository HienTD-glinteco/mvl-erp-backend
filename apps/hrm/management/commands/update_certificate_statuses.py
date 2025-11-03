from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from apps.hrm.models import EmployeeCertificate


class Command(BaseCommand):
    help = _("Update certificate statuses based on expiry dates")

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be updated without making changes",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING(_("DRY RUN MODE - No changes will be made")))

        # Get all certificates
        certificates = EmployeeCertificate.objects.all()
        total_count = certificates.count()

        self.stdout.write(_("Processing {} certificates...").format(total_count))

        updated_count = 0
        status_changes = {"valid": 0, "near_expiry": 0, "expired": 0}

        for certificate in certificates:
            old_status = certificate.status
            new_status = certificate.compute_status()

            if old_status != new_status:
                updated_count += 1
                status_changes[new_status] += 1

                self.stdout.write(
                    _("Certificate {}: {} -> {}").format(certificate.id, old_status, new_status)
                )

                if not dry_run:
                    certificate.status = new_status
                    # Skip validation and signals by using update_fields
                    certificate.save(update_fields=["status", "updated_at"])

        # Summary
        self.stdout.write("\n" + _("Summary:"))
        self.stdout.write(_("Total certificates: {}").format(total_count))
        self.stdout.write(_("Certificates updated: {}").format(updated_count))
        self.stdout.write(_("  - Changed to VALID: {}").format(status_changes["valid"]))
        self.stdout.write(_("  - Changed to NEAR_EXPIRY: {}").format(status_changes["near_expiry"]))
        self.stdout.write(_("  - Changed to EXPIRED: {}").format(status_changes["expired"]))

        if dry_run:
            self.stdout.write(
                self.style.WARNING(_("\nNo changes made (dry run mode). Run without --dry-run to apply changes."))
            )
        else:
            self.stdout.write(self.style.SUCCESS(_("\nCertificate statuses updated successfully!")))
