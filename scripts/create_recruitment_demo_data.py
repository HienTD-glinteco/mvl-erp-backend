"""
Demo data generator for recruitment reports and dashboard.

This script creates realistic demo data for:
- Organizational structure (branches, blocks, departments)
- Recruitment sources and channels
- Employees (for referrals)
- Report data (staff growth, recruitment source/channel, cost, hired candidates)
- Dashboard real-time data (job descriptions, recruitment requests, candidates, interviews)

Usage:
    poetry run python manage.py shell < scripts/create_recruitment_demo_data.py

Or in Django shell:
    exec(open('scripts/create_recruitment_demo_data.py').read())
"""

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.models import AdministrativeUnit, Province
from apps.hrm.constants import RecruitmentSourceType
from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    HiredCandidateReport,
    InterviewSchedule,
    JobDescription,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentExpense,
    RecruitmentRequest,
    RecruitmentSource,
    RecruitmentSourceReport,
    StaffGrowthReport,
)


def clear_existing_data():
    """Clear existing demo data (optional - use with caution)."""
    print("Clearing existing report data...")
    StaffGrowthReport.objects.all().delete()
    RecruitmentSourceReport.objects.all().delete()
    RecruitmentChannelReport.objects.all().delete()
    RecruitmentCostReport.objects.all().delete()
    HiredCandidateReport.objects.all().delete()
    RecruitmentExpense.objects.filter(recruitment_source__allow_referral=True).delete()
    print("Existing report data cleared.")


def create_provinces_and_administrative_units():
    """Create provinces and administrative units for branches."""
    print("Creating provinces and administrative units...")

    provinces_data = [
        {"name": "Ha Noi", "code": "HN", "level": Province.ProvinceLevel.CENTRAL_CITY},
        {"name": "Ho Chi Minh", "code": "HCM", "level": Province.ProvinceLevel.CENTRAL_CITY},
        {"name": "Da Nang", "code": "DN", "level": Province.ProvinceLevel.CENTRAL_CITY},
    ]

    provinces = {}
    for prov_data in provinces_data:
        province, created = Province.objects.get_or_create(
            code=prov_data["code"],
            enabled=True,
            defaults={
                "name": prov_data["name"],
                "english_name": prov_data["name"],
                "level": prov_data["level"],
                "enabled": True,
            },
        )
        provinces[prov_data["code"]] = province
        if created:
            print(f"  Created province: {province.name}")

    # Create administrative units for each province
    admin_units_data = [
        {
            "province_code": "HN",
            "name": "Ba Dinh District",
            "code": "HN_BD",
            "level": AdministrativeUnit.UnitLevel.DISTRICT,
        },
        {
            "province_code": "HCM",
            "name": "District 1",
            "code": "HCM_D1",
            "level": AdministrativeUnit.UnitLevel.DISTRICT,
        },
        {
            "province_code": "DN",
            "name": "Hai Chau District",
            "code": "DN_HC",
            "level": AdministrativeUnit.UnitLevel.DISTRICT,
        },
    ]

    admin_units = {}
    for unit_data in admin_units_data:
        province = provinces[unit_data["province_code"]]
        admin_unit, created = AdministrativeUnit.objects.get_or_create(
            code=unit_data["code"],
            enabled=True,
            defaults={
                "name": unit_data["name"],
                "english_name": unit_data["name"],
                "parent_province": province,
                "level": unit_data["level"],
                "enabled": True,
            },
        )
        admin_units[unit_data["code"]] = admin_unit
        if created:
            print(f"  Created administrative unit: {admin_unit.name}")

    print(f"Created {len(provinces)} provinces and {len(admin_units)} administrative units")
    return provinces, admin_units


