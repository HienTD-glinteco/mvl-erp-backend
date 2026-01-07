from .department_kpi_assessment import DepartmentKPIAssessmentViewSet
from .employee_kpi_assessment import (
    EmployeeKPIAssessmentViewSet,
    EmployeeSelfAssessmentViewSet,
    ManagerAssessmentViewSet,
)
from .kpi_assessment_period import KPIAssessmentPeriodManagerViewSet, KPIAssessmentPeriodViewSet
from .kpi_config import CurrentKPIConfigView
from .kpi_criterion import KPICriterionViewSet
from .mobile import MyKPIAssessmentViewSet, MyPenaltyTicketViewSet, MyTeamKPIAssessmentViewSet

# from .my_penalty_tickets import MyPenaltyTicketViewSet
from .payroll_slip import PayrollSlipViewSet
from .penalty_tickets import PenaltyTicketViewSet
from .recovery_voucher import RecoveryVoucherViewSet
from .salary_config import CurrentSalaryConfigView
from .salary_period import (
    SalaryPeriodNotReadySlipsViewSet,
    SalaryPeriodReadySlipsViewSet,
    SalaryPeriodViewSet,
)
from .sales_revenue import SalesRevenueViewSet
from .sales_revenue_report import SalesRevenueReportViewSet
from .travel_expense import TravelExpenseViewSet

__all__ = [
    "CurrentKPIConfigView",
    "EmployeeSelfAssessmentViewSet",
    "ManagerAssessmentViewSet",
    "KPICriterionViewSet",
    "CurrentSalaryConfigView",
    "KPIAssessmentPeriodViewSet",
    "KPIAssessmentPeriodManagerViewSet",
    "EmployeeKPIAssessmentViewSet",
    "DepartmentKPIAssessmentViewSet",
    "TravelExpenseViewSet",
    "RecoveryVoucherViewSet",
    "SalesRevenueViewSet",
    "SalesRevenueReportViewSet",
    "PenaltyTicketViewSet",
    # "MyPenaltyTicketViewSet",
    "SalaryPeriodViewSet",
    "PayrollSlipViewSet",
    "SalaryPeriodReadySlipsViewSet",
    "SalaryPeriodNotReadySlipsViewSet",
    "MyKPIAssessmentViewSet",
    "MyTeamKPIAssessmentViewSet",
    "MyPenaltyTicketViewSet",
]
