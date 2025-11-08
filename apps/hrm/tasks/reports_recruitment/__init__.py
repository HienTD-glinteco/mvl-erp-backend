"""Recruitment Reports Aggregation Tasks Package.

This package contains Celery tasks for aggregating recruitment reporting data into
RecruitmentSourceReport, RecruitmentChannelReport, RecruitmentCostReport,
HiredCandidateReport, and StaffGrowthReport models.

Public API exports:
- aggregate_recruitment_reports_for_candidate: Event-driven task for candidate changes
- aggregate_recruitment_reports_batch: Scheduled batch task for daily reconciliation
"""

from .batch_tasks import aggregate_recruitment_reports_batch
from .event_tasks import aggregate_recruitment_reports_for_candidate

__all__ = [
    "aggregate_recruitment_reports_for_candidate",
    "aggregate_recruitment_reports_batch",
]
