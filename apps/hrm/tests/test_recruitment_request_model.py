from django.core.exceptions import ValidationError
from django.test import TransactionTestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    RecruitmentRequest,
)
from libs import ColorVariant


class RecruitmentRequestModelTest(TransactionTestCase):
    """Test cases for RecruitmentRequest model"""

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

        # Create employee as proposer
        self.employee = Employee.objects.create(
            fullname="Nguyen Van A",
            username="nguyenvana",
            email="nguyenvana@example.com",
            branch=self.branch,
            phone="0123456789",
            attendance_code="EMP001",
            date_of_birth="1990-01-01",
            personal_email="emp.personal@example.com",
            start_date="2024-01-01",
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

    def test_create_recruitment_request(self):
        """Test creating a recruitment request"""
        request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.DRAFT,
            proposed_salary="2000-3000 USD",
            number_of_positions=2,
        )

        self.assertIsNotNone(request.id)
        self.assertEqual(request.name, "Backend Developer Position")
        self.assertEqual(request.job_description, self.job_description)
        self.assertEqual(request.department, self.department)
        self.assertEqual(request.proposer, self.employee)
        self.assertEqual(request.recruitment_type, RecruitmentRequest.RecruitmentType.NEW_HIRE)
        self.assertEqual(request.status, RecruitmentRequest.Status.DRAFT)
        self.assertEqual(request.proposed_salary, "2000-3000 USD")
        self.assertEqual(request.number_of_positions, 2)

    def test_auto_code_generation(self):
        """Test that code is auto-generated with RR prefix"""
        request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.DRAFT,
            proposed_salary="2000-3000 USD",
            number_of_positions=1,
        )

        self.assertIsNotNone(request.code)
        self.assertTrue(request.code.startswith("RR"))

    def test_auto_set_branch_from_department(self):
        """Test that branch is automatically set from department"""
        request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.DRAFT,
            proposed_salary="2000-3000 USD",
            number_of_positions=1,
        )

        self.assertEqual(request.branch, self.department.branch)

    def test_auto_set_block_from_department(self):
        """Test that block is automatically set from department"""
        request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.DRAFT,
            proposed_salary="2000-3000 USD",
            number_of_positions=1,
        )

        self.assertEqual(request.block, self.department.block)

    def test_default_status_is_draft(self):
        """Test that default status is DRAFT"""
        request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
            number_of_positions=1,
        )

        self.assertEqual(request.status, RecruitmentRequest.Status.DRAFT)

    def test_default_number_of_positions(self):
        """Test that default number of positions is 1"""
        request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
        )

        self.assertEqual(request.number_of_positions, 1)

    def test_str_representation(self):
        """Test string representation of recruitment request"""
        request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
        )

        expected_str = f"{request.code} - Backend Developer Position"
        self.assertEqual(str(request), expected_str)

    def test_recruitment_types(self):
        """Test all recruitment type choices"""
        # Test NEW_HIRE
        request1 = RecruitmentRequest.objects.create(
            name="New Hire Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
        )
        self.assertEqual(request1.recruitment_type, "NEW_HIRE")

        # Test REPLACEMENT
        request2 = RecruitmentRequest.objects.create(
            name="Replacement Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.REPLACEMENT,
            proposed_salary="2000-3000 USD",
        )
        self.assertEqual(request2.recruitment_type, "REPLACEMENT")

    def test_status_choices(self):
        """Test all status choices"""
        # Test DRAFT
        request1 = RecruitmentRequest.objects.create(
            name="Draft Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.DRAFT,
            proposed_salary="2000-3000 USD",
        )
        self.assertEqual(request1.status, "DRAFT")

        # Test OPEN
        request2 = RecruitmentRequest.objects.create(
            name="Open Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2000-3000 USD",
        )
        self.assertEqual(request2.status, "OPEN")

        # Test PAUSED
        request3 = RecruitmentRequest.objects.create(
            name="Paused Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.PAUSED,
            proposed_salary="2000-3000 USD",
        )
        self.assertEqual(request3.status, "PAUSED")

        # Test CLOSED
        request4 = RecruitmentRequest.objects.create(
            name="Closed Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.CLOSED,
            proposed_salary="2000-3000 USD",
        )
        self.assertEqual(request4.status, "CLOSED")

    def test_validate_number_of_positions_minimum(self):
        """Test validation for minimum number of positions"""
        request = RecruitmentRequest(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
            number_of_positions=0,
        )

        with self.assertRaises(ValidationError) as context:
            request.save()

        self.assertIn("number_of_positions", context.exception.error_dict)

    def test_validate_organizational_hierarchy(self):
        """Test validation of organizational hierarchy"""
        # Create another branch, block, department
        branch2 = Branch.objects.create(
            name="HCMC Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        block2 = Block.objects.create(
            name="Support Block",
            branch=branch2,
            block_type=Block.BlockType.SUPPORT,
        )

        # Try to create request with mismatched hierarchy
        request = RecruitmentRequest(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            branch=branch2,  # Wrong branch
            block=self.block,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
            number_of_positions=1,
        )

        request.save()
        self.assertEqual(request.branch, self.department.branch)
        self.assertEqual(request.block, self.department.block)

    def test_code_uniqueness(self):
        """Test that code field is unique"""
        request1 = RecruitmentRequest.objects.create(
            name="Position 1",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
        )

        # Try to create another request with the same code (should auto-generate different code)
        request2 = RecruitmentRequest.objects.create(
            name="Position 2",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
        )

        self.assertNotEqual(request1.code, request2.code)

    def test_ordering(self):
        """Test that recruitment requests are ordered by created_at descending"""
        request1 = RecruitmentRequest.objects.create(
            name="Position 1",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
        )

        request2 = RecruitmentRequest.objects.create(
            name="Position 2",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
        )

        requests = list(RecruitmentRequest.objects.all())
        self.assertEqual(requests[0], request2)
        self.assertEqual(requests[1], request1)

    def test_colored_status_property(self):
        """Test colored_status property returns correct value and variant"""
        request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            status=RecruitmentRequest.Status.OPEN,
            proposed_salary="2000-3000 USD",
        )

        colored_status = request.colored_status
        self.assertEqual(colored_status["value"], "OPEN")
        self.assertEqual(colored_status["variant"], ColorVariant.GREEN)

    def test_colored_status_all_variants(self):
        """Test all status values have correct color variants"""
        test_cases = [
            (RecruitmentRequest.Status.DRAFT, ColorVariant.GREY),
            (RecruitmentRequest.Status.OPEN, ColorVariant.GREEN),
            (RecruitmentRequest.Status.PAUSED, ColorVariant.YELLOW),
            (RecruitmentRequest.Status.CLOSED, ColorVariant.RED),
        ]

        for status, expected_variant in test_cases:
            request = RecruitmentRequest.objects.create(
                name=f"Position {status}",
                job_description=self.job_description,
                department=self.department,
                proposer=self.employee,
                recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
                status=status,
                proposed_salary="2000-3000 USD",
            )

            colored_status = request.colored_status
            self.assertEqual(colored_status["value"], status)
            self.assertEqual(colored_status["variant"], expected_variant)

    def test_colored_recruitment_type_property(self):
        """Test colored_recruitment_type property returns correct value and variant"""
        request = RecruitmentRequest.objects.create(
            name="Backend Developer Position",
            job_description=self.job_description,
            department=self.department,
            proposer=self.employee,
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="2000-3000 USD",
        )

        colored_recruitment_type = request.colored_recruitment_type
        self.assertEqual(colored_recruitment_type["value"], "NEW_HIRE")
        self.assertEqual(colored_recruitment_type["variant"], ColorVariant.BLUE)

    def test_colored_recruitment_type_all_variants(self):
        """Test all recruitment type values have correct color variants"""
        test_cases = [
            (RecruitmentRequest.RecruitmentType.NEW_HIRE, ColorVariant.BLUE),
            (RecruitmentRequest.RecruitmentType.REPLACEMENT, ColorVariant.PURPLE),
        ]

        for recruitment_type, expected_variant in test_cases:
            request = RecruitmentRequest.objects.create(
                name=f"Position {recruitment_type}",
                job_description=self.job_description,
                department=self.department,
                proposer=self.employee,
                recruitment_type=recruitment_type,
                proposed_salary="2000-3000 USD",
            )

            colored_recruitment_type = request.colored_recruitment_type
            self.assertEqual(colored_recruitment_type["value"], recruitment_type)
            self.assertEqual(colored_recruitment_type["variant"], expected_variant)
