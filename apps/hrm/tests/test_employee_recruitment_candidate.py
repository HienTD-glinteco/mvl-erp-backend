from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from apps.hrm.models import Employee, RecruitmentCandidate

User = get_user_model()


class EmployeeRecruitmentCandidateTest(TransactionTestCase):
    """Test cases for Employee recruitment_candidate field."""

    def setUp(self):
        # Clear all existing data for clean tests
        Employee.objects.all().delete()
        RecruitmentCandidate.objects.all().delete()

        # Create organizational structure
        from apps.core.models import AdministrativeUnit, Province
        from apps.hrm.models import (
            Block,
            Branch,
            Department,
            RecruitmentChannel,
            RecruitmentRequest,
            RecruitmentSource,
        )

        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001",
            name="Main Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001", name="Main Block", branch=self.branch, block_type=Block.BlockType.BUSINESS
        )
        self.department = Department.objects.create(
            code="PB001", name="Engineering Department", block=self.block, branch=self.branch
        )

        # Create recruitment request, source, and channel for candidate
        self.recruitment_source = RecruitmentSource.objects.create(name="LinkedIn")
        self.recruitment_channel = RecruitmentChannel.objects.create(name="Online")

        # Create job description
        from apps.hrm.models import JobDescription

        self.job_description = JobDescription.objects.create(
            title="Software Engineer",
            responsibility="Develop software",
            requirement="3+ years experience",
            benefit="Competitive salary",
            proposed_salary="1000-1500 USD",
        )

        # Create a proposer employee
        self.proposer = Employee.objects.create(
            fullname="Proposer User",
            username="proposer",
            email="proposer@example.com",
            phone="0987654321",
            attendance_code="99999",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2023-01-01",
            citizen_id="000000020014",
        )

        self.recruitment_request = RecruitmentRequest.objects.create(
            name="Software Engineer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.proposer,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="1000-1500 USD",
            number_of_positions=1,
        )

        # Create recruitment candidate
        self.candidate = RecruitmentCandidate.objects.create(
            name="Jane Candidate",
            citizen_id="123456789012",
            email="jane@example.com",
            phone="0123456789",
            recruitment_request=self.recruitment_request,
            recruitment_source=self.recruitment_source,
            recruitment_channel=self.recruitment_channel,
            submitted_date="2024-01-01",
            status=RecruitmentCandidate.Status.HIRED,
            onboard_date="2024-02-01",
        )

    def test_employee_with_recruitment_candidate(self):
        """Test creating an employee with a recruitment_candidate."""
        employee = Employee.objects.create(
            fullname="Jane Candidate",
            username="janecandidate",
            email="jane.employee@example.com",
            phone="0123456789",
            attendance_code="54321",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-02-01",
            recruitment_candidate=self.candidate,
            citizen_id="000000020015",
        )

        self.assertEqual(employee.recruitment_candidate, self.candidate)
        self.assertIn(employee, self.candidate.employees.all())

    def test_employee_without_recruitment_candidate(self):
        """Test creating an employee without a recruitment_candidate."""
        employee = Employee.objects.create(
            fullname="John Doe",
            username="johndoe",
            email="john@example.com",
            phone="0987654321",
            attendance_code="12345",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-01-01",
            citizen_id="000000020016",
        )

        self.assertIsNone(employee.recruitment_candidate)

    def test_recruitment_candidate_set_null_on_delete(self):
        """Test that recruitment_candidate is set to NULL when candidate is deleted."""
        employee = Employee.objects.create(
            fullname="Jane Candidate",
            username="janecandidate",
            email="jane.employee@example.com",
            phone="0123456789",
            attendance_code="54321",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-02-01",
            recruitment_candidate=self.candidate,
            citizen_id="000000020017",
        )

        candidate_id = self.candidate.id
        self.candidate.delete()

        employee.refresh_from_db()
        self.assertIsNone(employee.recruitment_candidate)

    def test_multiple_employees_from_same_candidate(self):
        """Test that multiple employees can be linked to the same recruitment candidate."""
        employee1 = Employee.objects.create(
            fullname="Jane Candidate 1",
            username="janecandidate1",
            email="jane1@example.com",
            phone="0123456789",
            attendance_code="54321",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-02-01",
            recruitment_candidate=self.candidate,
            citizen_id="000000020018",
        )

        employee2 = Employee.objects.create(
            fullname="Jane Candidate 2",
            username="janecandidate2",
            email="jane2@example.com",
            phone="0987654321",
            attendance_code="54322",
            code_type="MV",
            branch=self.branch,
            block=self.block,
            department=self.department,
            start_date="2024-02-15",
            recruitment_candidate=self.candidate,
            citizen_id="000000020019",
        )

        self.assertEqual(employee1.recruitment_candidate, self.candidate)
        self.assertEqual(employee2.recruitment_candidate, self.candidate)
        self.assertEqual(self.candidate.employees.count(), 2)
