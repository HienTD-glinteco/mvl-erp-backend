# OpenAPI Examples for PR #198 Endpoints

This document provides complete OpenAPI example implementations for all 8 endpoints in PR #198.

## How to Use These Examples

1. Import `OpenApiExample` in the view files
2. Add `examples=[...]` parameter to each `@extend_schema` decorator
3. Ensure all response examples use the envelope format: `{success, data, error}`

## Import Statement

Add to both view files:
```python
from drf_spectacular.utils import extend_schema, OpenApiExample
```

---

## 1. Staff Growth Report (`/api/hrm/reports/staff-growth/`)

**File**: `apps/hrm/api/views/recruitment_reports.py`

```python
@extend_schema(
    summary="Staff Growth Report",
    description="Aggregate staff changes (introductions, returns, new hires, transfers, resignations) by period (week/month).",
    parameters=[StaffGrowthReportParametersSerializer],
    responses={200: StaffGrowthReportAggregatedSerializer(many=True)},
    examples=[
        OpenApiExample(
            "Success - Monthly Period",
            value={
                "success": True,
                "data": [
                    {
                        "period_type": "month",
                        "label": "Month 10/2025",
                        "num_introductions": 5,
                        "num_returns": 2,
                        "num_new_hires": 10,
                        "num_transfers": 3,
                        "num_resignations": 1
                    },
                    {
                        "period_type": "month",
                        "label": "Month 11/2025",
                        "num_introductions": 7,
                        "num_returns": 3,
                        "num_new_hires": 12,
                        "num_transfers": 2,
                        "num_resignations": 2
                    }
                ],
                "error": None
            },
            response_only=True,
        ),
        OpenApiExample(
            "Success - Weekly Period",
            value={
                "success": True,
                "data": [
                    {
                        "period_type": "week",
                        "label": "(01/10 - 07/10)",
                        "num_introductions": 2,
                        "num_returns": 1,
                        "num_new_hires": 4,
                        "num_transfers": 1,
                        "num_resignations": 0
                    },
                    {
                        "period_type": "week",
                        "label": "(08/10 - 14/10)",
                        "num_introductions": 3,
                        "num_returns": 1,
                        "num_new_hires": 6,
                        "num_transfers": 2,
                        "num_resignations": 1
                    }
                ],
                "error": None
            },
            response_only=True,
        ),
        OpenApiExample(
            "Error - Invalid Period Type",
            value={
                "success": False,
                "data": None,
                "error": {
                    "period_type": ["\"yearly\" is not a valid choice."]
                }
            },
            response_only=True,
            status_codes=["400"],
        ),
    ],
)
@action(detail=False, methods=["get"], url_path="staff-growth")
def staff_growth(self, request):
    # ... existing implementation
```

---

## 2. Recruitment Source Report (`/api/hrm/reports/recruitment-source/`)

```python
@extend_schema(
    summary="Recruitment Source Report",
    description="Aggregate hire statistics by recruitment source in nested organizational format (no period aggregation).",
    parameters=[RecruitmentSourceReportParametersSerializer],
    responses={200: RecruitmentSourceReportAggregatedSerializer},
    examples=[
        OpenApiExample(
            "Success - Nested Organizational Structure",
            value={
                "success": True,
                "data": {
                    "sources": ["LinkedIn", "Job Fair", "Employee Referral", "Website"],
                    "data": [
                        {
                            "type": "branch",
                            "name": "Hanoi Branch",
                            "statistics": [15, 8, 12, 5],  # Hires per source
                            "children": [
                                {
                                    "type": "block",
                                    "name": "Business Block",
                                    "statistics": [10, 5, 8, 3],
                                    "children": [
                                        {
                                            "type": "department",
                                            "name": "IT Department",
                                            "statistics": [5, 2, 4, 2]
                                        },
                                        {
                                            "type": "department",
                                            "name": "HR Department",
                                            "statistics": [5, 3, 4, 1]
                                        }
                                    ]
                                },
                                {
                                    "type": "block",
                                    "name": "Support Block",
                                    "statistics": [5, 3, 4, 2],
                                    "children": [
                                        {
                                            "type": "department",
                                            "name": "Admin Department",
                                            "statistics": [5, 3, 4, 2]
                                        }
                                    ]
                                }
                            ]
                        },
                        {
                            "type": "branch",
                            "name": "HCMC Branch",
                            "statistics": [12, 6, 10, 4],
                            "children": [
                                {
                                    "type": "block",
                                    "name": "Business Block",
                                    "statistics": [12, 6, 10, 4],
                                    "children": [
                                        {
                                            "type": "department",
                                            "name": "Sales Department",
                                            "statistics": [12, 6, 10, 4]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                "error": None
            },
            response_only=True,
        ),
        OpenApiExample(
            "Success - Empty Result",
            value={
                "success": True,
                "data": {
                    "sources": [],
                    "data": []
                },
                "error": None
            },
            response_only=True,
        ),
    ],
)
@action(detail=False, methods=["get"], url_path="recruitment-source")
def recruitment_source(self, request):
    # ... existing implementation
```

