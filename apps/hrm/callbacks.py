"""Callback functions for mail template actions in HRM module."""

from django.utils import timezone


def mark_employee_onboarding_email_sent(employee_instance, recipient, **kwargs):
    """Mark employee onboarding email as sent.

    Args:
        employee_instance: The Employee instance
        recipient: EmailSendRecipient instance
        **kwargs: Additional callback parameters
    """
    employee_instance.is_onboarding_email_sent = True
    employee_instance.save(update_fields=["is_onboarding_email_sent"])


def mark_interview_candidate_email_sent(interview_schedule_instance, recipient, **kwargs):
    """Mark interview candidate email as sent.

    Args:
        interview_schedule_instance: The InterviewSchedule instance
        recipient: EmailSendRecipient instance
        **kwargs: Additional callback parameters
    """
    if not recipient.callback_data or not recipient.callback_data.get("interview_candidate_id"):
        return

    interview_candidate_id = recipient.callback_data.get("interview_candidate_id")
    print(interview_schedule_instance)
    interview_schedule_instance.interview_candidates.filter(id=interview_candidate_id).update(
        email_sent_at=timezone.now()
    )
