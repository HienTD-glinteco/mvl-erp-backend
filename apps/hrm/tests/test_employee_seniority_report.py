"""Tests for Employee Seniority Report feature."""

import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Employee, EmployeeWorkHistory, Position

User = get_user_model()


class APITestMixin:
    """Mixin to handle wrapped API responses and data extraction"""

    def get_response_data(self, response):
        """Extract data from wrapped API response"""
        content = json.loads(response.content.decode())
        if "data" in content:
            data = content["data"]
            if isinstance(data, dict) and "results" in data:
                return data["results"]
            return data
        return content


class EmployeeSeniorityReportTest(TransactionTestCase, APITestMixin):
    """Test cases for Employee Seniority Report"""

    def setUp(self):
        """Set up test data"""
        # Clean up
        Employee.objects.all().delete()
        EmployeeWorkHistory.objects.all().delete()
        Department.objects.all().delete()
        Block.objects.all().delete()
        Branch.objects.all().delete()

        # Create user for authentication
        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.user = User.objects.create_superuser(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

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

        self.position = Position.objects.create(
            name="Developer",
        )

    def create_employee(self, code="MV001", status=Employee.Status.ACTIVE, start_date=None):
        """Helper to create an employee"""
        if start_date is None:
            start_date = date(2020, 1, 1)

        # Generate unique citizen_id based on code
        citizen_id = (
            f"{int(code[2:]):012d}"
            if code.startswith("MV") or code.startswith("OS")
            else f"{hash(code) % 1000000000000:012d}"
        )

        # Determine code_type based on code prefix
        if code.startswith("OS"):
            code_type = Employee.CodeType.OS
        elif code.startswith("CTV"):
            code_type = Employee.CodeType.CTV
        else:
            code_type = Employee.CodeType.MV

        employee_data = {
            "code": code,
            "code_type": code_type,
            "fullname": f"Test Employee {code}",
            "username": f"user_{code.lower()}",
            "email": f"{code.lower()}@example.com",
            "attendance_code": f"{int(code[2:]):05d}" if (code.startswith("MV") or code.startswith("OS")) else "12345",
            "citizen_id": citizen_id,
            "branch": self.branch,
            "block": self.block,
            "department": self.department,
            "position": self.position,
            "start_date": start_date,
            "status": status,
        }

        # Add resignation fields if status requires them
        if status in [Employee.Status.MATERNITY_LEAVE, Employee.Status.UNPAID_LEAVE]:
            employee_data["resignation_start_date"] = start_date
            if status == Employee.Status.MATERNITY_LEAVE:
                employee_data["resignation_end_date"] = date(2025, 12, 31)
        elif status == Employee.Status.RESIGNED:
            employee_data["resignation_start_date"] = start_date
            employee_data["resignation_reason"] = Employee.ResignationReason.VOLUNTARY_OTHER

        return Employee.objects.create(**employee_data)

    def create_work_history(self, employee, from_date, to_date=None, retain_seniority=True):
        """Helper to create work history representing an employment period.

        Creates appropriate events based on the period type:
        - Resignation event for past employment (to_date provided)
        - Return to Work event for ongoing or reset periods
        """
        if to_date is not None:
            # Past employment period ending with resignation
            # Create resignation event
            EmployeeWorkHistory.objects.create(
                employee=employee,
                date=to_date,  # Date of resignation
                name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
                detail="Test work history - resigned",
                status=Employee.Status.RESIGNED,
                from_date=from_date,
                to_date=to_date,
                retain_seniority=retain_seniority,
                previous_data={
                    "start_date": from_date.isoformat(),
                    "end_date": to_date.isoformat(),
                    "resignation_start_date": to_date.isoformat(),
                },
            )

            # If this marks a seniority reset, also create a Return to Work event at the end
            # with retain_seniority=False to mark the cutoff point
            if not retain_seniority:
                return EmployeeWorkHistory.objects.create(
                    employee=employee,
                    date=to_date,  # Same date as resignation - marks the reset point
                    name=EmployeeWorkHistory.EventType.RETURN_TO_WORK,
                    detail="Test work history - seniority reset point",
                    from_date=to_date,
                    to_date=to_date,
                    retain_seniority=False,
                )
        else:
            # Ongoing employment period - create return to work event
            return EmployeeWorkHistory.objects.create(
                employee=employee,
                date=from_date,  # Date of return to work
                name=EmployeeWorkHistory.EventType.RETURN_TO_WORK,
                detail="Test work history - return to work",
                from_date=from_date,
                to_date=None,
                retain_seniority=retain_seniority,
            )

    def test_seniority_calculation_no_work_history(self):
        """Test seniority calculation when employee has no work history.

        Business Logic: If no work history, calculate from start_date to today.
        """
        # Arrange
        employee = self.create_employee(
            code="MV001",
            status=Employee.Status.ACTIVE,
            start_date=date(2020, 1, 1),
        )

        # Act
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url)
        results = self.get_response_data(response)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["code"], "MV001")

        # Check seniority (at least 5 years from 2020-01-01)
        # Seniority is now an integer (total days)
        seniority_days = results[0]["seniority"]
        self.assertIsInstance(seniority_days, int)
        self.assertGreaterEqual(seniority_days, 5 * 365)  # At least 5 years

        # Check seniority_text exists and is a string
        self.assertIn("seniority_text", results[0])
        self.assertIsInstance(results[0]["seniority_text"], str)
        self.assertIn("year", results[0]["seniority_text"])
        # Should not have parentheses anymore
        self.assertNotIn("(s)", results[0]["seniority_text"])

        # Check work history includes current period (synthetic entry)
        self.assertEqual(len(results[0]["work_history"]), 1)
        self.assertEqual(results[0]["work_history"][0]["from_date"], "2020-01-01")
        self.assertIsNone(results[0]["work_history"][0]["to_date"])

    def test_seniority_calculation_with_continuous_periods(self):
        """Test seniority calculation with all continuous periods (retain_seniority=True).

        Business Logic: When all periods have retain_seniority=True or None,
        sum ALL employment periods.
        """
        # Arrange
        employee = self.create_employee(code="MV002")

        # Create work histories - all continuous
        self.create_work_history(
            employee,
            from_date=date(2018, 1, 15),
            to_date=date(2020, 6, 30),
            retain_seniority=True,
        )
        self.create_work_history(
            employee,
            from_date=date(2021, 1, 1),
            to_date=None,  # Current period
            retain_seniority=True,
        )

        # Update employee's start_date to match the return to work date
        employee.start_date = date(2021, 1, 1)
        employee.save()

        # Act
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url)
        results = self.get_response_data(response)

        # Assert
        self.assertEqual(response.status_code, 200)
        employee_data = next((e for e in results if e["code"] == "MV002"), None)
        self.assertIsNotNone(employee_data)

        # Check seniority includes both periods (now integer days)
        seniority_days = employee_data["seniority"]
        self.assertIsInstance(seniority_days, int)
        self.assertGreaterEqual(seniority_days, 6 * 365)  # At least 6 years

        # Check seniority_text
        self.assertIn("seniority_text", employee_data)
        self.assertIn("year", employee_data["seniority_text"])

        # Check work history displays both periods (ordered by creation time - ascending)
        self.assertEqual(len(employee_data["work_history"]), 2)
        # Ordered by date (ascending), so oldest first
        self.assertEqual(employee_data["work_history"][0]["from_date"], "2018-01-15")
        self.assertEqual(employee_data["work_history"][1]["from_date"], "2021-01-01")

    def test_seniority_calculation_with_non_continuous_period(self):
        """Test seniority calculation with non-continuous period (retain_seniority=False).

        Business Logic: When there's a retain_seniority=False event,
        only count from the MOST RECENT such event onwards.
        """
        # Arrange
        employee = self.create_employee(code="MV003")

        # Create work histories
        # Period 1: Old period (should be excluded)
        self.create_work_history(
            employee,
            from_date=date(2018, 1, 15),
            to_date=date(2019, 12, 31),
            retain_seniority=True,
        )
        # Period 2: Another old period (should be excluded)
        self.create_work_history(
            employee,
            from_date=date(2020, 1, 1),
            to_date=date(2020, 12, 31),
            retain_seniority=True,
        )
        # Period 3: Non-continuous period (seniority reset)
        self.create_work_history(
            employee,
            from_date=date(2021, 1, 1),
            to_date=date(2021, 12, 31),
            retain_seniority=False,
        )
        # Period 4: Current period (should be included)
        self.create_work_history(
            employee,
            from_date=date(2022, 1, 1),
            to_date=None,
            retain_seniority=True,
        )

        # Update employee's start_date to match the most recent return to work
        employee.start_date = date(2022, 1, 1)
        employee.save()

        # Act
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url)
        results = self.get_response_data(response)

        # Assert
        self.assertEqual(response.status_code, 200)
        employee_data = next((e for e in results if e["code"] == "MV003"), None)
        self.assertIsNotNone(employee_data)

        # Check seniority only includes Period 3 + Period 4 (now integer days)
        seniority_days = employee_data["seniority"]
        self.assertIsInstance(seniority_days, int)
        self.assertGreaterEqual(seniority_days, 3 * 365)  # At least 3 years
        self.assertLessEqual(seniority_days, 5 * 365)  # Should not include the old periods

        # Check seniority_text
        self.assertIn("seniority_text", employee_data)
        self.assertIn("year", employee_data["seniority_text"])

        # Check work history ONLY displays periods included in calculation (BR-4)
        self.assertEqual(len(employee_data["work_history"]), 2)
        # Ordered by date (ascending), so oldest included period first
        self.assertEqual(employee_data["work_history"][0]["from_date"], "2021-01-01")
        self.assertEqual(employee_data["work_history"][1]["from_date"], "2022-01-01")

    def test_work_history_display_matches_calculation_scope(self):
        """Test BR-4: Work history display matches calculation scope.

        When retain_seniority=False exists, displayed work history should only
        show periods from that point onwards, matching the calculation scope.
        """
        # Arrange
        employee = self.create_employee(code="MV004")

        # Multiple retain_seniority=False events
        self.create_work_history(
            employee,
            from_date=date(2017, 1, 1),
            to_date=date(2018, 12, 31),
            retain_seniority=True,
        )
        # First non-continuous period (should be excluded)
        self.create_work_history(
            employee,
            from_date=date(2019, 1, 1),
            to_date=date(2019, 12, 31),
            retain_seniority=False,
        )
        self.create_work_history(
            employee,
            from_date=date(2020, 1, 1),
            to_date=date(2020, 12, 31),
            retain_seniority=True,
        )
        # Second (most recent) non-continuous period
        self.create_work_history(
            employee,
            from_date=date(2021, 1, 1),
            to_date=date(2021, 12, 31),
            retain_seniority=False,
        )
        self.create_work_history(
            employee,
            from_date=date(2022, 1, 1),
            to_date=None,
            retain_seniority=True,
        )

        # Update employee's start_date to match the most recent return to work
        employee.start_date = date(2022, 1, 1)
        employee.save()

        # Act
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url)
        results = self.get_response_data(response)

        # Assert
        employee_data = next((e for e in results if e["code"] == "MV004"), None)
        self.assertIsNotNone(employee_data)

        # Should only show periods from most recent retain_seniority=False onwards
        self.assertEqual(len(employee_data["work_history"]), 2)
        displayed_dates = [wh["from_date"] for wh in employee_data["work_history"]]
        # Ordered by date (ascending)
        self.assertIn("2022-01-01", displayed_dates)
        self.assertIn("2021-01-01", displayed_dates)
        # Should NOT include older periods
        self.assertNotIn("2020-01-01", displayed_dates)
        self.assertNotIn("2019-01-01", displayed_dates)
        self.assertNotIn("2017-01-01", displayed_dates)

    def test_filter_by_status_includes_only_active_maternity_unpaid(self):
        """Test BR-1: Only include employees with specific statuses.

        Should include: Active, Maternity Leave, Unpaid Leave
        Should exclude: Resigned, Onboarding
        """
        # Arrange
        self.create_employee(code="MV010", status=Employee.Status.ACTIVE)
        self.create_employee(code="MV011", status=Employee.Status.MATERNITY_LEAVE)
        self.create_employee(code="MV012", status=Employee.Status.UNPAID_LEAVE)
        self.create_employee(code="MV013", status=Employee.Status.RESIGNED)
        self.create_employee(code="MV014", status=Employee.Status.ONBOARDING)

        # Act
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url)
        results = self.get_response_data(response)

        # Assert
        codes = [e["code"] for e in results]
        self.assertIn("MV010", codes)  # Active
        self.assertIn("MV011", codes)  # Maternity Leave
        self.assertIn("MV012", codes)  # Unpaid Leave
        self.assertNotIn("MV013", codes)  # Resigned (excluded)
        self.assertNotIn("MV014", codes)  # Onboarding (excluded)

    def test_filter_excludes_os_codes(self):
        """Test BR-1: Exclude employees with code starting with 'OS'"""
        # Arrange
        self.create_employee(code="MV020", status=Employee.Status.ACTIVE)
        self.create_employee(code="OS001", status=Employee.Status.ACTIVE)
        self.create_employee(code="OS002", status=Employee.Status.ACTIVE)

        # Act
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url)
        results = self.get_response_data(response)

        # Assert
        codes = [e["code"] for e in results]
        self.assertIn("MV020", codes)
        self.assertNotIn("OS001", codes)
        self.assertNotIn("OS002", codes)

    def test_filter_by_branch(self):
        """Test filtering by branch_id"""
        # Arrange
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
        dept2 = Department.objects.create(
            name="HR Department",
            branch=branch2,
            block=block2,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        emp1 = self.create_employee(code="MV030")

        # Create employee in branch2 using helper
        saved_branch = self.branch
        saved_block = self.block
        saved_dept = self.department
        self.branch = branch2
        self.block = block2
        self.department = dept2
        emp2 = self.create_employee(code="MV031")
        self.branch = saved_branch
        self.block = saved_block
        self.department = saved_dept

        # Act
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url, {"branch_id": self.branch.id})
        results = self.get_response_data(response)

        # Assert
        codes = [e["code"] for e in results]
        self.assertIn("MV030", codes)
        self.assertNotIn("MV031", codes)

    def test_filter_by_function_block(self):
        """Test filtering by function_block (block_type)"""
        # Arrange
        support_block = Block.objects.create(
            name="Support Block",
            branch=self.branch,
            block_type=Block.BlockType.SUPPORT,
        )
        support_dept = Department.objects.create(
            name="HR Department",
            branch=self.branch,
            block=support_block,
            function=Department.DepartmentFunction.HR_ADMIN,
        )

        # Employee in business block
        emp1 = self.create_employee(code="MV040")

        # Employee in support block
        saved_block = self.block
        saved_dept = self.department
        self.block = support_block
        self.department = support_dept
        emp2 = self.create_employee(code="MV041")
        self.block = saved_block
        self.department = saved_dept

        # Act - Filter by business block
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url, {"function_block": "business"})
        results = self.get_response_data(response)

        # Assert
        codes = [e["code"] for e in results]
        self.assertIn("MV040", codes)
        self.assertNotIn("MV041", codes)

    def test_ordering_by_seniority_descending(self):
        """Test ordering by seniority in descending order (most senior first)"""
        # Arrange
        # Employee with 5+ years seniority
        emp1 = self.create_employee(code="MV050", start_date=date(2018, 1, 1))

        # Employee with 3+ years seniority
        emp2 = self.create_employee(code="MV051", start_date=date(2021, 1, 1))

        # Employee with 1+ year seniority
        emp3 = self.create_employee(code="MV052", start_date=date(2023, 1, 1))

        # Act
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url, {"ordering": "-seniority_days"})
        results = self.get_response_data(response)

        # Assert
        codes = [e["code"] for e in results]
        # Most senior first
        self.assertEqual(codes[0], "MV050")
        self.assertEqual(codes[-1], "MV052")

    def test_ordering_by_seniority_ascending(self):
        """Test ordering by seniority in ascending order (least senior first)"""
        # Arrange
        emp1 = self.create_employee(code="MV060", start_date=date(2018, 1, 1))
        emp2 = self.create_employee(code="MV061", start_date=date(2021, 1, 1))
        emp3 = self.create_employee(code="MV062", start_date=date(2023, 1, 1))

        # Act
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url, {"ordering": "seniority_days"})
        results = self.get_response_data(response)

        # Assert
        codes = [e["code"] for e in results]
        # Least senior first
        self.assertEqual(codes[0], "MV062")
        self.assertEqual(codes[-1], "MV060")

    def test_pagination(self):
        """Test that results are paginated"""
        # Arrange - Create more employees than page size
        for i in range(35):
            self.create_employee(code=f"MV{100 + i:03d}", start_date=date(2020, 1, 1))

        # Act
        url = reverse("hrm:employee-reports-employee-seniority-report")
        response = self.client.get(url)
        data = json.loads(response.content.decode())["data"]

        # Assert
        self.assertIn("count", data)
        self.assertIn("next", data)
        self.assertIn("results", data)
        self.assertEqual(data["count"], 35)
        # Default page size is 25
        self.assertEqual(len(data["results"]), 25)
        self.assertIsNotNone(data["next"])