---

## 3. Recruitment Channel Report (`/api/hrm/reports/recruitment-channel/`)

```python
@extend_schema(
    summary="Recruitment Channel Report",
    description="Aggregate hire statistics by recruitment channel in nested organizational format (no period aggregation).",
    parameters=[RecruitmentChannelReportParametersSerializer],
    responses={200: RecruitmentChannelReportAggregatedSerializer},
    examples=[
        OpenApiExample(
            "Success - Nested Structure by Channel",
            value={
                "success": True,
                "data": {
                    "channels": ["Online Ads", "Job Portals", "Social Media", "Recruitment Events"],
                    "data": [
                        {
                            "type": "branch",
                            "name": "Hanoi Branch",
                            "statistics": [20, 15, 10, 8],  # Hires per channel
                            "children": [
                                {
                                    "type": "block",
                                    "name": "Business Block",
                                    "statistics": [15, 10, 6, 5],
                                    "children": [
                                        {
                                            "type": "department",
                                            "name": "IT Department",
                                            "statistics": [8, 5, 3, 2]
                                        },
                                        {
                                            "type": "department",
                                            "name": "Marketing Department",
                                            "statistics": [7, 5, 3, 3]
                                        }
                                    ]
                                }
                            ]
                        }
                    ]
                },
                "error": None
            },
            response_only=True,
        ),
    ],
)
@action(detail=False, methods=["get"], url_path="recruitment-channel")
def recruitment_channel(self, request):
    # ... existing implementation
```

---

## 4. Recruitment Cost Report (`/api/hrm/reports/recruitment-cost/`)

```python
@extend_schema(
    summary="Recruitment Cost Report",
    description="Aggregate recruitment cost data by source type and months (no period aggregation).",
    parameters=[RecruitmentCostReportParametersSerializer],
    responses={200: RecruitmentCostReportAggregatedSerializer},
    examples=[
        OpenApiExample(
            "Success - Cost by Source Type and Month",
            value={
                "success": True,
                "data": {
                    "months": ["10/2025", "11/2025", "12/2025", "Total"],
                    "data": [
                        {
                            "source_type": "referral_source",
                            "months": [
                                {"total": "50000.00", "count": 10, "avg": "5000.00"},
                                {"total": "60000.00", "count": 12, "avg": "5000.00"},
                                {"total": "55000.00", "count": 11, "avg": "5000.00"},
                                {"total": "165000.00", "count": 33, "avg": "5000.00"}  # Total column
                            ]
                        },
                        {
                            "source_type": "marketing_channel",
                            "months": [
                                {"total": "120000.00", "count": 15, "avg": "8000.00"},
                                {"total": "140000.00", "count": 17, "avg": "8235.29"},
                                {"total": "100000.00", "count": 12, "avg": "8333.33"},
                                {"total": "360000.00", "count": 44, "avg": "8181.82"}  # Total column
                            ]
                        },
                        {
                            "source_type": "job_website_channel",
                            "months": [
                                {"total": "80000.00", "count": 20, "avg": "4000.00"},
                                {"total": "75000.00", "count": 18, "avg": "4166.67"},
                                {"total": "90000.00", "count": 22, "avg": "4090.91"},
                                {"total": "245000.00", "count": 60, "avg": "4083.33"}  # Total column
                            ]
                        },
                        {
                            "source_type": "recruitment_department_source",
                            "months": [
                                {"total": "0.00", "count": 5, "avg": "0.00"},
                                {"total": "0.00", "count": 6, "avg": "0.00"},
                                {"total": "0.00", "count": 4, "avg": "0.00"},
                                {"total": "0.00", "count": 15, "avg": "0.00"}  # No cost, only count
                            ]
                        },
                        {
                            "source_type": "returning_employee",
                            "months": [
                                {"total": "0.00", "count": 2, "avg": "0.00"},
                                {"total": "0.00", "count": 3, "avg": "0.00"},
                                {"total": "0.00", "count": 1, "avg": "0.00"},
                                {"total": "0.00", "count": 6, "avg": "0.00"}  # No cost, only count
                            ]
                        }
                    ]
                },
                "error": None
            },
            response_only=True,
        ),
        OpenApiExample(
            "Success - Single Month",
            value={
                "success": True,
                "data": {
                    "months": ["10/2025", "Total"],
                    "data": [
                        {
                            "source_type": "referral_source",
                            "months": [
                                {"total": "50000.00", "count": 10, "avg": "5000.00"},
                                {"total": "50000.00", "count": 10, "avg": "5000.00"}
                            ]
                        }
                    ]
                },
                "error": None
            },
            response_only=True,
        ),
    ],
)
@action(detail=False, methods=["get"], url_path="recruitment-cost")
def recruitment_cost(self, request):
    # ... existing implementation
```