def create_organizational_structure(provinces, admin_units):
    """Create branches, blocks, and departments."""
    print("Creating organizational structure...")

    branches_data = [
        {"name": "Hanoi Branch", "code": "HN", "province_code": "HN", "admin_unit_code": "HN_BD"},
        {"name": "HCMC Branch", "code": "HCM", "province_code": "HCM", "admin_unit_code": "HCM_D1"},
        {"name": "Da Nang Branch", "code": "DN", "province_code": "DN", "admin_unit_code": "DN_HC"},
    ]

    branches = []
    for branch_data in branches_data:
        province = provinces[branch_data["province_code"]]
        admin_unit = admin_units[branch_data["admin_unit_code"]]
        branch, created = Branch.objects.get_or_create(
            code=branch_data["code"],
            defaults={
                "name": branch_data["name"],
                "province": province,
                "administrative_unit": admin_unit,
                "is_active": True,
            },
        )
        branches.append(branch)
        if created:
            print(f"  Created branch: {branch.name}")

    blocks_data = [
        {"name": "Business Block", "code": "BUS", "block_type": Block.BlockType.BUSINESS},
        {"name": "Technology Block", "code": "TECH", "block_type": Block.BlockType.BUSINESS},
        {"name": "Support Block", "code": "SUP", "block_type": Block.BlockType.SUPPORT},
    ]

    departments_data = [
        {"name": "Sales Department", "code": "SALES"},
        {"name": "Marketing Department", "code": "MKT"},
        {"name": "IT Department", "code": "IT"},
        {"name": "HR Department", "code": "HR"},
        {"name": "Finance Department", "code": "FIN"},
    ]

    org_structure = []
    for branch in branches:
        for block_data in blocks_data:
            block, created = Block.objects.get_or_create(
                code=f"{branch.code}_{block_data['code']}",
                defaults={
                    "name": f"{block_data['name']} - {branch.name}",
                    "branch": branch,
                    "block_type": block_data["block_type"],
                    "is_active": True,
                },
            )
            if created:
                print(f"  Created block: {block.name}")

            for dept_data in departments_data:
                dept, created = Department.objects.get_or_create(
                    code=f"{block.code}_{dept_data['code']}",
                    defaults={
                        "name": f"{dept_data['name']} - {block.name}",
                        "branch": branch,
                        "block": block,
                        "is_active": True,
                    },
                )
                org_structure.append({"branch": branch, "block": block, "department": dept})
                if created:
                    print(f"  Created department: {dept.name}")

    print(f"Organizational structure created: {len(branches)} branches, {len(org_structure)} departments")
    return org_structure


def create_recruitment_sources_and_channels():
    """Create recruitment sources and channels."""
    print("Creating recruitment sources and channels...")

    sources_data = [
        {"name": "Employee Referral", "code": "EMP_REF", "allow_referral": True},
        {"name": "Internal Recruitment", "code": "INT_REC", "allow_referral": False},
        {"name": "Headhunter", "code": "HEADHUNT", "allow_referral": False},
    ]

    sources = []
    for source_data in sources_data:
        source, created = RecruitmentSource.objects.get_or_create(
            code=source_data["code"],
            defaults={
                "name": source_data["name"],
                "allow_referral": source_data["allow_referral"],
                "description": f"Demo source: {source_data['name']}",
            },
        )
        sources.append(source)
        if created:
            print(f"  Created source: {source.name}")

    channels_data = [
        {"name": "LinkedIn", "code": "LINKEDIN", "belong_to": RecruitmentChannel.BelongTo.JOB_WEBSITE},
        {"name": "VietnamWorks", "code": "VNWORKS", "belong_to": RecruitmentChannel.BelongTo.JOB_WEBSITE},
        {"name": "Facebook Ads", "code": "FB_ADS", "belong_to": RecruitmentChannel.BelongTo.MARKETING},
        {"name": "Google Ads", "code": "GG_ADS", "belong_to": RecruitmentChannel.BelongTo.MARKETING},
        {"name": "Job Fair", "code": "JOB_FAIR", "belong_to": RecruitmentChannel.BelongTo.MARKETING},
    ]

    channels = []
    for channel_data in channels_data:
        channel, created = RecruitmentChannel.objects.get_or_create(
            code=channel_data["code"],
            defaults={
                "name": channel_data["name"],
                "belong_to": channel_data["belong_to"],
                "description": f"Demo channel: {channel_data['name']}",
                "is_active": True,
            },
        )
        channels.append(channel)
        if created:
            print(f"  Created channel: {channel.name}")

    print(f"Created {len(sources)} sources and {len(channels)} channels")
    return sources, channels


