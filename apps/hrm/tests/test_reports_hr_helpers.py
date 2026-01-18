"""Tests for recruitment reports helpers.

This module tests helper functions used in recruitment reports processing.
"""

from unittest.mock import patch

import pytest

from apps.hrm.tasks.reports_recruitment import helpers as rec_helpers


@pytest.mark.parametrize(
    "event_type, previous, current, expected_calls",
    [
        ("create", None, {"status": rec_helpers.RecruitmentCandidate.Status.HIRED}, 1),
        ("delete", {"status": rec_helpers.RecruitmentCandidate.Status.HIRED}, None, 1),
        (
            "update",
            {"status": rec_helpers.RecruitmentCandidate.Status.HIRED},
            {"status": "NOT_HIRED"},
            1,
        ),
        (
            "update",
            {"status": "NOT_HIRED"},
            {"status": rec_helpers.RecruitmentCandidate.Status.HIRED},
            1,
        ),
        (
            "update",
            {"status": rec_helpers.RecruitmentCandidate.Status.HIRED},
            {"status": rec_helpers.RecruitmentCandidate.Status.HIRED},
            2,
        ),
    ],
)
def test_increment_recruitment_reports_calls_process_as_expected(event_type, previous, current, expected_calls):
    snapshot = {"previous": previous, "current": current}

    with patch.object(rec_helpers, "_process_recruitment_change") as mock_proc:
        rec_helpers._increment_recruitment_reports(event_type, snapshot)
        assert mock_proc.call_count == expected_calls