---

## 5. Hired Candidate Report (`/api/hrm/reports/hired-candidate/`)

```python
@extend_schema(
    summary="Hired Candidate Report",
    description="Aggregate hired candidate statistics by source type with period aggregation (week/month) and conditional employee details.",
    parameters=[HiredCandidateReportParametersSerializer],
    responses={200: HiredCandidateReportAggregatedSerializer},
    examples=[
        OpenApiExample(
            "Success - Monthly with Employee Breakdown for Referrals",
            value={
                "success": True,
                "data": {
                    "period_type": "month",
                    "months": ["10/2025", "11/2025", "Total"],
                    "sources": ["Total Hired"],
                    "data": [
                        {
                            "type": "source_type",
                            "name": "Referral Source",
                            "statistics": [[15], [18], [33]],  # Total per period
                            "children": [  # Employee breakdown only for referral_source
                                {
                                    "type": "employee",
                                    "name": "Nguyen Van A",
                                    "statistics": [[8], [10], [18]]
                                },
                                {
                                    "type": "employee",
                                    "name": "Tran Thi B",
                                    "statistics": [[7], [8], [15]]
                                }
                            ]
                        },
                        {
                            "type": "source_type",
                            "name": "Marketing Channel",
                            "statistics": [[20], [25], [45]],
                            "children": []  # No children for non-referral sources
                        },
                        {
                            "type": "source_type",
                            "name": "Job Website Channel",
                            "statistics": [[30], [35], [65]],
                            "children": []
                        },
                        {
                            "type": "source_type",
                            "name": "Recruitment Department Source",
                            "statistics": [[10], [12], [22]],
                            "children": []
                        },
                        {
                            "type": "source_type",
                            "name": "Returning Employee",
                            "statistics": [[5], [6], [11]],
                            "children": []
                        }
                    ]
                },
                "error": None
            },
            response_only=True,
        ),
        OpenApiExample(
            "Success - Weekly Period",
            value={
                "success": True,
                "data": {
                    "period_type": "week",
                    "months": ["(01/10 - 07/10)", "(08/10 - 14/10)", "Total"],
                    "sources": ["Total Hired"],
                    "data": [
                        {
                            "type": "source_type",
                            "name": "Referral Source",
                            "statistics": [[5], [6], [11]],
                            "children": [
                                {
                                    "type": "employee",
                                    "name": "Nguyen Van A",
                                    "statistics": [[5], [6], [11]]
                                }
                            ]
                        },
                        {
                            "type": "source_type",
                            "name": "Marketing Channel",
                            "statistics": [[8], [10], [18]],
                            "children": []
                        }
                    ]
                },
                "error": None
            },
            response_only=True,
        ),
    ],
)
@action(detail=False, methods=["get"], url_path="hired-candidate")
def hired_candidate(self, request):
    # ... existing implementation
```

