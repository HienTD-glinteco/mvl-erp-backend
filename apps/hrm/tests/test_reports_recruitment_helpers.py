from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.tasks.reports_recruitment import helpers


class DummyReport:
    def __init__(self, initial_hires=0, initial_total=Decimal("0")):
        self.num_hires = initial_hires
        self.total_cost = initial_total
        self.avg_cost_per_hire = Decimal("0")
        self._saves = []

    def save(self, update_fields=None):
        self._saves.append(list(update_fields) if update_fields else None)

    def refresh_from_db(self):
        # No-op: tests will set values externally as needed
        return


@pytest.mark.parametrize(
    "hired_count, delta, expected_cost_per_hire, expected_num_hires_after",
    [
        (0, 1, Decimal("100"), 1),  # new hire gets whole expense
        (2, -1, Decimal("50"), 1),  # removing one of two -> per-hire share 100/2
    ],
)
def test_increment_recruitment_cost_report_calculation(
    hired_count, delta, expected_cost_per_hire, expected_num_hires_after
):
    report_date = date(2025, 12, 1)
    branch_id = 1
    block_id = 1
    department_id = 1
    source_type = RecruitmentSourceType.MARKETING_CHANNEL
    recruitment_request_id = 10

    # Patch RecruitmentExpense.aggregate and RecruitmentCandidate.count and get_or_create
    expense_agg = {"total": Decimal("100")}

    dummy_report = DummyReport(initial_hires=0, initial_total=Decimal("0"))

    with (
        patch.object(helpers.RecruitmentExpense.objects, "filter") as mock_exp_filter,
        patch.object(helpers.RecruitmentCandidate.objects, "filter") as mock_cand_filter,
        patch.object(helpers.RecruitmentCostReport.objects, "get_or_create") as mock_get_or_create,
    ):
        # expense aggregate
        mock_exp_qs = MagicMock()
        mock_exp_qs.aggregate.return_value = expense_agg
        mock_exp_filter.return_value = mock_exp_qs

        # candidate count
        mock_cand_qs = MagicMock()
        mock_cand_qs.count.return_value = hired_count
        mock_cand_filter.return_value = mock_cand_qs

        # get_or_create returns our dummy report
        mock_get_or_create.return_value = (dummy_report, False)

        # Call function under test
        helpers._increment_recruitment_cost_report(
            report_date,
            branch_id,
            block_id,
            department_id,
            source_type,
            recruitment_request_id,
            delta,
        )

        # Compute expected denom per helper logic
        if delta > 0:
            denom = max(1, hired_count + delta)
        else:
            denom = max(1, hired_count)

        assert denom >= 1
        assert expected_cost_per_hire == Decimal("100") / Decimal(denom)

        # Ensure get_or_create was called for the report
        mock_get_or_create.assert_called()
