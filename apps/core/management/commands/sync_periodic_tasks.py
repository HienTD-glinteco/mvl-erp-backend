"""
Management command to synchronize Periodic Tasks from CELERY_BEAT_SCHEDULE.

This command creates or updates PeriodicTask records in the database
based on the static CELERY_BEAT_SCHEDULE configuration, allowing
management of scheduled tasks through Django Admin.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Sync periodic tasks from CELERY_BEAT_SCHEDULE to database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without applying them",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force update all tasks even if they exist",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", {})

        if not schedule:
            self.stdout.write(self.style.WARNING("No tasks found in CELERY_BEAT_SCHEDULE"))
            return

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for task_name, task_config in schedule.items():
            result = self._process_task(task_name, task_config, dry_run, force)
            if result == "created":
                created_count += 1
            elif result == "updated":
                updated_count += 1
            elif result == "skipped":
                skipped_count += 1

        # Summary
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Summary: {created_count} created, {updated_count} updated, {skipped_count} skipped")
        )

    def _process_task(self, task_name, task_config, dry_run, force):
        """Process a single task and return the action taken."""
        task_path = task_config.get("task")
        schedule_obj = task_config.get("schedule")
        task_args = task_config.get("args", [])
        task_kwargs = task_config.get("kwargs", {})

        if not task_path or not schedule_obj:
            self.stdout.write(self.style.WARNING(f"Skipping {task_name}: missing task or schedule"))
            return None

        # Determine schedule type and create/get schedule object
        schedule_instance, schedule_type = self._get_or_create_schedule(schedule_obj, dry_run)

        if schedule_instance is None:
            self.stdout.write(self.style.WARNING(f"Skipping {task_name}: unsupported schedule type"))
            return None

        # Check if task exists
        existing_task = PeriodicTask.objects.filter(name=task_name).first()

        if existing_task and not force:
            self.stdout.write(f"  [SKIP] {task_name} (already exists)")
            return "skipped"

        if dry_run:
            action = "UPDATE" if existing_task else "CREATE"
            self.stdout.write(f"  [DRY-RUN] Would {action}: {task_name}")
            return "updated" if existing_task else "created"

        return self._create_or_update_task(
            task_name, task_path, task_args, task_kwargs, schedule_instance, schedule_type, existing_task
        )

    def _create_or_update_task(
        self, task_name, task_path, task_args, task_kwargs, schedule_instance, schedule_type, existing_task
    ):
        """Create or update a PeriodicTask in the database."""
        task_data = {
            "task": task_path,
            "args": task_args,
            "kwargs": task_kwargs,
            "enabled": True,
        }

        # Set the appropriate schedule field
        if schedule_type == "crontab":
            task_data["crontab"] = schedule_instance
            task_data["interval"] = None
        elif schedule_type == "interval":
            task_data["interval"] = schedule_instance
            task_data["crontab"] = None

        if existing_task:
            for key, value in task_data.items():
                setattr(existing_task, key, value)
            existing_task.save()
            self.stdout.write(self.style.SUCCESS(f"  [UPDATE] {task_name}"))
            return "updated"

        PeriodicTask.objects.create(name=task_name, **task_data)
        self.stdout.write(self.style.SUCCESS(f"  [CREATE] {task_name}"))
        return "created"

    def _get_or_create_schedule(self, schedule_obj, dry_run):
        """
        Parse schedule object and return the corresponding database model instance.
        Returns (schedule_instance, schedule_type) tuple.
        """
        from celery.schedules import crontab

        # Handle crontab schedule
        if isinstance(schedule_obj, crontab):
            crontab_kwargs = {
                "minute": str(schedule_obj._orig_minute),
                "hour": str(schedule_obj._orig_hour),
                "day_of_week": str(schedule_obj._orig_day_of_week),
                "day_of_month": str(schedule_obj._orig_day_of_month),
                "month_of_year": str(schedule_obj._orig_month_of_year),
            }

            if dry_run:
                return (True, "crontab")  # Return truthy value for dry-run

            schedule_instance, _ = CrontabSchedule.objects.get_or_create(
                **crontab_kwargs,
                defaults={"timezone": settings.CELERY_TIMEZONE},
            )
            return (schedule_instance, "crontab")

        # Handle interval schedule (float or int seconds)
        if isinstance(schedule_obj, (int, float)):
            if dry_run:
                return (True, "interval")  # Return truthy value for dry-run

            schedule_instance, _ = IntervalSchedule.objects.get_or_create(
                every=int(schedule_obj),
                period=IntervalSchedule.SECONDS,
            )
            return (schedule_instance, "interval")

        return (None, None)
