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


def mark_interview_candidate_email_sent(interview_candidate_instance, recipient, **kwargs):
    """Mark interview candidate email as sent.
    
    Args:
        interview_candidate_instance: The InterviewCandidate instance
        recipient: EmailSendRecipient instance
        **kwargs: Additional callback parameters
    """
    interview_candidate_instance.email_sent_at = timezone.now()
    interview_candidate_instance.save(update_fields=["email_sent_at"])