def create_demo_employees(org_structure):
    """Create demo employees for referrals."""
    print("Creating demo employees...")

    employees_data = [
        {"fullname": "Nguyen Van A", "code": "EMP001", "email": "nguyenvana@example.com"},
        {"fullname": "Tran Thi B", "code": "EMP002", "email": "tranthib@example.com"},
        {"fullname": "Le Van C", "code": "EMP003", "email": "levanc@example.com"},
        {"fullname": "Pham Thi D", "code": "EMP004", "email": "phamthid@example.com"},
        {"fullname": "Hoang Van E", "code": "EMP005", "email": "hoangvane@example.com"},
    ]

    employees = []
    for i, emp_data in enumerate(employees_data):
        org = org_structure[i % len(org_structure)]
        emp, created = Employee.objects.get_or_create(
            code=emp_data["code"],
            defaults={
                "fullname": emp_data["fullname"],
                "email": emp_data["email"],
                "username": emp_data["code"].lower(),
                "attendance_code": str(1000 + i),
                "branch": org["branch"],
                "block": org["block"],
                "department": org["department"],
                "start_date": date.today() - timedelta(days=365),
                "status": Employee.Status.ACTIVE,
                "date_of_birth": timezone.now(),
                "personal_email": emp_data["email"],
            },
        )
        employees.append(emp)
        if created:
            print(f"  Created employee: {emp.fullname}")

    print(f"Created {len(employees)} employees")
    return employees


def create_staff_growth_reports(org_structure, days=60):
    """Create staff growth reports for the last N days."""
    print(f"Creating staff growth reports for last {days} days...")

    today = date.today()
    reports = []

    for i in range(days):
        report_date = today - timedelta(days=i)
        month_key = report_date.strftime("%m/%Y")
        week_number = report_date.isocalendar()[1]
        week_key = f"Week {week_number} - {report_date.strftime('%m/%Y')}"

        for org in org_structure:
            report, created = StaffGrowthReport.objects.get_or_create(
                report_date=report_date,
                branch=org["branch"],
                block=org["block"],
                department=org["department"],
                month_key=month_key,
                week_key=week_key,
                defaults={
                    "num_introductions": random.randint(0, 5),
                    "num_returns": random.randint(0, 2),
                    "num_recruitment_source": random.randint(0, 8),
                    "num_transfers": random.randint(0, 3),
                    "num_resignations": random.randint(0, 4),
                },
            )
            if created:
                reports.append(report)

    print(f"  Created {len(reports)} staff growth reports")
    return reports


def create_recruitment_source_reports(org_structure, sources, days=60):
    """Create recruitment source reports for the last N days."""
    print(f"Creating recruitment source reports for last {days} days...")

    today = date.today()
    reports = []

    for i in range(days):
        report_date = today - timedelta(days=i)

        for org in org_structure:
            for source in sources:
                report, created = RecruitmentSourceReport.objects.get_or_create(
                    report_date=report_date,
                    branch=org["branch"],
                    block=org["block"],
                    department=org["department"],
                    recruitment_source=source,
                    defaults={
                        "num_hires": random.randint(0, 10),
                    },
                )
                if created:
                    reports.append(report)

    print(f"  Created {len(reports)} recruitment source reports")
    return reports


def create_recruitment_channel_reports(org_structure, channels, days=60):
    """Create recruitment channel reports for the last N days."""
    print(f"Creating recruitment channel reports for last {days} days...")

    today = date.today()
    reports = []

    for i in range(days):
        report_date = today - timedelta(days=i)

        for org in org_structure:
            for channel in channels:
                report, created = RecruitmentChannelReport.objects.get_or_create(
                    report_date=report_date,
                    branch=org["branch"],
                    block=org["block"],
                    department=org["department"],
                    recruitment_channel=channel,
                    defaults={
                        "num_hires": random.randint(0, 8),
                    },
                )
                if created:
                    reports.append(report)

    print(f"  Created {len(reports)} recruitment channel reports")
    return reports


