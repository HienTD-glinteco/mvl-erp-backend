from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.api.views.employee import EmployeeViewSet
from apps.hrm.models import Block, Branch, BranchContactInfo, Department, Employee, EmployeeWorkHistory, Position

User = get_user_model()


class EmployeeActionAPITest(TestCase):
    """Test cases for Employee API actions"""

    def setUp(self):
        """Set up test data"""

        # Changed to superuser to bypass RoleBasedPermission for API tests
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)

        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )

        self.branch = Branch.objects.create(
            code="CN001",
            name="Test Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001",
            name="Test Block",
            branch=self.branch,
            block_type=Block.BlockType.BUSINESS,
        )
        self.department = Department.objects.create(
            code="PB001",
            name="Test Department",
            branch=self.branch,
            block=self.block,
        )
        self.position = Position.objects.create(
            code="CV_POSITION",
            name="Test Position",
        )

        self.onboarding_employee = Employee.objects.create(
            fullname="Onboarding Employee",
            username="onboarding001",
            email="onboarding1@example.com",
            phone="5754304508",
            attendance_code="ONB001",
            date_of_birth=date(1992, 6, 10),
            start_date=date(2024, 1, 1),
            branch=self.branch,
            block=self.block,
            department=self.department,
            status=Employee.Status.ONBOARDING,
            citizen_id="000000010024",
            personal_email="onboarding1@example.com",
        )

        self.active_employee = Employee.objects.create(
            fullname="Active Employee",
            username="active001",
            email="active1@example.com",
            phone="6586993429",
            attendance_code="ACT001",
            date_of_birth=date(1988, 3, 5),
            start_date="2024-01-01",
            branch=self.branch,
            block=self.block,
            department=self.department,
            position=self.position,
            citizen_id="000000010025",
            personal_email="requester@example.com",
        )
        # Set status to ACTIVE using update_fields to bypass validation
        self.active_employee.status = Employee.Status.ACTIVE
        self.active_employee.save(update_fields=["status"])
        # Start patchers for periodic/async aggregation tasks so they don't run during tests
        # Patch the symbol where it's used (signals) so .delay() calls are intercepted
        self._patcher_aggregate_hr = patch("apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history")
        self.mock_aggregate_hr = self._patcher_aggregate_hr.start()

        self._patcher_aggregate_recruit = patch(
            "apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate"
        )
        self.mock_aggregate_recruit = self._patcher_aggregate_recruit.start()

    def tearDown(self):
        # Stop patchers to clean up after each test
        self._patcher_aggregate_hr.stop()
        self._patcher_aggregate_recruit.stop()

    def test_active_action(self):
        """Test activating an employee with department and position assignment"""
        # Create a new position for assignment
        new_position = Position.objects.create(
            code="CV_NEW",
            name="New Position",
        )

        url = reverse("hrm:employee-active", kwargs={"pk": self.onboarding_employee.id})
        payload = {
            "start_date": "2024-02-01",
            "department_id": self.department.id,
            "position_id": new_position.id,
            "employee_type": "PROBATION",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.onboarding_employee.refresh_from_db()
        self.assertEqual(self.onboarding_employee.status, Employee.Status.ACTIVE)
        self.assertEqual(str(self.onboarding_employee.start_date), "2024-02-01")
        self.assertEqual(self.onboarding_employee.employee_type, "PROBATION")
        # Verify department and position update
        self.assertEqual(self.onboarding_employee.department, self.department)
        self.assertEqual(self.onboarding_employee.position, new_position)

        # Verify work history
        history = EmployeeWorkHistory.objects.filter(
            employee=self.onboarding_employee,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
        ).first()
        self.assertIsNotNone(history)
        self.assertIn("Assigned to", history.detail)
        self.assertIn(self.department.name, history.detail)
        self.assertIn(new_position.name, history.detail)

    def test_active_action_with_description(self):
        """Test activating an employee with a description"""
        url = reverse("hrm:employee-active", kwargs={"pk": self.onboarding_employee.id})
        payload = {
            "start_date": "2024-02-01",
            "department_id": self.department.id,
            "position_id": self.active_employee.position.id,
            "employee_type": "OFFICIAL",
            "description": "Promoted from internship",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        history = EmployeeWorkHistory.objects.filter(
            employee=self.onboarding_employee,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
        ).first()
        self.assertEqual(history.note, "Promoted from internship")

    def test_active_action_missing_fields_fails(self):
        """Test activation fails if department or position is missing"""
        url = reverse("hrm:employee-active", kwargs={"pk": self.onboarding_employee.id})

        # Missing department and position
        payload = {"start_date": "2024-02-01"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        data = response.json()

        # Handle standardized errors response structure
        if "error" in data and "errors" in data["error"]:
            errors = data["error"]["errors"]
            error_attrs = [err.get("attr") for err in errors]
            self.assertIn("department_id", error_attrs)
            self.assertIn("position_id", error_attrs)
            self.assertIn("employee_type", error_attrs)
        else:
            self.assertIn("department_id", data)
            self.assertIn("position_id", data)
            self.assertIn("employee_type", data)

    def test_active_action_inactive_department_fails(self):
        """Test activation fails if department is inactive"""
        inactive_dept = Department.objects.create(
            code="PB_INACTIVE",
            name="Inactive Dept",
            branch=self.branch,
            block=self.block,
            is_active=False,
        )
        url = reverse("hrm:employee-active", kwargs={"pk": self.onboarding_employee.id})
        payload = {
            "start_date": "2024-02-01",
            "department_id": inactive_dept.id,
            "position_id": self.active_employee.position.id,
            "employee_type": "PROBATION",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_active_action_inactive_position_fails(self):
        """Test activation fails if position is inactive"""
        inactive_position = Position.objects.create(
            code="CV_INACTIVE",
            name="Inactive Position",
            is_active=False,
        )
        url = reverse("hrm:employee-active", kwargs={"pk": self.onboarding_employee.id})
        payload = {
            "start_date": "2024-02-01",
            "department_id": self.department.id,
            "position_id": inactive_position.id,
            "employee_type": "PROBATION",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_active_action_on_active_employee_fails(self):
        url = reverse("hrm:employee-active", kwargs={"pk": self.active_employee.id})
        payload = {
            "start_date": "2024-02-01",
            "department_id": self.department.id,
            "position_id": self.active_employee.position.id,
            "employee_type": "PROBATION",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reactive_action_retain_seniority(self):
        # Set status to RESIGNED using update_fields to bypass validation
        self.onboarding_employee.status = Employee.Status.RESIGNED
        self.onboarding_employee.resignation_start_date = date(2024, 12, 31)
        self.onboarding_employee.resignation_reason = Employee.ResignationReason.VOLUNTARY_OTHER
        self.onboarding_employee.save(update_fields=["status", "resignation_start_date", "resignation_reason"])

        url = reverse("hrm:employee-reactive", kwargs={"pk": self.onboarding_employee.id})
        payload = {"start_date": "2025-01-01", "is_seniority_retained": True}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.onboarding_employee.refresh_from_db()
        self.assertEqual(self.onboarding_employee.status, Employee.Status.ACTIVE)
        # The reactive action always updates start_date, regardless of is_seniority_retained
        self.assertEqual(str(self.onboarding_employee.start_date), "2025-01-01")

    def test_reactive_action_not_retain_seniority(self):
        # Set status to RESIGNED using update_fields to bypass validation
        self.onboarding_employee.status = Employee.Status.RESIGNED
        self.onboarding_employee.resignation_start_date = date(2024, 12, 31)
        self.onboarding_employee.resignation_reason = Employee.ResignationReason.VOLUNTARY_OTHER
        self.onboarding_employee.save(update_fields=["status", "resignation_start_date", "resignation_reason"])

        url = reverse("hrm:employee-reactive", kwargs={"pk": self.onboarding_employee.id})
        payload = {"start_date": "2025-01-01", "is_seniority_retained": False}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.onboarding_employee.refresh_from_db()
        self.assertEqual(self.onboarding_employee.status, Employee.Status.ACTIVE)
        self.assertEqual(str(self.onboarding_employee.start_date), "2025-01-01")

    def test_resigned_action(self):
        url = reverse("hrm:employee-resigned", kwargs={"pk": self.active_employee.id})
        payload = {
            "start_date": "2024-12-31",
            "resignation_reason": Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_employee.refresh_from_db()
        self.assertEqual(self.active_employee.status, Employee.Status.RESIGNED)
        # The resigned action sets resignation_start_date, not start_date
        self.assertEqual(str(self.active_employee.resignation_start_date), "2024-12-31")
        self.assertEqual(
            self.active_employee.resignation_reason,
            Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
        )

    def test_resigned_action_on_onboarding_employee_fails(self):
        url = reverse("hrm:employee-resigned", kwargs={"pk": self.onboarding_employee.id})
        payload = {
            "start_date": "2024-12-31",
            "resignation_reason": Employee.ResignationReason.VOLUNTARY_CAREER_CHANGE,
        }
        response = self.client.post(url, payload, format="json")
        # The resigned action does NOT allow ONBOARDING -> RESIGNED transition
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.onboarding_employee.refresh_from_db()
        self.assertEqual(self.onboarding_employee.status, Employee.Status.ONBOARDING)

    def test_maternity_leave_action(self):
        url = reverse("hrm:employee-maternity-leave", kwargs={"pk": self.active_employee.id})
        payload = {"start_date": "2026-01-01", "end_date": "2027-04-01"}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_employee.refresh_from_db()
        self.assertEqual(self.active_employee.status, Employee.Status.MATERNITY_LEAVE)
        self.assertEqual(str(self.active_employee.resignation_start_date), "2026-01-01")
        self.assertEqual(str(self.active_employee.resignation_end_date), "2027-04-01")

    def test_maternity_leave_action_past_end_date(self):
        """Test maternity leave with end date in the past switches to ACTIVE status."""
        url = reverse("hrm:employee-maternity-leave", kwargs={"pk": self.active_employee.id})
        # Current time is 2026-01-07, so 2025 is in the past
        payload = {"start_date": "2025-10-01", "end_date": "2025-12-01"}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_employee.refresh_from_db()
        self.assertEqual(self.active_employee.status, Employee.Status.ACTIVE)
        # Resignation dates are cleared by model.clean() when status is ACTIVE
        self.assertIsNone(self.active_employee.resignation_start_date)
        self.assertIsNone(self.active_employee.resignation_end_date)

    def test_maternity_leave_action_on_onboarding_employee_fails(self):
        url = reverse("hrm:employee-maternity-leave", kwargs={"pk": self.onboarding_employee.id})
        payload = {"start_date": "2024-10-01", "end_date": "2025-04-01"}
        response = self.client.post(url, payload, format="json")
        # The maternity leave action does NOT allow ONBOARDING -> MATERNITY_LEAVE transition
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.onboarding_employee.refresh_from_db()
        self.assertEqual(self.onboarding_employee.status, Employee.Status.ONBOARDING)

    def test_transfer_action(self):
        """Test transferring an employee to a new department and position"""
        # Create a new department and position
        new_block = Block.objects.create(
            code="KH002",
            name="New Block",
            branch=self.branch,
            block_type=Block.BlockType.SUPPORT,
        )
        new_department = Department.objects.create(
            code="PB002",
            name="New Department",
            branch=self.branch,
            block=new_block,
        )
        new_position = Position.objects.create(
            code="CV002",
            name="Senior Manager",
        )

        url = reverse("hrm:employee-transfer", kwargs={"pk": self.active_employee.id})
        payload = {
            "date": "2024-03-01",
            "department_id": new_department.id,
            "position_id": new_position.id,
            "note": "Transferred to new department for expansion",
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_employee.refresh_from_db()
        self.assertEqual(self.active_employee.department, new_department)
        self.assertEqual(self.active_employee.position, new_position)
        # Branch and block should be automatically updated from the new department
        self.assertEqual(self.active_employee.branch, new_department.branch)
        self.assertEqual(self.active_employee.block, new_department.block)

    def test_change_employee_type_action(self):
        """Test changing employee type successfully creates work history and updates employee."""
        effective_date = timezone.localdate()

        url = reverse("hrm:employee-change-employee-type", kwargs={"pk": self.active_employee.id})
        payload = {"date": effective_date.isoformat(), "employee_type": "INTERN", "note": "Role change"}
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_employee.refresh_from_db()
        self.assertEqual(self.active_employee.employee_type, "INTERN")

        # Check that work history record was created
        wh = (
            EmployeeWorkHistory.objects.filter(
                employee=self.active_employee, name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE
            )
            .order_by("-date")
            .first()
        )
        self.assertIsNotNone(wh)
        self.assertEqual(str(wh.date), effective_date.isoformat())
        self.assertEqual(wh.from_date.isoformat(), effective_date.isoformat())
        self.assertEqual(wh.note, "Role change")

    def test_change_employee_type_action_future_date_fails(self):
        url = reverse("hrm:employee-change-employee-type", kwargs={"pk": self.active_employee.id})
        future_date = date.today().replace(year=date.today().year + 10).isoformat()
        payload = {"date": future_date, "employee_type": "INTERN"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_employee_type_action_earlier_than_history_fails(self):
        # Create an existing work history (CHANGE_EMPLOYEE_TYPE) later than the requested effective date
        EmployeeWorkHistory.objects.create(
            date=date(2024, 5, 1),
            from_date=date(2024, 5, 1),
            name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
            employee=self.active_employee,
            detail="existing change employee type history",
        )
        url = reverse("hrm:employee-change-employee-type", kwargs={"pk": self.active_employee.id})
        payload = {"date": "2024-04-01", "employee_type": "INTERN"}
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # No new change-employee-type work history should be created when validation fails
        change_type_count = EmployeeWorkHistory.objects.filter(
            employee=self.active_employee, name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE
        ).count()
        self.assertEqual(change_type_count, 1)

    def test_transfer_action_department_only(self):
        """Test transferring an employee with same position"""
        # Create a new department
        new_block = Block.objects.create(
            code="KH003",
            name="Another Block",
            branch=self.branch,
            block_type=Block.BlockType.SUPPORT,
        )
        new_department = Department.objects.create(
            code="PB003",
            name="Another Department",
            branch=self.branch,
            block=new_block,
        )

        # Keep the same position but transfer to new department
        original_position = Position.objects.create(
            code="CV003",
            name="Manager",
        )
        self.active_employee.position = original_position
        self.active_employee.save(update_fields=["position"])

        url = reverse("hrm:employee-transfer", kwargs={"pk": self.active_employee.id})
        payload = {
            "date": "2024-04-01",
            "department_id": new_department.id,
            "position_id": original_position.id,
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.active_employee.refresh_from_db()
        self.assertEqual(self.active_employee.department, new_department)
        self.assertEqual(self.active_employee.position, original_position)

    def test_transfer_action_validates_department(self):
        """Test that transfer action validates the department"""
        url = reverse("hrm:employee-transfer", kwargs={"pk": self.active_employee.id})
        payload = {
            "date": "2024-03-01",
            "department_id": 99999,  # Non-existent department
            "position_id": 1,
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transfer_action_validates_position(self):
        """Test that transfer action validates the position"""
        url = reverse("hrm:employee-transfer", kwargs={"pk": self.active_employee.id})
        payload = {
            "date": "2024-03-01",
            "department_id": self.department.id,
            "position_id": 99999,  # Non-existent position
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transfer_action_requires_date(self):
        """Test that transfer action requires date field"""
        url = reverse("hrm:employee-transfer", kwargs={"pk": self.active_employee.id})
        payload = {
            "department_id": self.department.id,
            "position_id": 1,
        }
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmployeeEmailTemplateContextTest(TestCase):
    """Validate get_template_action_data context construction."""

    def setUp(self):
        self.province = Province.objects.create(code="01", name="Test Province")
        self.admin_unit = AdministrativeUnit.objects.create(
            code="01",
            name="Test Admin Unit",
            parent_province=self.province,
            level=AdministrativeUnit.UnitLevel.DISTRICT,
        )
        self.branch = Branch.objects.create(
            code="CN001",
            name="Test Branch",
            province=self.province,
            administrative_unit=self.admin_unit,
        )
        self.block = Block.objects.create(
            code="KH001",
            name="Support Block",
            branch=self.branch,
            block_type=Block.BlockType.SUPPORT,
        )
        self.department = Department.objects.create(
            code="PB001",
            name="HR Department",
            branch=self.branch,
            block=self.block,
        )
        self.employee_counter = 0

        # Patch Celery-triggered tasks invoked by employee signals
        self.hr_report_patcher = patch(
            "apps.hrm.signals.hr_reports.aggregate_hr_reports_for_work_history.delay"
        ).start()
        self.recruitment_report_patcher = patch(
            "apps.hrm.signals.recruitment_reports.aggregate_recruitment_reports_for_candidate.delay"
        ).start()
        self.timesheet_patcher = patch("apps.hrm.signals.employee.prepare_monthly_timesheets.delay").start()

        self.department_leader = self._create_employee(fullname="Leader One")
        self.department.leader = self.department_leader
        self.department.save(update_fields=["leader"])

    def tearDown(self):
        self.hr_report_patcher.stop()
        self.recruitment_report_patcher.stop()
        self.timesheet_patcher.stop()
        super().tearDown()

    def _create_employee(self, **overrides):
        self.employee_counter += 1
        suffix = f"{self.employee_counter:03d}"
        defaults = {
            "fullname": f"Employee {suffix}",
            "username": f"employee{suffix}",
            "email": f"employee{suffix}@example.com",
            "phone": f"09{self.employee_counter:08d}",
            "attendance_code": f"{self.employee_counter:05d}",
            "start_date": date(2024, 1, 1),
            "department": self.department,
            "branch": self.branch,
            "block": self.block,
            "citizen_id": f"987654{self.employee_counter:04d}",
            "personal_email": f"employee{suffix}@example.com",
        }
        defaults.update(overrides)
        return Employee.objects.create(**defaults)

    @patch("apps.hrm.api.views.employee.generate_valid_password")
    def test_welcome_email_send_populates_context_and_updates_password(self, mock_generate_valid_password):
        mock_generate_valid_password.return_value = "Demo123!@#"
        BranchContactInfo.objects.create(
            branch=self.branch,
            business_line="Sales",
            name="Alice",
            phone_number="0912345678",
            email="alice@example.com",
        )
        employee = self._create_employee(fullname="New Hire")
        employee.user.set_password = MagicMock()
        employee.user.save = MagicMock()

        viewset = EmployeeViewSet()
        viewset.action = "welcome_email_send"

        context = viewset.get_template_action_data(employee, "welcome")

        self.assertEqual(context["new_password"], "Demo123!@#")
        employee.user.set_password.assert_called_once_with("Demo123!@#")
        employee.user.save.assert_called_once()
        self.assertEqual(context["employee_department_name"], self.department.name)
        self.assertEqual(context["leader_fullname"], self.department_leader.fullname)
        self.assertEqual(len(context["branch_contact_infos"]), 1)
        self.assertEqual(context["branch_contact_infos"][0]["email"], "alice@example.com")

    def test_welcome_email_preview_returns_placeholder_and_skips_password_reset(self):
        employee = self._create_employee(fullname="Preview User")
        employee.user.set_password = MagicMock()
        employee.user.save = MagicMock()

        viewset = EmployeeViewSet()
        viewset.action = "welcome_email_preview"

        context = viewset.get_template_action_data(employee, "welcome")

        self.assertEqual(
            context["new_password"],
            "********",
        )
        employee.user.set_password.assert_not_called()
        employee.user.save.assert_not_called()
        self.assertEqual(context["branch_contact_infos"], [])

    @override_settings(SMS_API_URL="https://maivietland.com/logo.png")
    def test_context_includes_logo_image_url(self):
        """Test that logo_image_url is included in context"""
        employee = self._create_employee(fullname="Logo Test User")

        viewset = EmployeeViewSet()
        viewset.action = "welcome_email_preview"

        context = viewset.get_template_action_data(employee, "welcome")

        self.assertIn("logo_image_url", context)
        self.assertIn("/logo.png", context["logo_image_url"])

    def test_context_with_department_without_leader(self):
        """Test context when department has no leader"""
        self.department.leader = None
        self.department.save(update_fields=["leader"])

        employee = self._create_employee(fullname="No Leader User")

        viewset = EmployeeViewSet()
        viewset.action = "welcome_email_preview"

        context = viewset.get_template_action_data(employee, "welcome")

        self.assertNotIn("leader_fullname", context)

    def test_context_with_multiple_branch_contact_infos(self):
        """Test context with multiple branch contact information entries"""
        BranchContactInfo.objects.create(
            branch=self.branch,
            business_line="Sales",
            name="Alice",
            phone_number="0912345678",
            email="alice@example.com",
        )
        BranchContactInfo.objects.create(
            branch=self.branch,
            business_line="Support",
            name="Bob",
            phone_number="0987654321",
            email="bob@example.com",
        )
        BranchContactInfo.objects.create(
            branch=self.branch,
            business_line="HR",
            name="Charlie",
            phone_number="0901234567",
            email="charlie@example.com",
        )

        employee = self._create_employee(fullname="Multi Contact User")

        viewset = EmployeeViewSet()
        viewset.action = "welcome_email_send"

        context = viewset.get_template_action_data(employee, "welcome")

        self.assertEqual(len(context["branch_contact_infos"]), 3)
        self.assertEqual(context["branch_contact_infos"][0]["name"], "Alice")
        self.assertEqual(context["branch_contact_infos"][1]["name"], "Bob")
        self.assertEqual(context["branch_contact_infos"][2]["name"], "Charlie")
        self.assertEqual(context["branch_contact_infos"][0]["business_line"], "Sales")
        self.assertEqual(context["branch_contact_infos"][1]["email"], "bob@example.com")
        self.assertEqual(context["branch_contact_infos"][2]["phone_number"], "0901234567")

    def test_context_structure_matches_expected_schema(self):
        """Test that context structure matches the expected schema for template"""
        BranchContactInfo.objects.create(
            branch=self.branch,
            business_line="Sales",
            name="Alice",
            phone_number="0912345678",
            email="alice@example.com",
        )

        employee = self._create_employee(fullname="Schema Test User")

        viewset = EmployeeViewSet()
        viewset.action = "welcome_email_send"

        context = viewset.get_template_action_data(employee, "welcome")

        # Check top-level keys (flat structure)
        self.assertIn("employee_fullname", context)
        self.assertIn("employee_email", context)
        self.assertIn("employee_username", context)
        self.assertIn("employee_start_date", context)
        self.assertIn("employee_code", context)
        self.assertIn("employee_department_name", context)
        self.assertIn("new_password", context)
        self.assertIn("logo_image_url", context)
        self.assertIn("branch_contact_infos", context)

        # Check leader keys (flat structure)
        self.assertIn("leader_fullname", context)
        self.assertIn("leader_department_name", context)
        self.assertIn("leader_block_name", context)
        self.assertIn("leader_branch_name", context)

        # Check branch_contact_infos structure
        self.assertIsInstance(context["branch_contact_infos"], list)
        self.assertGreater(len(context["branch_contact_infos"]), 0)
        contact_info = context["branch_contact_infos"][0]
        self.assertIn("business_line", contact_info)
        self.assertIn("name", contact_info)
        self.assertIn("phone_number", contact_info)
        self.assertIn("email", contact_info)

    def test_employee_start_date_is_isoformat(self):
        """Test that employee start_date is converted to ISO format string"""
        employee = self._create_employee(fullname="Date Format User", start_date=date(2024, 6, 15))

        viewset = EmployeeViewSet()
        viewset.action = "welcome_email_preview"

        context = viewset.get_template_action_data(employee, "welcome")

        self.assertEqual(context["employee_start_date"], "2024-06-15")
        self.assertIsInstance(context["employee_start_date"], str)
