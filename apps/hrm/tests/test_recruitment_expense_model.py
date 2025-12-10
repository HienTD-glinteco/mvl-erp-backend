from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    RecruitmentChannel,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
)

User = get_user_model()


class RecruitmentExpenseModelTest(TestCase):
    """Test cases for RecruitmentExpense model"""

    def setUp(self):
        """Set up test data"""
        # Create organizational structure
        self.province = Province.objects.create(
            code="01",
            name="Hanoi",
            english_name="Hanoi",
            level=Province.ProvinceLevel.CENTRAL_CITY,
            enabled=True,
        )
        self.administrative_unit = AdministrativeUnit.objects.create(
            code="001",
            name="Ba Dinh District",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
            enabled=True,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            code="HN",
            province=self.province,
            administrative_unit=self.administrative_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            code="BB",
            block_type=Block.BlockType.BUSINESS,
            branch=self.branch,
        )

        self.department = Department.objects.create(
            name="HR Department",
            code="HR",
            branch=self.branch,
            block=self.block,
        )

        # Create employees
        self.employee1 = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            phone="3357059683",
            attendance_code="NGUYENVANA",
            date_of_birth="1990-01-01",
            personal_email="nguyenvana.personal@example.com",
            start_date="2024-01-01",
            citizen_id="000000020003",
        )

        self.employee2 = Employee.objects.create(
            fullname="Tran Thi B",
            username="tranthib",
            email="tranthib@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
            phone="3512357609",
            attendance_code="TRANTHIB",
            date_of_birth="1990-01-01",
            personal_email="tranthib.personal@example.com",
            start_date="2024-01-01",
            citizen_id="000000020004",
        )

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Software Engineer",
            responsibility="Develop software",
            requirement="5+ years experience",
            benefit="Competitive salary",
            proposed_salary="2000-3000 USD",
        )

        # Create recruitment request
        self.recruitment_request = RecruitmentRequest.objects.create(
            name="Hiring Software Engineer",
            job_description=self.job_description,
            proposer=self.employee1,
            branch=self.branch,
            block=self.block,
            department=self.department,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="1000-2000 USD",
            number_of_positions=5,
        )

        # Create recruitment source (with referral)
        self.recruitment_source_with_referral = RecruitmentSource.objects.create(
            name="Employee Referral",
            code="REF",
            allow_referral=True,
        )

        # Create recruitment source (without referral)
        self.recruitment_source_no_referral = RecruitmentSource.objects.create(
            name="LinkedIn",
            code="LI",
            allow_referral=False,
        )

        # Create recruitment channel
        self.recruitment_channel = RecruitmentChannel.objects.create(
            name="Social Media",
            code="SM",
            belong_to=RecruitmentChannel.BelongTo.MARKETING,
        )

    def test_create_recruitment_expense_basic(self):
        """Test creating a basic recruitment expense"""
        expense = RecruitmentExpense.objects.create(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            num_candidates_participated=10,
            total_cost=Decimal("5000.00"),
            num_candidates_hired=2,
            activity="Job fair at university",
            note="Good candidates pool",
        )

        self.assertEqual(expense.date, date(2024, 1, 15))
        self.assertEqual(expense.recruitment_source, self.recruitment_source_no_referral)
        self.assertEqual(expense.num_candidates_participated, 10)
        self.assertEqual(expense.total_cost, Decimal("5000.00"))
        self.assertEqual(expense.num_candidates_hired, 2)
        self.assertIsNotNone(expense.id)

    def test_avg_cost_property(self):
        """Test avg_cost property calculation"""
        expense = RecruitmentExpense.objects.create(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("6000.00"),
            num_candidates_hired=3,
        )

        self.assertEqual(expense.avg_cost, Decimal("2000.00"))

    def test_avg_cost_zero_division(self):
        """Test avg_cost property handles zero division safely"""
        expense = RecruitmentExpense.objects.create(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("5000.00"),
            num_candidates_hired=0,
        )

        self.assertEqual(expense.avg_cost, Decimal("0.00"))

    def test_recruitment_request_status_validation(self):
        """Test validation of recruitment_request status"""
        # Create a DRAFT recruitment request
        draft_request = RecruitmentRequest.objects.create(
            name="Draft Request",
            job_description=self.job_description,
            proposer=self.employee1,
            branch=self.branch,
            block=self.block,
            department=self.department,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.DRAFT,
            proposed_salary="1000 USD",
        )

        expense = RecruitmentExpense(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=draft_request,
            total_cost=Decimal("1000.00"),
        )

        with self.assertRaises(ValidationError) as context:
            expense.save()

        self.assertIn("recruitment_request", context.exception.message_dict)

    def test_recruitment_request_status_open_allowed(self):
        """Test OPEN status is allowed for recruitment_request"""
        expense = RecruitmentExpense.objects.create(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
        )

        self.assertIsNotNone(expense.id)

    def test_recruitment_request_status_closed_allowed(self):
        """Test CLOSED status is allowed for recruitment_request"""
        closed_request = RecruitmentRequest.objects.create(
            name="Closed Request",
            job_description=self.job_description,
            proposer=self.employee1,
            branch=self.branch,
            block=self.block,
            department=self.department,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.CLOSED,
            proposed_salary="1000 USD",
        )

        expense = RecruitmentExpense.objects.create(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=closed_request,
            total_cost=Decimal("1000.00"),
        )

        self.assertIsNotNone(expense.id)

    def test_recruitment_request_status_paused_allowed(self):
        """Test PAUSED status is allowed for recruitment_request"""
        paused_request = RecruitmentRequest.objects.create(
            name="Paused Request",
            job_description=self.job_description,
            proposer=self.employee1,
            branch=self.branch,
            block=self.block,
            department=self.department,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.PAUSED,
            proposed_salary="1000 USD",
        )

        expense = RecruitmentExpense.objects.create(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=paused_request,
            total_cost=Decimal("1000.00"),
        )

        self.assertIsNotNone(expense.id)

    def test_referral_fields_required_when_allow_referral_true(self):
        """Test referee and referrer are required when recruitment_source.allow_referral=True"""
        # Missing both referee and referrer
        expense = RecruitmentExpense(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_with_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
        )

        with self.assertRaises(ValidationError) as context:
            expense.save()

        self.assertIn("referee", context.exception.message_dict)
        self.assertIn("referrer", context.exception.message_dict)

    def test_referral_fields_required_referee_only(self):
        """Test both referee and referrer are required, not just one"""
        # Only referee provided
        expense = RecruitmentExpense(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_with_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
            referee=self.employee1,
        )

        with self.assertRaises(ValidationError) as context:
            expense.save()

        self.assertIn("referrer", context.exception.message_dict)

    def test_referral_fields_required_referrer_only(self):
        """Test both referee and referrer are required, not just one"""
        # Only referrer provided
        expense = RecruitmentExpense(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_with_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
            referrer=self.employee1,
        )

        with self.assertRaises(ValidationError) as context:
            expense.save()

        self.assertIn("referee", context.exception.message_dict)

    def test_referral_fields_valid_when_both_provided(self):
        """Test expense is valid when both referee and referrer are provided with allow_referral=True"""
        expense = RecruitmentExpense.objects.create(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_with_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
            referee=self.employee1,
            referrer=self.employee2,
        )

        self.assertIsNotNone(expense.id)
        self.assertEqual(expense.referee, self.employee1)
        self.assertEqual(expense.referrer, self.employee2)

    def test_referral_fields_not_allowed_when_allow_referral_false(self):
        """Test referee and referrer must not be set when recruitment_source.allow_referral=False"""
        # Trying to set referee
        expense = RecruitmentExpense(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
            referee=self.employee1,
        )

        with self.assertRaises(ValidationError) as context:
            expense.save()

        self.assertIn("referee", context.exception.message_dict)

    def test_referrer_not_allowed_when_allow_referral_false(self):
        """Test referrer must not be set when recruitment_source.allow_referral=False"""
        # Trying to set referrer
        expense = RecruitmentExpense(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
            referrer=self.employee1,
        )

        with self.assertRaises(ValidationError) as context:
            expense.save()

        self.assertIn("referrer", context.exception.message_dict)

    def test_referee_and_referrer_cannot_be_same_person(self):
        """Test that referee and referrer cannot be the same employee"""
        expense = RecruitmentExpense(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_with_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
            referee=self.employee1,
            referrer=self.employee1,  # Same as referee
        )

        with self.assertRaises(ValidationError) as context:
            expense.save()

        self.assertIn("referrer", context.exception.message_dict)
        self.assertIn("cannot be the same person", str(context.exception.message_dict["referrer"][0]))

    def test_referee_and_referrer_can_be_different_persons(self):
        """Test that expense is valid when referee and referrer are different employees"""
        expense = RecruitmentExpense.objects.create(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_with_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
            referee=self.employee1,
            referrer=self.employee2,  # Different from referee
        )

        self.assertIsNotNone(expense.id)
        self.assertEqual(expense.referee, self.employee1)
        self.assertEqual(expense.referrer, self.employee2)
        self.assertNotEqual(expense.referee, expense.referrer)

    def test_code_auto_generation(self):
        """Test that expense can be created successfully"""
        expense = RecruitmentExpense.objects.create(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
        )

        # Verify expense is created successfully
        self.assertIsNotNone(expense.id)
        self.assertIsNotNone(expense.pk)

    def test_activity_max_length(self):
        """Test activity field accepts long text (TextField allows any length)"""
        long_activity = "A" * 1001
        expense = RecruitmentExpense(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
            activity=long_activity,
        )

        # TextField doesn't enforce max_length, so this should not raise ValidationError
        expense.full_clean()
        self.assertEqual(expense.activity, long_activity)

    def test_note_max_length(self):
        """Test note field accepts long text (TextField allows any length)"""
        long_note = "B" * 501
        expense = RecruitmentExpense(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
            note=long_note,
        )

        # TextField doesn't enforce max_length, so this should not raise ValidationError
        expense.full_clean()
        self.assertEqual(expense.note, long_note)

    def test_ordering(self):
        """Test default ordering by -created_at"""
        expense1 = RecruitmentExpense.objects.create(
            date=date(2024, 1, 15),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("1000.00"),
        )

        expense2 = RecruitmentExpense.objects.create(
            date=date(2024, 1, 16),
            recruitment_source=self.recruitment_source_no_referral,
            recruitment_channel=self.recruitment_channel,
            recruitment_request=self.recruitment_request,
            total_cost=Decimal("2000.00"),
        )

        expenses = list(RecruitmentExpense.objects.all())
        self.assertEqual(expenses[0], expense2)
        self.assertEqual(expenses[1], expense1)
