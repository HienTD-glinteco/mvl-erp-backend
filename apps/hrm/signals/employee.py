"""Signal handlers for Employee model."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.hrm.models import Employee

User = get_user_model()


@receiver(post_save, sender=Employee)
def create_user_for_employee(sender, instance, created, **kwargs):  # noqa: ARG001
    """Create a User instance for the Employee after it is created.

    This signal handler automatically creates a User account when an Employee
    is created. It uses the employee's username and email fields.
    """
    # Only create user if employee was just created and doesn't have a user yet
    if created and not instance.user:
        user = User.objects.create_user(
            username=instance.username,
            email=instance.email,
            first_name=instance.fullname.split()[0] if instance.fullname else "",
            last_name=" ".join(instance.fullname.split()[1:]) if len(instance.fullname.split()) > 1 else "",
            phone_number=instance.phone,
        )
        # Update the employee with the created user
        instance.user = user
        instance.save(update_fields=["user"])
