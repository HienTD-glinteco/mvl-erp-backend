from datetime import date
from unittest.mock import patch

import pytest

from apps.hrm.tasks.reports_hr import helpers as hr_helpers
from apps.hrm.tasks.reports_recruitment import helpers as rec_helpers


def make_transfer_data(report_date: date, branch_id=1, block_id=1, department_id=1, prev=None):
    return {
        "date": report_date,
        "name": hr_helpers.EmployeeWorkHistory.EventType.TRANSFER,
        "branch_id": branch_id,
        "block_id": block_id,
        "department_id": department_id,
        "previous_data": prev or {},
    }


def test_process_staff_growth_change_transfer_calls_update_for_both_source_and_destination():
    report_date = date(2025, 12, 1)
    prev = {"branch_id": 2, "block_id": 3, "department_id": 4}
    data = make_transfer_data(report_date, branch_id=1, block_id=10, department_id=11, prev=prev)

    with patch.object(hr_helpers, "_update_staff_growth_counter") as mock_update:
        hr_helpers._process_staff_growth_change(data, delta=1)

        # Should call twice: destination (+1) and source (-1)
        assert mock_update.call_count == 2
        # First call is destination increment
        dest_call = mock_update.call_args_list[0]
        # args: (report_date, branch_id, block_id, department_id, counter_field, delta, month_key, week_key)
        assert dest_call[0][4] == "num_transfers"
        assert dest_call[0][5] == 1
        # Second call is source decrement
        src_call = mock_update.call_args_list[1]
        assert src_call[0][0] == report_date
        assert src_call[0][1] == 2
        assert src_call[0][2] == 3
        assert src_call[0][4] == "num_transfers"
        assert src_call[0][5] == -1


def test_process_staff_growth_change_transfer_incomplete_previous_data_skips_source_update():
    report_date = date(2025, 12, 1)
    prev = {"branch_id": None}
    data = make_transfer_data(report_date, branch_id=1, block_id=10, department_id=11, prev=prev)

    with patch.object(hr_helpers, "_update_staff_growth_counter") as mock_update:
        hr_helpers._process_staff_growth_change(data, delta=1)

        # Should call only once for destination
        assert mock_update.call_count == 1


def test_process_staff_growth_change_change_status_return_from_leave_calls_num_returns():
    report_date = date(2025, 12, 1)
    previous_data = {"status": hr_helpers.Employee.Status.UNPAID_LEAVE}
    data = {
        "date": report_date,
        "name": hr_helpers.EmployeeWorkHistory.EventType.CHANGE_STATUS,
        "branch_id": 1,
        "block_id": 1,
        "department_id": 1,
        "status": hr_helpers.Employee.Status.ACTIVE,
        "previous_data": previous_data,
    }

    # Patch leave statuses and update counter
    with patch.object(
        hr_helpers.Employee.Status, "get_leave_statuses", return_value=[hr_helpers.Employee.Status.UNPAID_LEAVE]
    ):
        with patch.object(hr_helpers, "_update_staff_growth_counter") as mock_update:
            hr_helpers._process_staff_growth_change(data, delta=1)
            # Should call num_returns once
            assert mock_update.call_count == 1
            call = mock_update.call_args_list[0]
            # counter_field is arg index 4
            assert call[0][4] == "num_returns"


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
