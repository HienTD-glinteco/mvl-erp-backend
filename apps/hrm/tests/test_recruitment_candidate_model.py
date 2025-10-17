from datetime import date

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentRequest,
    RecruitmentSource,
)


class RecruitmentCandidateModelTest(TransactionTestCase):
    """Test cases for RecruitmentCandidate model"""

    def setUp(self):
        """Set up test data"""
        # Create organizational structure
        self.province = Province.objects.create(name="Hanoi", code="01")
        self.admin_unit = AdministrativeUnit.objects.create(
            name="City",
            code="TP",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            name="Hanoi Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )

        self.block = Block.objects.create(
            name="Business Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )

        self.department = Department.objects.create(
            name="IT Department",
            branch=self.branch,
            block=self.block,
            function=Department.DepartmentFunction.BUSINESS,
        )

        # Create employee
        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            branch=self.branch,
            block=self.block,
            department=self.department,
        )

        # Create job description
        self.job_description = JobDescription.objects.create(
            title="Senior Python Developer",
            responsibility="Develop backend services",
            requirement="5+ years experience",
            benefit="Competitive salary",
            proposed_salary="2000-3000 USD",
        )

        # Create recruitment request
        self.recruitment_request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2000-3000 USD",
            number_of_positions=2,
        )

        # Create recruitment source and channel
        self.recruitment_source = RecruitmentSource.objects.create(
            name="LinkedIn",
            description="Professional networking platform",
        )

        self.recruitment_channel = RecruitmentChannel.objects.create(
            name="Job Website",
            belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE,
            description="Online job posting platform",
        )

    def test_create_recruitment_candidate(self):
        """Test creating a recruitment candidate"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.CONTACTED,
            note="Strong Python skills",
        )

        self.assertIsNotNone(candidate.id)
        self.assertEqual(candidate.name, "Nguyen Van B")
        self.assertEqual(candidate.citizen_id, "123456789012")
        self.assertEqual(candidate.email, "nguyenvanb@example.com")
        self.assertEqual(candidate.phone, "0123456789")
        self.assertEqual(candidate.recruitment_request, self.recruitment_request)
        self.assertEqual(candidate.years_of_experience, 5)
        self.assertEqual(candidate.status, RecruitmentCandidate.Status.CONTACTED)

    def test_auto_code_generation(self):
        """Test that code is auto-generated with UV prefix"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        self.assertIsNotNone(candidate.code)
        self.assertTrue(candidate.code.startswith("UV"))

    def test_auto_set_branch_from_recruitment_request(self):
        """Test that branch is automatically set from recruitment_request"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        self.assertEqual(candidate.branch, self.recruitment_request.branch)

    def test_auto_set_block_from_recruitment_request(self):
        """Test that block is automatically set from recruitment_request"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        self.assertEqual(candidate.block, self.recruitment_request.block)

    def test_auto_set_department_from_recruitment_request(self):
        """Test that department is automatically set from recruitment_request"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        self.assertEqual(candidate.department, self.recruitment_request.department)

    def test_default_status_is_contacted(self):
        """Test that default status is CONTACTED"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        self.assertEqual(candidate.status, RecruitmentCandidate.Status.CONTACTED)

    def test_str_representation(self):
        """Test string representation of recruitment candidate"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        expected_str = f"{candidate.code} - Nguyen Van B"
        self.assertEqual(str(candidate), expected_str)

    def test_citizen_id_validation_non_digit(self):
        """Test validation for citizen_id with non-digit characters"""
        candidate = RecruitmentCandidate(
            name="Nguyen Van B",
            citizen_id="12345678901A",  # Contains letter
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        with self.assertRaises(ValidationError) as context:
            candidate.full_clean()

        self.assertIn("citizen_id", context.exception.error_dict)

    def test_citizen_id_validation_wrong_length(self):
        """Test validation for citizen_id with wrong length"""
        candidate = RecruitmentCandidate(
            name="Nguyen Van B",
            citizen_id="12345",  # Too short
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        with self.assertRaises(ValidationError) as context:
            candidate.full_clean()

        self.assertIn("citizen_id", context.exception.error_dict)

    def test_onboard_date_required_when_hired(self):
        """Test validation for onboard_date when status is HIRED"""
        candidate = RecruitmentCandidate(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=None,
        )

        with self.assertRaises(ValidationError) as context:
            candidate.save()

        self.assertIn("onboard_date", context.exception.error_dict)

    def test_onboard_date_not_required_for_other_statuses(self):
        """Test that onboard_date is not required for non-HIRED statuses"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.INTERVIEWED_1,
            onboard_date=None,
        )

        self.assertIsNotNone(candidate.id)
        self.assertIsNone(candidate.onboard_date)

    def test_hired_candidate_with_onboard_date(self):
        """Test creating a hired candidate with onboard_date"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date=date(2025, 11, 1),
        )

        self.assertIsNotNone(candidate.id)
        self.assertEqual(candidate.status, RecruitmentCandidate.Status.HIRED)
        self.assertEqual(candidate.onboard_date, date(2025, 11, 1))

    def test_all_status_choices(self):
        """Test all status choices"""
        statuses = [
            RecruitmentCandidate.Status.CONTACTED,
            RecruitmentCandidate.Status.INTERVIEW_SCHEDULED_1,
            RecruitmentCandidate.Status.INTERVIEWED_1,
            RecruitmentCandidate.Status.INTERVIEW_SCHEDULED_2,
            RecruitmentCandidate.Status.INTERVIEWED_2,
            RecruitmentCandidate.Status.REJECTED,
        ]

        for status in statuses:
            candidate = RecruitmentCandidate.objects.create(
                name=f"Candidate {status}",
                citizen_id=f"{123456789000 + statuses.index(status):012d}",
                email=f"candidate{statuses.index(status)}@example.com",
                phone="0123456789",
                recruitment_request=self.recruitment_request,
                recruitment_source=self.recruitment_source,
                recruitment_channel=self.recruitment_channel,
                years_of_experience=5,
                submitted_date=date(2025, 10, 15),
                status=status,
            )
            self.assertEqual(candidate.status, status)

    def test_referrer_optional(self):
        """Test that referrer field is optional"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
            referrer=None,
        )

        self.assertIsNotNone(candidate.id)
        self.assertIsNone(candidate.referrer)

    def test_referrer_with_employee(self):
        """Test setting referrer field with an employee"""
        candidate = RecruitmentCandidate.objects.create(
            name="Nguyen Van B",
            citizen_id="123456789012",
            email="nguyenvanb@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
            referrer=self.employee,
        )

        self.assertIsNotNone(candidate.id)
        self.assertEqual(candidate.referrer, self.employee)

    def test_code_uniqueness(self):
        """Test that code field is unique"""
        candidate1 = RecruitmentCandidate.objects.create(
            name="Candidate 1",
            citizen_id="123456789012",
            email="candidate1@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        candidate2 = RecruitmentCandidate.objects.create(
            name="Candidate 2",
            citizen_id="123456789013",
            email="candidate2@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=3,
            submitted_date=date(2025, 10, 16),
        )

        self.assertNotEqual(candidate1.code, candidate2.code)

    def test_ordering(self):
        """Test that recruitment candidates are ordered by created_at descending"""
        candidate1 = RecruitmentCandidate.objects.create(
            name="Candidate 1",
            citizen_id="123456789012",
            email="candidate1@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=5,
            submitted_date=date(2025, 10, 15),
        )

        candidate2 = RecruitmentCandidate.objects.create(
            name="Candidate 2",
            citizen_id="123456789013",
            email="candidate2@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            years_of_experience=3,
            submitted_date=date(2025, 10, 16),
        )

        candidates = list(RecruitmentCandidate.objects.all())
        self.assertEqual(candidates[0], candidate2)
        self.assertEqual(candidates[1], candidate1)