def create_recruitment_cost_reports(org_structure, days=60):
    """Create recruitment cost reports for the last N days."""
    print(f"Creating recruitment cost reports for last {days} days...")

    today = date.today()
    reports = []

    source_types = [
        RecruitmentSourceType.REFERRAL_SOURCE.value,
        RecruitmentSourceType.MARKETING_CHANNEL.value,
        RecruitmentSourceType.JOB_WEBSITE_CHANNEL.value,
        RecruitmentSourceType.RECRUITMENT_DEPARTMENT_SOURCE.value,
        RecruitmentSourceType.RETURNING_EMPLOYEE.value,
    ]

    for i in range(days):
        report_date = today - timedelta(days=i)
        month_key = report_date.strftime("%m/%Y")

        for org in org_structure:
            for source_type in source_types:
                # Skip cost for types that don't have cost
                if source_type in [
                    RecruitmentSourceType.RECRUITMENT_DEPARTMENT_SOURCE.value,
                    RecruitmentSourceType.RETURNING_EMPLOYEE.value,
                ]:
                    total_cost = Decimal("0")
                    num_hires = random.randint(0, 5)
                    avg_cost = Decimal("0")
                else:
                    num_hires = random.randint(0, 10)
                    avg_cost = Decimal(random.randint(300000, 1000000))
                    total_cost = avg_cost * num_hires

                report, created = RecruitmentCostReport.objects.get_or_create(
                    report_date=report_date,
                    branch=org["branch"],
                    block=org["block"],
                    department=org["department"],
                    source_type=source_type,
                    month_key=month_key,
                    defaults={
                        "total_cost": total_cost,
                        "num_hires": num_hires,
                        "avg_cost_per_hire": avg_cost,
                    },
                )
                if created:
                    reports.append(report)

    print(f"  Created {len(reports)} recruitment cost reports")
    return reports


def create_hired_candidate_reports(org_structure, employees, days=60):
    """Create hired candidate reports for the last N days."""
    print(f"Creating hired candidate reports for last {days} days...")

    today = date.today()
    reports = []

    source_types = [
        RecruitmentSourceType.REFERRAL_SOURCE.value,
        RecruitmentSourceType.MARKETING_CHANNEL.value,
        RecruitmentSourceType.JOB_WEBSITE_CHANNEL.value,
        RecruitmentSourceType.RECRUITMENT_DEPARTMENT_SOURCE.value,
        RecruitmentSourceType.RETURNING_EMPLOYEE.value,
    ]

    for i in range(days):
        report_date = today - timedelta(days=i)
        month_key = report_date.strftime("%m/%Y")
        week_number = report_date.isocalendar()[1]
        week_key = f"Week {week_number} - {report_date.strftime('%m/%Y')}"

        for org in org_structure:
            for source_type in source_types:
                # For referral source, create records per employee
                if source_type == RecruitmentSourceType.REFERRAL_SOURCE.value:
                    for employee in random.sample(employees, k=min(3, len(employees))):
                        num_hired = random.randint(0, 5)
                        report, created = HiredCandidateReport.objects.get_or_create(
                            report_date=report_date,
                            branch=org["branch"],
                            block=org["block"],
                            department=org["department"],
                            source_type=source_type,
                            month_key=month_key,
                            week_key=week_key,
                            employee=employee,
                            defaults={
                                "num_candidates_hired": num_hired,
                                "num_experienced": random.randint(0, num_hired),
                            },
                        )
                        if created:
                            reports.append(report)
                else:
                    num_hired = random.randint(0, 10)
                    report, created = HiredCandidateReport.objects.get_or_create(
                        report_date=report_date,
                        branch=org["branch"],
                        block=org["block"],
                        department=org["department"],
                        source_type=source_type,
                        month_key=month_key,
                        week_key=week_key,
                        employee=None,
                        defaults={
                            "num_candidates_hired": num_hired,
                            "num_experienced": random.randint(0, num_hired),
                        },
                    )
                    if created:
                        reports.append(report)

    print(f"  Created {len(reports)} hired candidate reports")
    return reports


