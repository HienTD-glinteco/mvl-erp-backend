"""Payroll slip calculation service."""

from decimal import Decimal
from typing import Optional

from django.db.models import Sum
from django.utils import timezone

from apps.hrm.models import Contract, EmployeeDependent, EmployeeMonthlyTimesheet
from apps.payroll.models import (
    EmployeeKPIAssessment,
    PenaltyTicket,
    RecoveryVoucher,
    SalesRevenue,
    TravelExpense,
)


class PayrollCalculationService:
    """Service for calculating payroll slip values."""

    def __init__(self, payroll_slip):
        """Initialize with a PayrollSlip instance.

        Args:
            payroll_slip: PayrollSlip instance to calculate
        """
        self.slip = payroll_slip
        self.employee = payroll_slip.employee
        self.period = payroll_slip.salary_period
        self.config = payroll_slip.salary_period.salary_config_snapshot

    def calculate(self):
        """Perform full payroll calculation and update the slip.

        This method orchestrates the entire calculation process including:
        - Employee data caching
        - Contract data retrieval (optional - if no contract, salary fields will be 0)
        - KPI calculation
        - Sales performance
        - Timesheet and overtime
        - Travel expenses
        - Insurance contributions
        - Personal income tax
        - Recovery vouchers
        - Penalty status check
        - Final net salary
        """
        # Step 1: Cache employee information (independent of contract)
        self._cache_employee_data()

        # Step 2: Get employee's active contract (optional)
        contract = self._get_active_contract()

        # Step 3: Cache contract data (if contract exists)
        if contract:
            self._cache_contract_data(contract)
        else:
            # Set salary fields to 0 if no contract
            self._set_zero_salary_fields()

        # Step 4: Get KPI grade and calculate bonus
        self._calculate_kpi_bonus()

        # Step 5: Get timesheet data
        timesheet = self._get_timesheet()
        self._process_timesheet_data(timesheet)

        # Step 6: Get travel expenses (needed for business progressive calculation)
        self._calculate_travel_expenses()

        # Step 7: Get sales data and calculate business progressive salary
        self._calculate_business_progressive_salary()

        # Step 8: Calculate overtime pay (now includes business_progressive_salary in total_position_income)
        self._calculate_overtime_pay()

        # Step 9: Calculate gross income
        self._calculate_gross_income()

        # Step 10: Calculate insurance contributions
        self._calculate_insurance_contributions()

        # Step 11: Calculate personal income tax
        self._calculate_personal_income_tax()

        # Step 12: Get recovery vouchers
        self._process_recovery_vouchers()

        # Step 13: Calculate net salary
        self._calculate_net_salary()

        # Step 14: Check for unpaid penalties
        self._check_unpaid_penalties()

        # Step 15: Determine final status
        self._determine_final_status(contract, timesheet)

        # Step 16: Update timestamp and save
        self.slip.calculated_at = timezone.now()
        self.slip.save()

        # Step 17: Update related models status
        self._update_related_models_status()

    def _get_active_contract(self) -> Optional[Contract]:
        """Get employee's active contract for the salary period."""
        return (
            Contract.objects.filter(
                employee=self.employee, status=Contract.ContractStatus.ACTIVE, effective_date__lte=self.period.month
            )
            .order_by("-effective_date")
            .first()
        )

    def _cache_employee_data(self):
        """Cache employee information in the payroll slip.

        This caches basic employee info that doesn't depend on contract.
        """
        self.slip.employee_code = self.employee.code
        self.slip.employee_name = self.employee.fullname
        self.slip.employee_email = self.employee.email or ""
        self.slip.tax_code = self.employee.tax_code or ""
        self.slip.department_name = self.employee.department.name if self.employee.department else ""
        self.slip.position_name = self.employee.position.name if self.employee.position else ""

    def _cache_contract_data(self, contract: Contract):
        """Cache contract data in the payroll slip."""
        self.slip.contract_id = contract.id
        self.slip.base_salary = contract.base_salary
        self.slip.kpi_salary = contract.kpi_salary
        self.slip.lunch_allowance = contract.lunch_allowance or 0
        self.slip.phone_allowance = contract.phone_allowance or 0
        self.slip.other_allowance = contract.other_allowance or 0
        # Store employee_type, not contract status
        self.slip.employment_status = self.employee.employee_type or ""

    def _set_zero_salary_fields(self):
        """Set salary fields to 0 when no contract exists."""
        self.slip.contract_id = None
        self.slip.base_salary = 0
        self.slip.kpi_salary = 0
        self.slip.lunch_allowance = 0
        self.slip.phone_allowance = 0
        self.slip.other_allowance = 0
        self.slip.employment_status = ""

    def _calculate_kpi_bonus(self):
        """Calculate KPI bonus based on assessment."""
        kpi_assessment = EmployeeKPIAssessment.objects.filter(
            employee=self.employee, period__month=self.period.month
        ).first()

        # Get KPI grade (prefer grade_hrm, fallback to grade_manager, default to C)
        if kpi_assessment:
            kpi_grade = kpi_assessment.grade_hrm or kpi_assessment.grade_manager or "C"
        else:
            kpi_grade = "C"

        # Find KPI tier
        kpi_tiers = self.config["kpi_salary"]["tiers"]
        kpi_tier = next((t for t in kpi_tiers if t["code"] == kpi_grade), None)

        if kpi_tier:
            kpi_percentage = Decimal(str(kpi_tier["percentage"]))
        else:
            kpi_percentage = Decimal("0.0000")

        kpi_bonus = self.slip.base_salary * kpi_percentage

        self.slip.kpi_grade = kpi_grade
        self.slip.kpi_percentage = kpi_percentage
        self.slip.kpi_bonus = kpi_bonus.quantize(Decimal("1"))

    def _calculate_business_progressive_salary(self):
        """Calculate business progressive salary based on sales revenue."""
        sales_revenue_obj = SalesRevenue.objects.filter(employee=self.employee, month=self.period.month).first()

        if sales_revenue_obj:
            sales_revenue = sales_revenue_obj.revenue
            sales_transaction_count = sales_revenue_obj.transaction_count
        else:
            sales_revenue = 0
            sales_transaction_count = 0

        # Calculate business progressive salary using tier matching logic
        tiers = self.config["business_progressive_salary"]["tiers"]
        # Sort tiers by amount descending to get highest matching tier
        sorted_tiers = sorted(tiers, key=lambda t: t["amount"], reverse=True)

        business_grade = "M0"
        business_progressive_salary = Decimal("0")

        for tier in sorted_tiers:
            criteria = tier["criteria"]
            meets_all = True

            for criterion in criteria:
                if criterion["name"] == "revenue":
                    if sales_revenue < criterion["min"]:
                        meets_all = False
                        break
                elif criterion["name"] == "transaction_count":
                    if sales_transaction_count < criterion["min"]:
                        meets_all = False
                        break

            if meets_all:
                business_grade = tier["code"]
                business_progressive_salary = Decimal(str(tier["amount"]))
                break

        business_progressive_salary = (
            business_progressive_salary
            - self.slip.base_salary
            - self.slip.kpi_salary
            - self.slip.lunch_allowance
            - self.slip.other_allowance
            - self.slip.total_travel_expense
        )
        business_progressive_salary = max(Decimal("0"), business_progressive_salary)

        self.slip.sales_revenue = sales_revenue
        self.slip.sales_transaction_count = sales_transaction_count
        self.slip.business_grade = business_grade
        self.slip.business_progressive_salary = business_progressive_salary.quantize(Decimal("1"))

    def _get_timesheet(self) -> Optional[EmployeeMonthlyTimesheet]:
        """Get employee's monthly timesheet."""
        return EmployeeMonthlyTimesheet.objects.filter(employee=self.employee, report_date=self.period.month).first()

    def _process_timesheet_data(self, timesheet: Optional[EmployeeMonthlyTimesheet]):
        """Process timesheet data into payroll slip."""
        self.slip.standard_working_days = self.period.standard_working_days

        if timesheet:
            self.slip.total_working_days = timesheet.total_working_days
            self.slip.official_working_days = timesheet.official_working_days
            self.slip.probation_working_days = timesheet.probation_working_days
            self.slip.tc1_overtime_hours = timesheet.tc1_overtime_hours
            self.slip.tc2_overtime_hours = timesheet.tc2_overtime_hours
            self.slip.tc3_overtime_hours = timesheet.tc3_overtime_hours
        else:
            # Use zero values if no timesheet
            self.slip.total_working_days = Decimal("0.00")
            self.slip.official_working_days = Decimal("0.00")
            self.slip.probation_working_days = Decimal("0.00")
            self.slip.tc1_overtime_hours = Decimal("0.00")
            self.slip.tc2_overtime_hours = Decimal("0.00")
            self.slip.tc3_overtime_hours = Decimal("0.00")

    def _calculate_overtime_pay(self):
        """Calculate overtime payment with new formula."""
        from apps.hrm.constants import EmployeeType

        # Calculate total position income
        total_position_income = (
            self.slip.base_salary
            + self.slip.lunch_allowance
            + self.slip.phone_allowance
            + self.slip.other_allowance
            + self.slip.kpi_salary
            + self.slip.kpi_bonus
            + self.slip.business_progressive_salary
        )
        self.slip.total_position_income = total_position_income.quantize(Decimal("1"))

        # Calculate actual working days income
        if self.period.standard_working_days > 0:
            # Check if employee position is NVKD (sales staff) via position name
            is_sales_staff = False
            if self.employee.position:
                position_name = self.employee.position.name.upper()
                is_sales_staff = "NVKD" in position_name or "KINH DOANH" in position_name

            if is_sales_staff:
                # For sales staff: (total_working_days / standard_working_days) * total_position_income
                actual_working_days_income = (
                    self.slip.total_working_days / self.period.standard_working_days
                ) * total_position_income
            else:
                # For non-sales staff: ((official_working_days * total_position_income) + (probation_working_days * total_position_income * 0.85)) / standard_working_days
                official_income = self.slip.official_working_days * total_position_income
                probation_income = self.slip.probation_working_days * total_position_income * Decimal("0.85")
                actual_working_days_income = (official_income + probation_income) / self.period.standard_working_days

            self.slip.actual_working_days_income = actual_working_days_income.quantize(Decimal("1"))
        else:
            self.slip.actual_working_days_income = Decimal("0")

        # Calculate hourly rate based on employee status
        if self.period.standard_working_days > 0:
            # Check if employee status is probation
            is_probation = self.slip.employment_status in [
                EmployeeType.PROBATION,
                EmployeeType.PROBATION_TYPE_1,
                EmployeeType.UNPAID_PROBATION,
            ]

            if is_probation:
                # Probation: total_position_income * 0.85 / standard_working_days / 8
                self.slip.hourly_rate = (
                    (total_position_income * Decimal("0.85")) / (self.period.standard_working_days * Decimal("8"))
                ).quantize(Decimal("0.01"))
            else:
                # Non-probation: total_position_income / standard_working_days / 8
                self.slip.hourly_rate = (
                    total_position_income / (self.period.standard_working_days * Decimal("8"))
                ).quantize(Decimal("0.01"))
        else:
            self.slip.hourly_rate = Decimal("0.00")

        # Get overtime multipliers
        overtime_multipliers = self.config["overtime_multipliers"]

        # Calculate overtime pay for each type
        tc1_pay = (
            self.slip.tc1_overtime_hours
            * self.slip.hourly_rate
            * Decimal(str(overtime_multipliers["saturday_inweek"]))
        )

        tc2_pay = self.slip.tc2_overtime_hours * self.slip.hourly_rate * Decimal(str(overtime_multipliers["sunday"]))

        tc3_pay = self.slip.tc3_overtime_hours * self.slip.hourly_rate * Decimal(str(overtime_multipliers["holiday"]))

        self.slip.total_overtime_hours = (
            self.slip.tc1_overtime_hours + self.slip.tc2_overtime_hours + self.slip.tc3_overtime_hours
        )

        self.slip.overtime_pay = (tc1_pay + tc2_pay + tc3_pay).quantize(Decimal("1"))

        # Calculate taxable overtime salary
        taxable_overtime_salary = self.slip.total_overtime_hours * self.slip.hourly_rate
        self.slip.taxable_overtime_salary = taxable_overtime_salary.quantize(Decimal("1"))

        # Calculate overtime progress allowance
        overtime_progress_allowance = self.slip.overtime_pay - taxable_overtime_salary
        self.slip.overtime_progress_allowance = overtime_progress_allowance.quantize(Decimal("1"))

        # Calculate non-taxable overtime salary
        if overtime_progress_allowance > (taxable_overtime_salary * Decimal("2")):
            # If overtime progress allowance > (taxable overtime salary * 2), cap at 2x
            non_taxable_overtime_salary = taxable_overtime_salary * Decimal("2")
        else:
            # Otherwise, use overtime_pay - taxable_overtime_salary
            non_taxable_overtime_salary = self.slip.overtime_pay - taxable_overtime_salary

        self.slip.non_taxable_overtime_salary = non_taxable_overtime_salary.quantize(Decimal("1"))

    def _calculate_travel_expenses(self):
        """Calculate travel expenses."""
        travel_expenses = TravelExpense.objects.filter(employee=self.employee, month=self.period.month)

        taxable = (
            travel_expenses.filter(expense_type=TravelExpense.ExpenseType.TAXABLE).aggregate(Sum("amount"))[
                "amount__sum"
            ]
            or 0
        )

        non_taxable = (
            travel_expenses.filter(expense_type=TravelExpense.ExpenseType.NON_TAXABLE).aggregate(Sum("amount"))[
                "amount__sum"
            ]
            or 0
        )

        self.slip.taxable_travel_expense = Decimal(str(taxable))
        self.slip.non_taxable_travel_expense = Decimal(str(non_taxable))
        self.slip.total_travel_expense = Decimal(str(taxable + non_taxable))

    def _calculate_gross_income(self):
        """Calculate gross income with new formula."""
        self.slip.gross_income = (
            self.slip.actual_working_days_income
            + self.slip.taxable_overtime_salary
            + self.slip.non_taxable_overtime_salary
            + self.slip.total_travel_expense
        ).quantize(Decimal("1"))

    def _calculate_insurance_contributions(self):
        """Calculate insurance contributions."""
        from apps.hrm.constants import EmployeeType

        insurance_config = self.config["insurance_contributions"]

        # Check if employee is official (not probation)
        is_official = self.slip.employment_status == EmployeeType.OFFICIAL

        # Social insurance
        si_config = insurance_config["social_insurance"]
        if is_official:
            # Official employee: use base_salary with ceiling
            social_insurance_base = min(self.slip.base_salary, Decimal(str(si_config["salary_ceiling"])))
        else:
            # Non-official employee: no social insurance
            social_insurance_base = Decimal("0")

        self.slip.social_insurance_base = social_insurance_base
        self.slip.employee_social_insurance = (
            social_insurance_base * Decimal(str(si_config["employee_rate"]))
        ).quantize(Decimal("1"))
        self.slip.employer_social_insurance = (
            social_insurance_base * Decimal(str(si_config["employer_rate"]))
        ).quantize(Decimal("1"))

        # Health insurance
        hi_config = insurance_config["health_insurance"]
        hi_base = (
            min(social_insurance_base, Decimal(str(hi_config["salary_ceiling"]))) if is_official else Decimal("0")
        )
        self.slip.employee_health_insurance = (hi_base * Decimal(str(hi_config["employee_rate"]))).quantize(
            Decimal("1")
        )
        self.slip.employer_health_insurance = (hi_base * Decimal(str(hi_config["employer_rate"]))).quantize(
            Decimal("1")
        )

        # Unemployment insurance
        ui_config = insurance_config["unemployment_insurance"]
        ui_base = (
            min(social_insurance_base, Decimal(str(ui_config["salary_ceiling"]))) if is_official else Decimal("0")
        )
        self.slip.employee_unemployment_insurance = (ui_base * Decimal(str(ui_config["employee_rate"]))).quantize(
            Decimal("1")
        )
        self.slip.employer_unemployment_insurance = (ui_base * Decimal(str(ui_config["employer_rate"]))).quantize(
            Decimal("1")
        )

        # Union fee
        uf_config = insurance_config["union_fee"]
        uf_base = (
            min(social_insurance_base, Decimal(str(uf_config["salary_ceiling"]))) if is_official else Decimal("0")
        )
        self.slip.employee_union_fee = (uf_base * Decimal(str(uf_config["employee_rate"]))).quantize(Decimal("1"))
        self.slip.employer_union_fee = (uf_base * Decimal(str(uf_config["employer_rate"]))).quantize(Decimal("1"))

        # Accident insurance (employer only)
        ai_config = insurance_config["accident_occupational_insurance"]
        if is_official:
            if ai_config["salary_ceiling"] is None:
                ai_base = self.slip.base_salary
            else:
                ai_base = min(self.slip.base_salary, Decimal(str(ai_config["salary_ceiling"])))
        else:
            ai_base = Decimal("0")
        self.slip.employer_accident_insurance = (ai_base * Decimal(str(ai_config["employer_rate"]))).quantize(
            Decimal("1")
        )

    def _calculate_personal_income_tax(self):
        """Calculate personal income tax with updated formula."""
        from apps.hrm.constants import EmployeeType

        tax_config = self.config["personal_income_tax"]

        # Get dependent count
        dependent_count = EmployeeDependent.objects.filter(employee=self.employee, is_active=True).count()

        self.slip.dependent_count = dependent_count
        self.slip.personal_deduction = Decimal(str(tax_config["standard_deduction"]))
        self.slip.dependent_deduction = dependent_count * Decimal(str(tax_config["dependent_deduction"]))

        # Check if employee is official
        is_official = self.slip.employment_status == EmployeeType.OFFICIAL

        if is_official:
            # Official employee: Calculate taxable income base with deductions
            self.slip.taxable_income_base = (
                self.slip.gross_income
                - self.slip.non_taxable_travel_expense
                - self.slip.employee_social_insurance
                - self.slip.employee_health_insurance
                - self.slip.employee_unemployment_insurance
                - self.slip.non_taxable_overtime_salary
            ).quantize(Decimal("1"))

            # Calculate taxable income after deductions
            taxable_income = (
                self.slip.taxable_income_base - self.slip.personal_deduction - self.slip.dependent_deduction
            )

            if taxable_income < 0:
                taxable_income = Decimal("0")

            self.slip.taxable_income = taxable_income.quantize(Decimal("1"))

            # Progressive tax calculation
            personal_income_tax = Decimal("0")
            progressive_levels = tax_config["progressive_levels"]
            previous_threshold = Decimal("0")

            for level in progressive_levels:
                threshold = level["up_to"]
                rate = Decimal(str(level["rate"]))

                if threshold is None:
                    # Last bracket
                    if taxable_income > previous_threshold:
                        personal_income_tax += (taxable_income - previous_threshold) * rate
                    break

                threshold = Decimal(str(threshold))

                if taxable_income > threshold:
                    personal_income_tax += (threshold - previous_threshold) * rate
                    previous_threshold = threshold
                else:
                    if taxable_income > previous_threshold:
                        personal_income_tax += (taxable_income - previous_threshold) * rate
                    break

            self.slip.personal_income_tax = personal_income_tax.quantize(Decimal("1"))
        else:
            # Non-official employee: taxable_income_base = gross_income, tax = 10%
            self.slip.taxable_income_base = self.slip.gross_income
            self.slip.taxable_income = self.slip.gross_income
            self.slip.personal_income_tax = (self.slip.gross_income * Decimal("0.10")).quantize(Decimal("1"))

    def _process_recovery_vouchers(self):
        """Process recovery vouchers."""
        vouchers = RecoveryVoucher.objects.filter(employee=self.employee, month=self.period.month)

        back_pay = (
            vouchers.filter(voucher_type=RecoveryVoucher.VoucherType.BACK_PAY).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        recovery = (
            vouchers.filter(voucher_type=RecoveryVoucher.VoucherType.RECOVERY).aggregate(Sum("amount"))["amount__sum"]
            or 0
        )

        self.slip.back_pay_amount = Decimal(str(back_pay))
        self.slip.recovery_amount = Decimal(str(recovery))

    def _calculate_net_salary(self):
        """Calculate final net salary."""
        self.slip.net_salary = (
            self.slip.gross_income
            - self.slip.employee_social_insurance
            - self.slip.employee_health_insurance
            - self.slip.employee_unemployment_insurance
            - self.slip.employee_union_fee
            - self.slip.personal_income_tax
            + self.slip.back_pay_amount
            - self.slip.recovery_amount
        ).quantize(Decimal("1"))

    def _check_unpaid_penalties(self):
        """Check for unpaid penalty tickets."""
        unpaid_penalties = PenaltyTicket.objects.filter(
            employee=self.employee, month=self.period.month, status=PenaltyTicket.Status.UNPAID
        )

        self.slip.has_unpaid_penalty = unpaid_penalties.exists()
        self.slip.unpaid_penalty_count = unpaid_penalties.count()

    def _determine_final_status(self, contract, timesheet):
        """Determine final status based on data availability."""
        missing_reasons = []

        if not contract:
            missing_reasons.append("contract")
        if not timesheet:
            missing_reasons.append("timesheet")
        if self.slip.has_unpaid_penalty:
            missing_reasons.append(f"unpaid penalties ({self.slip.unpaid_penalty_count})")

        if missing_reasons:
            self.slip.status = self.slip.Status.PENDING
            self.slip.status_note = "Missing/blocking: " + ", ".join(missing_reasons)
        else:
            # Only change to READY if currently PENDING
            # Don't override HOLD or DELIVERED status
            if self.slip.status == self.slip.Status.PENDING:
                self.slip.status = self.slip.Status.READY
                self.slip.status_note = ""

    def _update_related_models_status(self):
        """Update status of related models to CALCULATED."""
        # Update sales revenue status
        SalesRevenue.objects.filter(employee=self.employee, month=self.period.month).update(
            status=SalesRevenue.SalesRevenueStatus.CALCULATED
        )

        # Update travel expenses status
        TravelExpense.objects.filter(employee=self.employee, month=self.period.month).update(
            status=TravelExpense.TravelExpenseStatus.CALCULATED
        )

        # Update recovery vouchers status
        RecoveryVoucher.objects.filter(employee=self.employee, month=self.period.month).update(
            status=RecoveryVoucher.RecoveryVoucherStatus.CALCULATED
        )