---

## 6. Referral Cost Report (`/api/hrm/reports/referral-cost/`)

```python
@extend_schema(
    summary="Referral Cost Report",
    description=(
        "Referral cost report with department summary and employee details.\n\n"
        "**Important**: This report is restricted to a single month query only (use month=MM/YYYY parameter). "
        "This is because referral costs are queried directly from RecruitmentExpense table for detailed employee tracking. "
        "For multi-month cost analysis, use the recruitment-cost endpoint instead."
    ),
    parameters=[ReferralCostReportParametersSerializer],
    responses={200: ReferralCostReportAggregatedSerializer},
    examples=[
        OpenApiExample(
            "Success - Department-Based Structure",
            value={
                "success": True,
                "data": {
                    "data": [
                        {
                            "name": "IT Department",
                            "items": [
                                {
                                    "id": 1,
                                    "date": "2025-10-15",
                                    "recruitment_source": {
                                        "id": 1,
                                        "code": "REFERRAL",
                                        "name": "Employee Referral",
                                        "allow_referral": True
                                    },
                                    "recruitment_channel": {
                                        "id": 1,
                                        "code": "INTERNAL",
                                        "name": "Internal Referral"
                                    },
                                    "recruitment_request": {
                                        "id": 1,
                                        "code": "RR001",
                                        "name": "Senior Backend Developer"
                                    },
                                    "num_candidates_participated": 5,
                                    "total_cost": "25000.00",
                                    "num_candidates_hired": 2,
                                    "avg_cost": "12500.00",
                                    "referee": {
                                        "id": 10,
                                        "code": "EMP010",
                                        "fullname": "Nguyen Van A",
                                        "email": "nguyenvana@example.com"
                                    },
                                    "referrer": {
                                        "id": 15,
                                        "code": "EMP015",
                                        "fullname": "Tran Thi B",
                                        "email": "tranthib@example.com"
                                    },
                                    "activity": "Referred qualified candidates from professional network",
                                    "note": "High quality referrals",
                                    "created_at": "2025-10-16T03:00:00Z",
                                    "updated_at": "2025-10-16T03:00:00Z"
                                },
                                {
                                    "id": 2,
                                    "date": "2025-10-20",
                                    "recruitment_source": {
                                        "id": 1,
                                        "code": "REFERRAL",
                                        "name": "Employee Referral",
                                        "allow_referral": True
                                    },
                                    "total_cost": "15000.00",
                                    "num_candidates_hired": 1,
                                    "avg_cost": "15000.00",
                                    "referee": {
                                        "id": 12,
                                        "code": "EMP012",
                                        "fullname": "Le Van C",
                                        "email": "levanc@example.com"
                                    },
                                    "referrer": {
                                        "id": 18,
                                        "code": "EMP018",
                                        "fullname": "Pham Thi D",
                                        "email": "phamthid@example.com"
                                    },
                                    "activity": "Referred former colleague",
                                    "note": "Experienced developer"
                                }
                            ]
                        },
                        {
                            "name": "HR Department",
                            "items": [
                                {
                                    "id": 3,
                                    "date": "2025-10-18",
                                    "recruitment_source": {
                                        "id": 1,
                                        "code": "REFERRAL",
                                        "name": "Employee Referral",
                                        "allow_referral": True
                                    },
                                    "total_cost": "10000.00",
                                    "num_candidates_hired": 1,
                                    "avg_cost": "10000.00",
                                    "referee": {
                                        "id": 20,
                                        "code": "EMP020",
                                        "fullname": "Hoang Van E",
                                        "email": "hoangvane@example.com"
                                    },
                                    "referrer": {
                                        "id": 22,
                                        "code": "EMP022",
                                        "fullname": "Do Thi F",
                                        "email": "dothif@example.com"
                                    },
                                    "activity": "Referred candidate from university network",
                                    "note": "Recent graduate with potential"
                                }
                            ]
                        }
                    ],
                    "summary_total": "50000"
                },
                "error": None
            },
            response_only=True,
        ),
        OpenApiExample(
            "Success - Empty Result",
            value={
                "success": True,
                "data": {
                    "data": [],
                    "summary_total": "0"
                },
                "error": None
            },
            response_only=True,
        ),
        OpenApiExample(
            "Error - Invalid Month Format",
            value={
                "success": False,
                "data": None,
                "error": {
                    "month": ["Invalid month format. Use MM/YYYY."]
                }
            },
            response_only=True,
            status_codes=["400"],
        ),
    ],
)
@action(detail=False, methods=["get"], url_path="referral-cost")
def referral_cost(self, request):
    # ... existing implementation
```