def create_referral_expenses(sources, employees, channels=None):
    """Create referral expenses for the current month."""
    print("Creating referral expenses for current month...")

    referral_source = next((s for s in sources if s.allow_referral), None)
    if not referral_source:
        print("  No referral source found, skipping referral expenses")
        return []

    today = date.today()
    expenses = []

    # Get all open recruitment requests for assignment
    open_requests = list(RecruitmentRequest.objects.filter(status=RecruitmentRequest.Status.OPEN))
    if not open_requests:
        # Create a fallback recruitment request if none exist
        print("  No open recruitment requests found, creating a fallback request...")

        # Ensure a JobDescription exists to link to
        job_desc, _ = JobDescription.objects.get_or_create(
            title="Fallback Job Description",
            defaults={
                "position_title": "Fallback Position",
                "responsibility": "Perform fallback duties as required.",
                "requirement": "Basic requirements for the fallback position.",
                "benefit": "Standard company benefits.",
                "proposed_salary": "Competitive",
            },
        )

        fallback_req = RecruitmentRequest.objects.create(
            name="Demo Referral Request",
            department=Department.objects.first(),
            number_of_positions=5,
            status=RecruitmentRequest.Status.OPEN,
            job_description=job_desc,
            proposer=Employee.objects.first(),
            recruitment_type=RecruitmentRequest.RecruitmentType.NEW_HIRE,
            proposed_salary="Competitive",
        )
        open_requests = [fallback_req]

    for _ in range(20):
        expense_date = today - timedelta(days=random.randint(0, 30))
        referrer = random.choice(employees)
        referee = random.choice([e for e in employees if e != referrer])
        # Pick a random channel if available, else None
        channel = random.choice(channels) if channels else None
        recruitment_request = random.choice(open_requests)
        expense = RecruitmentExpense.objects.create(
            recruitment_source=referral_source,
            recruitment_channel=channel,
            recruitment_request=recruitment_request,
            date=expense_date,
            total_cost=Decimal(random.randint(500000, 2000000)),
            referrer=referrer,
            referee=referee,
            num_candidates_participated=1,
            num_candidates_hired=1,
            activity=f"Referral bonus for {referee.fullname}",
            note="Demo referral expense",
        )
        expenses.append(expense)

    print(f"  Created {len(expenses)} referral expenses")
    return expenses


def create_dashboard_realtime_data(org_structure):
    """Create data for dashboard real-time metrics."""
    print("Creating dashboard real-time data...")

    today = datetime.now().date()

    # Create job descriptions (open positions)
    job = None
    job_count = 0
    for org in random.sample(org_structure, k=min(5, len(org_structure))):
        job, created = JobDescription.objects.get_or_create(
            title=f"Software Engineer - {org['department'].name}",
            defaults={
                "position_title": f"Software Engineer - {org['department'].name}",
                "responsibility": "",
                "requirement": "Basic requirements for the fallback position.",
                "benefit": "",
                "proposed_salary": "10000",
            },
        )
        if created:
            job_count += 1

    # Create recruitment requests (open positions)
    req = None
    req_count = 0
    employees = list(Employee.objects.all())
    sources = list(RecruitmentSource.objects.all())
    channels = list(RecruitmentChannel.objects.all())
    for org in random.sample(org_structure, k=min(10, len(org_structure))):
        proposer = random.choice(employees) if employees else None
        req, created = RecruitmentRequest.objects.get_or_create(
            name=f"Hiring Request - {org['department'].name}",
            defaults={
                "job_description": job,
                "branch": org["branch"],
                "block": org["block"],
                "department": org["department"],
                "proposer": proposer,
                "recruitment_type": RecruitmentRequest.RecruitmentType.NEW_HIRE,
                "status": RecruitmentRequest.Status.OPEN,
                "proposed_salary": "Competitive",
            },
        )
        if created:
            req_count += 1

    # Create candidates (applicants today)
    cand_count = 0
    for _ in range(8):
        recruitment_source = random.choice(sources) if sources else None
        recruitment_channel = random.choice(channels) if channels else None
        years_of_experience = random.randint(0, 10)
        referrer = None
        # If the source allows referral, pick a random employee as referrer
        if recruitment_source and getattr(recruitment_source, "allow_referral", False) and employees:
            referrer = random.choice(employees)
        candidate = RecruitmentCandidate.objects.create(
            name=f"Candidate {random.randint(1000, 9999)}",
            citizen_id=str(random.randint(100000000000, 999999999999)),
            email=f"candidate{random.randint(1000, 9999)}@example.com",
            phone=f"0{random.randint(100000000, 999999999)}",
            status=RecruitmentCandidate.Status.CONTACTED,
            recruitment_request=req,
            branch=org["branch"],
            block=org["block"],
            department=org["department"],
            recruitment_source=recruitment_source,
            recruitment_channel=recruitment_channel,
            years_of_experience=years_of_experience,
            submitted_date=timezone.now(),
            referrer=referrer,
        )
        cand_count += 1

    # Create interview schedules (interviews today)
    interview_count = 0
    for _ in range(5):
        interview = InterviewSchedule.objects.create(
            title=f"Interview - {random.randint(1000, 9999)}",
            recruitment_request=req,
            time=timezone.make_aware(
                datetime.combine(today, datetime.min.time()) + timedelta(hours=random.randint(9, 17))
            ),
            location="Office",
        )
        interview_count += 1

    print(f"  Created {job_count} jobs, {req_count} requests, {cand_count} candidates, {interview_count} interviews")


