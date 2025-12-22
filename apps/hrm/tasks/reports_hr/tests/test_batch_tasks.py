from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.hrm.tasks.reports_hr import batch_tasks


@pytest.mark.django_db
class TestAggregateHRReportsBatch:
    @patch("apps.hrm.tasks.reports_hr.batch_tasks._aggregate_employee_status_for_date")
    @patch("apps.hrm.tasks.reports_hr.batch_tasks.Department.objects.filter")
    def test_daily_status_aggregation_for_all_departments(self, mock_dept_filter, mock_agg_status):
        # Setup: create mock departments
        branch = MagicMock()
        block = MagicMock()
        dept1 = MagicMock(branch=branch, block=block)
        dept2 = MagicMock(branch=branch, block=block)
        mock_dept_filter.return_value.select_related.return_value = [dept1, dept2]

        # Patch _get_reports_needing_refresh to return None, [] so only the new lines are tested
        with patch("apps.hrm.tasks.reports_hr.batch_tasks._get_reports_needing_refresh", return_value=(None, [])):
            result = batch_tasks.aggregate_hr_reports_batch()

        # Assert _aggregate_employee_status_for_date called for each department
        today = timezone.localdate()
        calls = [(today, dept1.branch, dept1.block, dept1), (today, dept2.branch, dept2.block, dept2)]
        actual_calls = [call.args for call in mock_agg_status.call_args_list]
        assert actual_calls == calls
        assert result == 0

    # Optionally, add more tests for the rest of the batch logic
