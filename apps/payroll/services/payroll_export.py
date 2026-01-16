"""Service for exporting payroll slips to XLSX."""

from django.utils.translation import gettext as _

from apps.payroll.models import PayrollSlip


class PayrollSlipExportService:
    """Service to build export schema for payroll slips."""

    def __init__(self, period):
        """Initialize with salary period.

        Args:
            period: SalaryPeriod instance
        """
        self.period = period

    def build_export_schema(self):
        """Build complete export schema with headers, data, and formulas.

        Returns:
            dict: Export schema compatible with XLSXGenerator format:
                {
                    "sheets": [{
                        "name": str,
                        "groups": [{"title": str, "span": int}, ...],
                        "headers": [str, ...],
                        "field_names": [str, ...],
                        "data": [dict, ...]
                    }]
                }
        """
        # Define headers
        headers = self._build_headers()
        groups = self._build_groups()
        field_names = self._build_field_names()

        # Build data for both sheets
        ready_slips = self._get_ready_slips()
        not_ready_slips = self._get_not_ready_slips()

        ready_data = self._build_sheet_data(ready_slips)
        not_ready_data = self._build_sheet_data(not_ready_slips)

        # Build schema
        schema = {
            "sheets": [
                {
                    "name": _("Ready Slips"),
                    "groups": groups,
                    "headers": headers,
                    "field_names": field_names,
                    "data": ready_data,
                },
                {
                    "name": _("Not Ready Slips"),
                    "groups": groups,
                    "headers": headers,
                    "field_names": field_names,
                    "data": not_ready_data,
                },
            ],
        }

        return schema

    def _get_ready_slips(self):
        """Get ready payroll slips based on period status."""
        if self.period.status == "COMPLETED":
            return (
                PayrollSlip.objects.filter(salary_period=self.period, status=PayrollSlip.Status.DELIVERED)
                .select_related("employee", "salary_period")
                .prefetch_related("employee__bank_accounts")
            )
        else:  # ONGOING
            return (
                PayrollSlip.objects.filter(salary_period=self.period, status=PayrollSlip.Status.READY)
                .select_related("employee", "salary_period")
                .prefetch_related("employee__bank_accounts")
            )

    def _get_not_ready_slips(self):
        """Get not ready payroll slips."""
        not_ready_statuses = [PayrollSlip.Status.PENDING, PayrollSlip.Status.HOLD]
        return (
            PayrollSlip.objects.filter(salary_period=self.period, status__in=not_ready_statuses)
            .select_related("employee", "salary_period")
            .prefetch_related("employee__bank_accounts")
        )

    def _build_headers(self):
        """Build column headers (row 2)."""
        headers = [
            "",  # A: STT - already in group
            "",  # B: Employee code - already in group
            "",  # C: Full name - already in group
            "",  # D: Department - already in group
            "",  # E: Position - already in group
            "",  # F: Employment status - already in group
            "",  # G: Is sale employee - already in group
            "",  # H: Email - already in group
            "",  # I: Sales revenue - already in group
            "",  # J: Transaction count - already in group
            # Position income (9 columns) - need sub-headers
            _("Base salary"),  # K
            _("Lunch allowance"),  # L
            _("Phone allowance"),  # M
            _("Travel allowance"),  # N
            _("KPI salary"),  # O
            _("KPI grade"),  # P
            _("KPI bonus"),  # Q
            _("Business bonus"),  # R
            _("Total"),  # S
            # Working days (5 columns) - need sub-headers
            _("Standard"),  # T
            _("Actual"),  # U
            _("Probation"),  # V
            _("Official"),  # W
            _("Probation %"),  # X
            # Income by working days
            "",  # Y: Already in group
            # Overtime (10 columns) - need sub-headers
            _("Weekday/Saturday"),  # Z
            _("Sunday"),  # AA
            _("Holiday"),  # AB
            _("Total"),  # AC
            _("Hourly rate"),  # AD
            _("Reference overtime pay"),  # AE
            _("Progress allowance"),  # AF
            _("Hours for calculation"),  # AG
            _("Taxable overtime"),  # AH
            _("Non-taxable overtime"),  # AI
            # Total income
            "",  # AJ: Already in group
            # Insurance
            "",  # AK: Has social insurance - already in group
            "",  # AL: Insurance base - already in group
            # Employer contributions (5 columns) - need sub-headers
            _("Social insurance (17%)"),  # AM
            _("Health insurance (3%)"),  # AN
            _("Accident insurance (0.5%)"),  # AO
            _("Unemployment insurance (1%)"),  # AP
            _("Union fee (2%)"),  # AQ
            # Employee deductions (4 columns) - need sub-headers
            _("Social insurance (8%)"),  # AR
            _("Health insurance (1.5%)"),  # AS
            _("Unemployment insurance (1%)"),  # AT
            _("Union fee (1%)"),  # AU
            # Tax (8 columns) - need sub-headers
            _("Tax code"),  # AV
            _("Tax method"),  # AW
            _("Dependents count"),  # AX
            _("Total deduction"),  # AY
            _("Non-taxable allowance"),  # AZ
            _("Min threshold 10%"),  # BA
            _("Taxable income"),  # BB
            _("Personal income tax"),  # BC
            # Adjustments
            "",  # BD: Back pay - already in group
            "",  # BE: Recovery - already in group
            # Net salary
            "",  # BF: Already in group
            # Bank account
            "",  # BG: Already in group
        ]
        return headers

    def _build_groups(self):
        """Build group headers (row 1) with colspan."""
        groups = [
            {"title": _("No."), "span": 1},
            {"title": _("Employee code"), "span": 1},
            {"title": _("Full name"), "span": 1},
            {"title": _("Department"), "span": 1},
            {"title": _("Position"), "span": 1},
            {"title": _("Employment status"), "span": 1},
            {"title": _("Is sale employee"), "span": 1},
            {"title": _("Email"), "span": 1},
            {"title": _("Sales revenue"), "span": 1},
            {"title": _("Transaction count"), "span": 1},
            {"title": _("Position income"), "span": 9},
            {"title": _("Working days"), "span": 5},
            {"title": _("Actual working days income"), "span": 1},
            {"title": _("Overtime"), "span": 10},
            {"title": _("Gross income"), "span": 1},
            {"title": _("Has social insurance"), "span": 1},
            {"title": _("Insurance base"), "span": 1},
            {"title": _("Employer contributions"), "span": 5},
            {"title": _("Employee deductions"), "span": 4},
            {"title": _("Tax information"), "span": 8},
            {"title": _("Back pay"), "span": 1},
            {"title": _("Recovery"), "span": 1},
            {"title": _("Net salary"), "span": 1},
            {"title": _("Bank account"), "span": 1},
        ]
        return groups

    def _build_field_names(self):
        """Build field names mapping."""
        field_names = [
            "stt",  # A
            "employee_code",  # B
            "employee_name",  # C
            "department_name",  # D
            "position_name",  # E
            "employment_status",  # F
            "is_sale_employee",  # G
            "employee_email",  # H
            "sales_revenue",  # I
            "sales_transaction_count",  # J
            # Position income (9 fields)
            "base_salary",  # K
            "lunch_allowance",  # L
            "phone_allowance",  # M
            "travel_expense_by_working_days",  # N
            "kpi_salary",  # O
            "kpi_grade",  # P
            "kpi_bonus",  # Q
            "business_progressive_salary",  # R
            "total_position_income",  # S
            # Working days (5 fields)
            "standard_working_days",  # T
            "total_working_days",  # U
            "probation_working_days",  # V
            "official_working_days",  # W
            "net_percentage",  # X
            # Income by working days (1 field)
            "actual_working_days_income",  # Y
            # Overtime (10 fields)
            "tc1_overtime_hours",  # Z
            "tc2_overtime_hours",  # AA
            "tc3_overtime_hours",  # AB
            "total_overtime_hours",  # AC
            "hourly_rate",  # AD
            "overtime_pay_reference",  # AE
            "overtime_progress_allowance",  # AF
            "overtime_hours_for_calculation",  # AG
            "taxable_overtime_salary",  # AH
            "non_taxable_overtime_salary",  # AI
            # Total income (1 field)
            "gross_income",  # AJ
            # Insurance (2 fields)
            "has_social_insurance",  # AK
            "social_insurance_base",  # AL
            # Employer contributions (5 fields)
            "employer_social_insurance",  # AM
            "employer_health_insurance",  # AN
            "employer_accident_insurance",  # AO
            "employer_unemployment_insurance",  # AP
            "employer_union_fee",  # AQ
            # Employee deductions (4 fields)
            "employee_social_insurance",  # AR
            "employee_health_insurance",  # AS
            "employee_unemployment_insurance",  # AT
            "employee_union_fee",  # AU
            # Tax (8 fields)
            "tax_code",  # AV
            "tax_calculation_method",  # AW
            "dependent_count",  # AX
            "total_deduction",  # AY
            "non_taxable_allowance",  # AZ
            "minimum_flat_tax_threshold",  # BA
            "taxable_income",  # BB
            "personal_income_tax",  # BC
            # Adjustments (2 fields)
            "back_pay_amount",  # BD
            "recovery_amount",  # BE
            # Net salary (1 field)
            "net_salary",  # BF
            # Bank account (1 field)
            "bank_account",  # BG
        ]
        return field_names

    def _build_sheet_data(self, slips):
        """Build sheet data with Excel formulas for calculated fields."""
        data = []

        # Get insurance config percentages from period's salary config
        insurance_config = self.period.salary_config_snapshot.get("insurance_contributions", {})
        employer_si_rate = insurance_config.get("employer_social_insurance", 17) / 100
        employer_hi_rate = insurance_config.get("employer_health_insurance", 3) / 100
        employer_ai_rate = insurance_config.get("employer_accident_insurance", 0.5) / 100
        employer_ui_rate = insurance_config.get("employer_unemployment_insurance", 1) / 100
        employer_uf_rate = insurance_config.get("employer_union_fee", 2) / 100
        employee_si_rate = insurance_config.get("employee_social_insurance", 8) / 100
        employee_hi_rate = insurance_config.get("employee_health_insurance", 1.5) / 100
        employee_ui_rate = insurance_config.get("employee_unemployment_insurance", 1) / 100
        employee_uf_rate = insurance_config.get("employee_union_fee", 1) / 100

        # Get tax config
        tax_config = self.period.salary_config_snapshot.get("personal_income_tax", {})
        personal_deduction = tax_config.get("personal_deduction", 11000000)
        dependent_deduction = tax_config.get("dependent_deduction", 4400000)

        for idx, slip in enumerate(slips, start=1):
            # Row number in Excel (accounting for header rows: 1 group + 1 header = 2 rows)
            excel_row = idx + 2

            row = {
                # A: STT
                "stt": idx,
                # B: Employee code
                "employee_code": slip.employee_code or "",
                # C: Full name
                "employee_name": slip.employee_name or "",
                # D: Department
                "department_name": slip.department_name or "",
                # E: Position
                "position_name": slip.position_name or "",
                # F: Employment status
                "employment_status": slip.employment_status or "",
                # G: Is sale employee
                "is_sale_employee": slip.is_sale_employee,
                # H: Email
                "employee_email": slip.employee_email or "",
                # I: Sales revenue
                "sales_revenue": slip.sales_revenue or 0,
                # J: Transaction count
                "sales_transaction_count": slip.sales_transaction_count or 0,
                # Position income (K-S)
                "base_salary": slip.base_salary or 0,  # K
                "lunch_allowance": slip.lunch_allowance or 0,  # L
                "phone_allowance": slip.phone_allowance or 0,  # M
                "travel_expense_by_working_days": slip.travel_expense_by_working_days or 0,  # N
                "kpi_salary": slip.kpi_salary or 0,  # O
                "kpi_grade": slip.kpi_grade or "",  # P
                "kpi_bonus": slip.kpi_bonus or 0,  # Q
                "business_progressive_salary": slip.business_progressive_salary or 0,  # R
                # S: Total position income = K+L+M+N+O+Q+R
                "total_position_income": f"=K{excel_row}+L{excel_row}+M{excel_row}+N{excel_row}+O{excel_row}+Q{excel_row}+R{excel_row}",
                # Working days (T-X)
                "standard_working_days": slip.standard_working_days or 0,  # T
                "total_working_days": slip.total_working_days or 0,  # U
                "probation_working_days": slip.probation_working_days or 0,  # V
                "official_working_days": slip.official_working_days or 0,  # W
                # X: Net percentage (0.85 or 1)
                "net_percentage": 0.85 if slip.net_percentage == 85 else 1.0,
                # Y: Actual working days income = (W*S+V*S*X)/T
                "actual_working_days_income": f"=(W{excel_row}*S{excel_row}+V{excel_row}*S{excel_row}*X{excel_row})/T{excel_row}",
                # Overtime (Z-AI)
                "tc1_overtime_hours": slip.tc1_overtime_hours or 0,  # Z
                "tc2_overtime_hours": slip.tc2_overtime_hours or 0,  # AA
                "tc3_overtime_hours": slip.tc3_overtime_hours or 0,  # AB
                "total_overtime_hours": slip.total_overtime_hours or 0,  # AC
                # AD: Hourly rate = IF(F="PROBATION",S*0.85/T/8,S/T/8)
                "hourly_rate": f'=IF(F{excel_row}="PROBATION",S{excel_row}*0.85/T{excel_row}/8,S{excel_row}/T{excel_row}/8)',
                # AE: Reference overtime pay = (Z*1.5+AA*2+AB*3)*AD
                "overtime_pay_reference": f"=(Z{excel_row}*1.5+AA{excel_row}*2+AB{excel_row}*3)*AD{excel_row}",
                # AF: Progress allowance = AE-AH
                "overtime_progress_allowance": f"=AE{excel_row}-AH{excel_row}",
                # AG: Hours for calculation = AC
                "overtime_hours_for_calculation": f"=AC{excel_row}",
                # AH: Taxable overtime = AG*AD
                "taxable_overtime_salary": f"=AG{excel_row}*AD{excel_row}",
                # AI: Non-taxable overtime = IF(AF>AH*2,AH*2,AE-AH)
                "non_taxable_overtime_salary": f"=IF(AF{excel_row}>AH{excel_row}*2,AH{excel_row}*2,AE{excel_row}-AH{excel_row})",
                # AJ: Gross income = Y+AH+AI
                "gross_income": f"=Y{excel_row}+AH{excel_row}+AI{excel_row}",
                # Insurance (AK-AL)
                # AK: Has social insurance
                "has_social_insurance": slip.has_social_insurance,
                # AL: Insurance base = IF(AK=TRUE,K,0)
                "social_insurance_base": f"=IF(AK{excel_row}=TRUE,K{excel_row},0)",
                # Employer contributions (AM-AQ)
                "employer_social_insurance": f"=AL{excel_row}*{employer_si_rate}",  # AM
                "employer_health_insurance": f"=AL{excel_row}*{employer_hi_rate}",  # AN
                "employer_accident_insurance": f"=AL{excel_row}*{employer_ai_rate}",  # AO
                "employer_unemployment_insurance": f"=AL{excel_row}*{employer_ui_rate}",  # AP
                "employer_union_fee": f"=AL{excel_row}*{employer_uf_rate}",  # AQ
                # Employee deductions (AR-AU)
                "employee_social_insurance": f"=AL{excel_row}*{employee_si_rate}",  # AR
                "employee_health_insurance": f"=AL{excel_row}*{employee_hi_rate}",  # AS
                "employee_unemployment_insurance": f"=AL{excel_row}*{employee_ui_rate}",  # AT
                "employee_union_fee": f"=AL{excel_row}*{employee_uf_rate}",  # AU
                # Tax information (AV-BC)
                "tax_code": slip.tax_code or "",  # AV
                # AW: Tax calculation method (translate)
                **self._get_tax_method_display(slip),  # AW
                "dependent_count": slip.dependent_count or 0,  # AX
                # AY: Total deduction = personal_deduction + dependent_count * dependent_deduction
                "total_deduction": f"={personal_deduction}+AX{excel_row}*{dependent_deduction}",
                # AZ: Non-taxable allowance = SUM(L:M)/T*(V*X+W)
                "non_taxable_allowance": f"=SUM(L{excel_row}:M{excel_row})/T{excel_row}*(V{excel_row}*X{excel_row}+W{excel_row})",
                # BA: Minimum flat tax threshold
                "minimum_flat_tax_threshold": tax_config.get("minimum_flat_tax_threshold", 2000000),
                # BB-BC: Taxable income and tax - conditional based on tax_calculation_method
                **self._get_tax_formulas(slip, excel_row),
                # Adjustments (BD-BE)
                "back_pay_amount": slip.back_pay_amount or 0,  # BD
                "recovery_amount": slip.recovery_amount or 0,  # BE
                # BF: Net salary = ROUND(AJ-SUM(AR:AT)-AU+BD-BE-BC,0)
                "net_salary": f"=ROUND(AJ{excel_row}-SUM(AR{excel_row}:AT{excel_row})-AU{excel_row}+BD{excel_row}-BE{excel_row}-BC{excel_row},0)",
                # BG: Bank account
                "bank_account": (
                    slip.employee.default_bank_account.account_number
                    if slip.employee and slip.employee.default_bank_account
                    else ""
                ),
            }

            data.append(row)

        return data

    def _get_tax_method_display(self, slip):
        """Get tax calculation method display value."""
        from apps.hrm.models import ContractType

        tax_method_display = ""
        if slip.tax_calculation_method:
            tax_method_display = dict(ContractType.TaxCalculationMethod.choices).get(
                slip.tax_calculation_method, slip.tax_calculation_method
            )
        return {"tax_calculation_method": str(tax_method_display)}

    def _get_tax_formulas(self, slip, excel_row):
        """Get taxable income and tax formulas based on tax_calculation_method."""
        tax_method = slip.tax_calculation_method or ""

        # BB: Taxable income
        if tax_method == "progressive":
            # =IF(AJ-SUM(AR:AT)-AY-AI-AZ>0,AJ-SUM(AR:AT)-AY-AI-AZ,0)
            taxable_income_formula = f"=IF(AJ{excel_row}-SUM(AR{excel_row}:AT{excel_row})-AY{excel_row}-AI{excel_row}-AZ{excel_row}>0,AJ{excel_row}-SUM(AR{excel_row}:AT{excel_row})-AY{excel_row}-AI{excel_row}-AZ{excel_row},0)"
        elif tax_method == "flat_10":
            # =AJ (gross income)
            taxable_income_formula = f"=AJ{excel_row}"
        else:  # none or empty
            taxable_income_formula = "=0"

        # BC: Personal income tax
        if tax_method == "progressive":
            # Progressive tax brackets
            tax_formula = f"=IF(BB{excel_row}<=5000000,BB{excel_row}*0.05,IF(BB{excel_row}<=10000000,BB{excel_row}*0.1-250000,IF(BB{excel_row}<=18000000,BB{excel_row}*0.15-750000,IF(BB{excel_row}<=32000000,BB{excel_row}*0.2-1650000,IF(BB{excel_row}<=52000000,BB{excel_row}*0.25-3250000,IF(BB{excel_row}<=80000000,BB{excel_row}*0.3-5850000,BB{excel_row}*0.35-9850000))))))"
        elif tax_method == "flat_10":
            # =IF(BB>=BA,BB*10%,0)
            tax_formula = f"=IF(BB{excel_row}>=BA{excel_row},BB{excel_row}*0.1,0)"
        else:  # none or empty
            tax_formula = "=0"

        return {
            "taxable_income": taxable_income_formula,
            "personal_income_tax": tax_formula,
        }
