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
            # Travel expense (2 columns) - need sub-headers
            _("Taxable"),  # AJ
            _("Non-taxable"),  # AK
            # Total income
            "",  # AL: Already in group
            # Insurance
            "",  # AM: Has social insurance - already in group
            "",  # AN: Insurance base - already in group
            # Employer contributions (5 columns) - need sub-headers
            _("Social insurance (17%)"),  # AO
            _("Health insurance (3%)"),  # AP
            _("Accident insurance (0.5%)"),  # AQ
            _("Unemployment insurance (1%)"),  # AR
            _("Union fee (2%)"),  # AS
            # Employee deductions (4 columns) - need sub-headers
            _("Social insurance (8%)"),  # AT
            _("Health insurance (1.5%)"),  # AU
            _("Unemployment insurance (1%)"),  # AV
            _("Union fee (1%)"),  # AW
            # Tax (8 columns) - need sub-headers
            _("Tax code"),  # AX
            _("Tax method"),  # AY
            _("Dependents count"),  # AZ
            _("Total deduction"),  # BA
            _("Non-taxable allowance"),  # BB
            _("Min threshold 10%"),  # BC
            _("Taxable income"),  # BD
            _("Personal income tax"),  # BE
            # Adjustments
            "",  # BF: Back pay - already in group
            "",  # BG: Recovery - already in group
            # Net salary
            "",  # BH: Already in group
            # Bank account
            "",  # BI: Already in group
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
            {"title": _("Travel expense"), "span": 2},
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
            # Travel expense (2 fields)
            "taxable_travel_expense",  # AJ
            "non_taxable_travel_expense",  # AK
            # Total income (1 field)
            "gross_income",  # AL
            # Insurance (2 fields)
            "has_social_insurance",  # AM
            "social_insurance_base",  # AN
            # Employer contributions (5 fields)
            "employer_social_insurance",  # AO
            "employer_health_insurance",  # AP
            "employer_accident_insurance",  # AQ
            "employer_unemployment_insurance",  # AR
            "employer_union_fee",  # AS
            # Employee deductions (4 fields)
            "employee_social_insurance",  # AT
            "employee_health_insurance",  # AU
            "employee_unemployment_insurance",  # AV
            "employee_union_fee",  # AW
            # Tax (8 fields)
            "tax_code",  # AX
            "tax_calculation_method",  # AY
            "dependent_count",  # AZ
            "total_deduction",  # BA
            "non_taxable_allowance",  # BB
            "minimum_flat_tax_threshold",  # BC
            "taxable_income",  # BD
            "personal_income_tax",  # BE
            # Adjustments (2 fields)
            "back_pay_amount",  # BF
            "recovery_amount",  # BG
            # Net salary (1 field)
            "net_salary",  # BH
            # Bank account (1 field)
            "bank_account",  # BI
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
                # Travel expense (AJ-AK)
                "taxable_travel_expense": slip.taxable_travel_expense or 0,  # AJ
                "non_taxable_travel_expense": slip.non_taxable_travel_expense or 0,  # AK
                # AL: Gross income = Y+AH+AI+AJ+AK
                "gross_income": f"=Y{excel_row}+AH{excel_row}+AI{excel_row}+AJ{excel_row}+AK{excel_row}",
                # Insurance (AM-AN)
                # AM: Has social insurance
                "has_social_insurance": slip.has_social_insurance,
                # AN: Insurance base = IF(AM=TRUE,K,0)
                "social_insurance_base": f"=IF(AM{excel_row}=TRUE,K{excel_row},0)",
                # Employer contributions (AO-AS)
                "employer_social_insurance": f"=AN{excel_row}*{employer_si_rate}",  # AO
                "employer_health_insurance": f"=AN{excel_row}*{employer_hi_rate}",  # AP
                "employer_accident_insurance": f"=AN{excel_row}*{employer_ai_rate}",  # AQ
                "employer_unemployment_insurance": f"=AN{excel_row}*{employer_ui_rate}",  # AR
                "employer_union_fee": f"=AN{excel_row}*{employer_uf_rate}",  # AS
                # Employee deductions (AT-AW)
                "employee_social_insurance": f"=AN{excel_row}*{employee_si_rate}",  # AT
                "employee_health_insurance": f"=AN{excel_row}*{employee_hi_rate}",  # AU
                "employee_unemployment_insurance": f"=AN{excel_row}*{employee_ui_rate}",  # AV
                "employee_union_fee": f"=AN{excel_row}*{employee_uf_rate}",  # AW
                # Tax information (AX-BE)
                "tax_code": slip.tax_code or "",  # AX
                # AY: Tax calculation method (translate)
                **self._get_tax_method_display(slip),  # AY
                "dependent_count": slip.dependent_count or 0,  # AZ
                # BA: Total deduction = 11000000 + AZ * 4400000
                "total_deduction": f"={personal_deduction}+AZ{excel_row}*{dependent_deduction}",
                # BB: Non-taxable allowance = SUM(L:M)/T*(V*X+W)
                "non_taxable_allowance": f"=SUM(L{excel_row}:M{excel_row})/T{excel_row}*(V{excel_row}*X{excel_row}+W{excel_row})",
                # BC: Minimum flat tax threshold
                "minimum_flat_tax_threshold": tax_config.get("minimum_flat_tax_threshold", 2000000),
                # BD-BE: Taxable income and tax - conditional based on tax_calculation_method
                **self._get_tax_formulas(slip, excel_row),
                # Adjustments (BF-BG)
                "back_pay_amount": slip.back_pay_amount or 0,  # BF
                "recovery_amount": slip.recovery_amount or 0,  # BG
                # BH: Net salary = ROUND(AL-SUM(AT:AV)-AW+BF-BG-BE,0)
                "net_salary": f"=ROUND(AL{excel_row}-SUM(AT{excel_row}:AV{excel_row})-AW{excel_row}+BF{excel_row}-BG{excel_row}-BE{excel_row},0)",
                # BI: Bank account
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
        """Get taxable income and tax formulas based on tax_calculation_method.

        BD: Taxable income
        BE: Personal income tax
        """
        tax_method = slip.tax_calculation_method or ""

        # BD: Taxable income
        if tax_method == "progressive":
            # =IF(AL-SUM(AT:AV)-BA-AI-BB>0,AL-SUM(AT:AV)-BA-AI-BB,0)
            taxable_income_formula = f"=IF(AL{excel_row}-AI{excel_row}-AK{excel_row}-SUM(AT{excel_row}:AV{excel_row})-BA{excel_row}-BB{excel_row}>0,AL{excel_row}-AI{excel_row}-AK{excel_row}-SUM(AT{excel_row}:AV{excel_row})-BA{excel_row}-BB{excel_row},0)"
        elif tax_method == "flat_10":
            # =AL (gross income)
            taxable_income_formula = f"=AL{excel_row}"
        else:  # none or empty
            taxable_income_formula = "=0"

        # BE: Personal income tax
        if tax_method == "progressive":
            # Progressive tax brackets
            tax_formula = f"=IF(BD{excel_row}<=5000000,BD{excel_row}*0.05,IF(BD{excel_row}<=10000000,BD{excel_row}*0.1-250000,IF(BD{excel_row}<=18000000,BD{excel_row}*0.15-750000,IF(BD{excel_row}<=32000000,BD{excel_row}*0.2-1650000,IF(BD{excel_row}<=52000000,BD{excel_row}*0.25-3250000,IF(BD{excel_row}<=80000000,BD{excel_row}*0.3-5850000,BD{excel_row}*0.35-9850000))))))"
        elif tax_method == "flat_10":
            # =IF(BD>=BC,BD*10%,0)
            tax_formula = f"=IF(BD{excel_row}>=BC{excel_row},BD{excel_row}*0.1,0)"
        else:  # none or empty
            tax_formula = "=0"

        return {
            "taxable_income": taxable_income_formula,
            "personal_income_tax": tax_formula,
        }