---

## 7. Dashboard Realtime KPIs (`/api/hrm/dashboard/realtime/`)

**File**: `apps/hrm/api/views/recruitment_dashboard.py`

```python
@extend_schema(
    summary="Realtime Dashboard KPIs",
    description="Get real-time recruitment KPIs: open positions, applicants today, hires today, interviews today.",
    responses={200: DashboardRealtimeDataSerializer},
    examples=[
        OpenApiExample(
            "Success - Realtime KPIs",
            value={
                "success": True,
                "data": {
                    "open_positions": 15,
                    "applicants_today": 8,
                    "hires_today": 3,
                    "interviews_today": 12
                },
                "error": None
            },
            response_only=True,
        ),
        OpenApiExample(
            "Success - No Activity Today",
            value={
                "success": True,
                "data": {
                    "open_positions": 10,
                    "applicants_today": 0,
                    "hires_today": 0,
                    "interviews_today": 0
                },
                "error": None
            },
            response_only=True,
        ),
    ],
)
@action(detail=False, methods=["get"])
def realtime(self, request):
    # ... existing implementation
```

---

## 8. Dashboard Chart Data (`/api/hrm/dashboard/charts/`)

```python
@extend_schema(
    summary="Dashboard Chart Data",
    description="Get aggregated data for dashboard charts.",
    parameters=[DashboardChartFilterSerializer],
    responses={200: DashboardChartDataSerializer},
    examples=[
        OpenApiExample(
            "Success - Complete Chart Data",
            value={
                "success": True,
                "data": {
                    "experience_breakdown": [
                        {
                            "label": "Experienced",
                            "count": 45,
                            "percentage": 75.0
                        },
                        {
                            "label": "Inexperienced",
                            "count": 15,
                            "percentage": 25.0
                        }
                    ],
                    "branch_breakdown": [
                        {
                            "branch_name": "Hanoi Branch",
                            "count": 35,
                            "percentage": 58.3
                        },
                        {
                            "branch_name": "HCMC Branch",
                            "count": 20,
                            "percentage": 33.3
                        },
                        {
                            "branch_name": "Da Nang Branch",
                            "count": 5,
                            "percentage": 8.3
                        }
                    ],
                    "cost_breakdown": [
                        {
                            "source_type": "marketing_channel",
                            "total_cost": "250000.00",
                            "percentage": 50.0
                        },
                        {
                            "source_type": "job_website_channel",
                            "total_cost": "180000.00",
                            "percentage": 36.0
                        },
                        {
                            "source_type": "referral_source",
                            "total_cost": "70000.00",
                            "percentage": 14.0
                        }
                    ],
                    "source_type_breakdown": [
                        {
                            "source_type": "marketing_channel",
                            "count": 25,
                            "percentage": 41.7
                        },
                        {
                            "source_type": "job_website_channel",
                            "count": 20,
                            "percentage": 33.3
                        },
                        {
                            "source_type": "referral_source",
                            "count": 10,
                            "percentage": 16.7
                        },
                        {
                            "source_type": "recruitment_department_source",
                            "count": 3,
                            "percentage": 5.0
                        },
                        {
                            "source_type": "returning_employee",
                            "count": 2,
                            "percentage": 3.3
                        }
                    ],
                    "monthly_trends": [
                        {
                            "month": "05/2025",
                            "referral_source": 5,
                            "marketing_channel": 12,
                            "job_website_channel": 10,
                            "recruitment_department_source": 2,
                            "returning_employee": 1
                        },
                        {
                            "month": "06/2025",
                            "referral_source": 6,
                            "marketing_channel": 15,
                            "job_website_channel": 12,
                            "recruitment_department_source": 3,
                            "returning_employee": 2
                        },
                        {
                            "month": "07/2025",
                            "referral_source": 8,
                            "marketing_channel": 18,
                            "job_website_channel": 14,
                            "recruitment_department_source": 4,
                            "returning_employee": 1
                        },
                        {
                            "month": "08/2025",
                            "referral_source": 7,
                            "marketing_channel": 20,
                            "job_website_channel": 15,
                            "recruitment_department_source": 3,
                            "returning_employee": 2
                        },
                        {
                            "month": "09/2025",
                            "referral_source": 9,
                            "marketing_channel": 22,
                            "job_website_channel": 18,
                            "recruitment_department_source": 5,
                            "returning_employee": 3
                        },
                        {
                            "month": "10/2025",
                            "referral_source": 10,
                            "marketing_channel": 25,
                            "job_website_channel": 20,
                            "recruitment_department_source": 3,
                            "returning_employee": 2
                        }
                    ]
                },
                "error": None
            },
            response_only=True,
        ),
        OpenApiExample(
            "Success - Custom Date Range",
            value={
                "success": True,
                "data": {
                    "experience_breakdown": [
                        {
                            "label": "Experienced",
                            "count": 20,
                            "percentage": 66.7
                        },
                        {
                            "label": "Inexperienced",
                            "count": 10,
                            "percentage": 33.3
                        }
                    ],
                    "branch_breakdown": [
                        {
                            "branch_name": "Hanoi Branch",
                            "count": 18,
                            "percentage": 60.0
                        },
                        {
                            "branch_name": "HCMC Branch",
                            "count": 12,
                            "percentage": 40.0
                        }
                    ],
                    "cost_breakdown": [
                        {
                            "source_type": "marketing_channel",
                            "total_cost": "100000.00",
                            "percentage": 50.0
                        },
                        {
                            "source_type": "job_website_channel",
                            "total_cost": "80000.00",
                            "percentage": 40.0
                        },
                        {
                            "source_type": "referral_source",
                            "total_cost": "20000.00",
                            "percentage": 10.0
                        }
                    ],
                    "source_type_breakdown": [
                        {
                            "source_type": "marketing_channel",
                            "count": 15,
                            "percentage": 50.0
                        },
                        {
                            "source_type": "job_website_channel",
                            "count": 10,
                            "percentage": 33.3
                        },
                        {
                            "source_type": "referral_source",
                            "count": 5,
                            "percentage": 16.7
                        }
                    ],
                    "monthly_trends": [
                        {
                            "month": "09/2025",
                            "referral_source": 3,
                            "marketing_channel": 8,
                            "job_website_channel": 6,
                            "recruitment_department_source": 2,
                            "returning_employee": 1
                        },
                        {
                            "month": "10/2025",
                            "referral_source": 2,
                            "marketing_channel": 7,
                            "job_website_channel": 4,
                            "recruitment_department_source": 1,
                            "returning_employee": 1
                        }
                    ]
                },
                "error": None
            },
            response_only=True,
        ),
    ],
)
@action(detail=False, methods=["get"])
def charts(self, request):
    # ... existing implementation
```

---

## Summary

These examples provide:

1. **Success scenarios** with realistic data showing the exact response structure
2. **Different parameter variations** (weekly vs monthly, with/without filters)
3. **Error scenarios** for validation failures
4. **Envelope format** for all responses: `{success, data, error}`
5. **Edge cases** (empty results, single period vs multiple periods)

## Implementation Checklist

- [ ] Add OpenApiExample import to both view files
- [ ] Add examples array to all 6 report endpoints in `recruitment_reports.py`
- [ ] Add examples array to both dashboard endpoints in `recruitment_dashboard.py`
- [ ] Verify all examples use envelope format
- [ ] Test Swagger UI to ensure examples display correctly
- [ ] Run linting to ensure no formatting issues

## Testing the Examples

After adding these examples:

1. Start the development server: `python manage.py runserver`
2. Navigate to the Swagger UI: `http://localhost:8000/api/schema/swagger-ui/`
3. Find each endpoint and verify:
   - Examples appear in the dropdown
   - Response structure matches the serializer
   - Envelope format is correct (`{success, data, error}`)
4. Test the "Try it out" feature with the example parameters