@transaction.atomic
def main():
    """Main function to create all demo data."""
    print("\n" + "=" * 60)
    print("RECRUITMENT DEMO DATA GENERATOR")
    print("=" * 60 + "\n")

    # Uncomment to clear existing data
    # clear_existing_data()

    # Create provinces and administrative units
    provinces, admin_units = create_provinces_and_administrative_units()

    # Create organizational structure
    org_structure = create_organizational_structure(provinces, admin_units)

    # Create recruitment sources and channels
    sources, channels = create_recruitment_sources_and_channels()

    # Create demo employees
    employees = create_demo_employees(org_structure)

    # Create report data (last 60 days)
    create_staff_growth_reports(org_structure, days=60)
    create_recruitment_source_reports(org_structure, sources, days=60)
    create_recruitment_channel_reports(org_structure, channels, days=60)
    create_recruitment_cost_reports(org_structure, days=60)
    create_hired_candidate_reports(org_structure, employees, days=60)

    # Create referral expenses
    create_referral_expenses(sources, employees, channels)

    # Create dashboard real-time data
    create_dashboard_realtime_data(org_structure)

    print("\n" + "=" * 60)
    print("DEMO DATA CREATION COMPLETED SUCCESSFULLY!")
    print("=" * 60 + "\n")

    print("Summary:")
    print(f"  - Provinces: {Province.objects.count()}")
    print(f"  - Administrative Units: {AdministrativeUnit.objects.count()}")
    print(f"  - Branches: {Branch.objects.count()}")
    print(f"  - Blocks: {Block.objects.count()}")
    print(f"  - Departments: {Department.objects.count()}")
    print(f"  - Employees: {Employee.objects.count()}")
    print(f"  - Recruitment Sources: {RecruitmentSource.objects.count()}")
    print(f"  - Recruitment Channels: {RecruitmentChannel.objects.count()}")
    print(f"  - Staff Growth Reports: {StaffGrowthReport.objects.count()}")
    print(f"  - Recruitment Source Reports: {RecruitmentSourceReport.objects.count()}")
    print(f"  - Recruitment Channel Reports: {RecruitmentChannelReport.objects.count()}")
    print(f"  - Recruitment Cost Reports: {RecruitmentCostReport.objects.count()}")
    print(f"  - Hired Candidate Reports: {HiredCandidateReport.objects.count()}")
    print(
        f"  - Referral Expenses: {RecruitmentExpense.objects.filter(recruitment_source__allow_referral=True).count()}"
    )
    print(f"  - Job Descriptions: {JobDescription.objects.count()}")
    print(f"  - Recruitment Requests: {RecruitmentRequest.objects.count()}")
    print(f"  - Recruitment Candidates: {RecruitmentCandidate.objects.count()}")
    print(f"  - Interview Schedules: {InterviewSchedule.objects.count()}")
    print("\nYou can now test the recruitment reports and dashboard APIs!")


if __name__ == "__main__":
    main()
