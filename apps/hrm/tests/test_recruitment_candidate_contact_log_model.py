from datetime import date

from django.test import TransactionTestCase

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    JobDescription,
    RecruitmentCandidate,
    RecruitmentCandidateContactLog,
    RecruitmentChannel,
    RecruitmentRequest,
    RecruitmentSource,
)


class RecruitmentCandidateContactLogModelTest(TransactionTestCase):
    """Test cases for RecruitmentCandidateContactLog model"""

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

        # Create recruitment candidate
        self.candidate = RecruitmentCandidate.objects.create(
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

    def test_create_contact_log(self):
        """Test creating a contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="Contacted to schedule first interview",
            recruitment_candidate=self.candidate,
        )

        self.assertIsNotNone(log.id)
        self.assertEqual(log.employee, self.employee)
        self.assertEqual(log.date, date(2025, 10, 16))
        self.assertEqual(log.method, "PHONE")
        self.assertEqual(log.note, "Contacted to schedule first interview")
        self.assertEqual(log.recruitment_candidate, self.candidate)

    def test_str_representation(self):
        """Test string representation of contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="Contacted to schedule first interview",
            recruitment_candidate=self.candidate,
        )

        expected_str = f"{self.candidate.name} - {date(2025, 10, 16)} - PHONE"
        self.assertEqual(str(log), expected_str)

    def test_all_contact_methods(self):
        """Test all contact method choices"""
        methods = [
            "PHONE",
            "EMAIL",
            "IN_PERSON",
            "VIDEO_CALL",
            "OTHER",
        ]

        for method in methods:
            log = RecruitmentCandidateContactLog.objects.create(
                employee=self.employee,
                date=date(2025, 10, 16),
                method=method,
                note=f"Contact via {method}",
                recruitment_candidate=self.candidate,
            )
            self.assertEqual(log.method, method)

    def test_note_optional(self):
        """Test that note field is optional"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            recruitment_candidate=self.candidate,
        )

        self.assertIsNotNone(log.id)
        self.assertEqual(log.note, "")

    def test_ordering(self):
        """Test that contact logs are ordered by date and created_at descending"""
        log1 = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 15),
            method="PHONE",
            note="First contact",
            recruitment_candidate=self.candidate,
        )

        log2 = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="EMAIL",
            note="Second contact",
            recruitment_candidate=self.candidate,
        )

        log3 = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="VIDEO_CALL",
            note="Third contact",
            recruitment_candidate=self.candidate,
        )

        logs = list(RecruitmentCandidateContactLog.objects.all())
        # Should be ordered by date desc, then created_at desc
        self.assertEqual(logs[0], log3)
        self.assertEqual(logs[1], log2)
        self.assertEqual(logs[2], log1)

    def test_cascade_delete_when_candidate_deleted(self):
        """Test that contact logs are deleted when candidate is deleted"""
        log1 = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=self.candidate,
        )

        log2 = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 17),
            method="EMAIL",
            note="Second contact",
            recruitment_candidate=self.candidate,
        )

        # Check logs exist
        self.assertEqual(
            RecruitmentCandidateContactLog.objects.filter(recruitment_candidate=self.candidate).count(), 2
        )

        # Delete candidate
        self.candidate.delete()

        # Check logs are also deleted
        self.assertEqual(RecruitmentCandidateContactLog.objects.count(), 0)

    def test_protect_delete_when_employee_referenced(self):
        """Test that employee cannot be deleted if referenced in contact log"""
        log = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="Contact log",
            recruitment_candidate=self.candidate,
        )

        # Try to delete employee should raise ProtectedError
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.employee.delete()

    def test_multiple_logs_for_same_candidate(self):
        """Test creating multiple contact logs for the same candidate"""
        log1 = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 16),
            method="PHONE",
            note="First contact",
            recruitment_candidate=self.candidate,
        )

        log2 = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 17),
            method="EMAIL",
            note="Second contact",
            recruitment_candidate=self.candidate,
        )

        log3 = RecruitmentCandidateContactLog.objects.create(
            employee=self.employee,
            date=date(2025, 10, 18),
            method="VIDEO_CALL",
            note="Third contact",
            recruitment_candidate=self.candidate,
        )

        logs = RecruitmentCandidateContactLog.objects.filter(recruitment_candidate=self.candidate)
        self.assertEqual(logs.count(), 3)
