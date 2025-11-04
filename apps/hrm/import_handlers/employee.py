"""Import handlers for HRM module."""

import logging
import re
from datetime import date, datetime
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify

from apps.core.models import AdministrativeUnit, Nationality, Province
from apps.hrm.models import (
    Bank,
    BankAccount,
    Block,
    Branch,
    ContractType,
    Department,
    Employee,
    Position,
)

logger = logging.getLogger(__name__)

User = get_user_model()

# Constants for import mapping
COLUMN_MAPPING = {
    "stt": "row_number",
    "mã nhân viên": "code",
    "tên": "fullname",
    "mã mcc": "attendance_code",
    "tình trạng": "status",
    "ngày bắt đầu làm việc": "start_day",
    "tháng bắt đầu làm việc": "start_month",
    "năm bắt đầu làm việc": "start_year",
    "loại nhân viên": "contract_type",
    "chức vụ": "position",
    "chi nhánh": "branch",
    "khối": "block",
    "phòng ban": "department",
    "điện thoại": "phone",
    "email cá nhân": "personal_email",
    "email": "email",
    "số tài khoản vpbank": "vpbank_account",
    "số tài khoản vietcombank": "vietcombank_account",
    "mã số thuế": "tax_code",
    "liên lạc khẩn cấp": "emergency_contact",
    "giới tính": "gender",
    "ngày sinh": "date_of_birth",
    "nơi sinh": "place_of_birth",
    "nguyên quán": "origin_place",
    "hôn nhân": "marital_status",
    "dân tộc": "ethnicity",
    "tôn giáo": "religion",
    "quốc tịch": "nationality",
    "số passport": "passport",
    "số cmnd": "citizen_id",
    "ngày cấp": "citizen_id_issued_date",
    "nơi cấp": "citizen_id_issued_place",
    "địa chỉ cư trú": "residential_address",
    "địa chỉ thường trú": "permanent_address",
    "tài khoản đăng nhập": "username",
    "ghi chú": "note",
}

# Gender mapping - only "Nam" or "Nữ"
GENDER_MAPPING = {
    "nam": Employee.Gender.MALE,
    "nữ": Employee.Gender.FEMALE,
}

# Status code mapping - W = Working (Active), C = Ceased (Resigned)
STATUS_CODE_MAPPING = {
    "w": Employee.Status.ACTIVE,
    "c": Employee.Status.RESIGNED,
}

# Contract types that should set specific employee status
CONTRACT_TYPE_STATUS_MAPPING = {
    "nghỉ không lương": Employee.Status.UNPAID_LEAVE,
    "nghỉ thai sản": Employee.Status.MATERNITY_LEAVE,
}

# Marital status mapping - only 3 statuses
MARITAL_STATUS_MAPPING = {
    "độc thân": Employee.MaritalStatus.SINGLE,
    "đã kết hôn": Employee.MaritalStatus.MARRIED,
    "đã ly hôn": Employee.MaritalStatus.DIVORCED,
}


def normalize_header(header: str) -> str:
    """Normalize header name by stripping and lowercasing."""
    if not header:
        return ""
    return str(header).strip().lower()


def normalize_value(value: Any) -> str:
    """Normalize cell value by converting to string and stripping."""
    if value is None:
        return ""
    return str(value).strip()


def is_section_header_row(row: list, first_col_value: str) -> bool:
    """
    Check if row is a section header (e.g., 'Chi nhánh: Bắc Giang').
    
    Section headers typically have text in first column but missing required fields.
    """
    if not first_col_value:
        return False
    
    # Check for common section header patterns
    # More specific patterns with delimiters to avoid false positives
    section_patterns = [
        r"chi\s*nhánh\s*:",
        r"khối\s*:",
        r"phòng\s*ban\s*:",
        r"phòng\s+[a-zA-Z0-9\s_]+_",  # Department names with underscore suffix
    ]
    
    first_col_lower = first_col_value.lower()
    for pattern in section_patterns:
        if re.search(pattern, first_col_lower, re.IGNORECASE):
            return True
    
    return False


def parse_date(value: Any, formats: list = None) -> date | None:
    """
    Parse date from various formats.
    
    Args:
        value: Date value (string or datetime)
        formats: List of date formats to try
        
    Returns:
        date object or None
    """
    if not value:
        return None
    
    # If already a date object
    if isinstance(value, date):
        return value
    
    # If datetime object
    if isinstance(value, datetime):
        return value.date()
    
    # Try parsing string
    value_str = str(value).strip()
    if not value_str or value_str == "-":
        return None
    
    if not formats:
        formats = [
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d.%m.%Y",
        ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(value_str, fmt)
            return parsed.date()
        except (ValueError, TypeError):
            continue
    
    return None


def combine_start_date(day: Any, month: Any, year: Any) -> tuple[date | None, list[str]]:
    """
    Combine day, month, year into a date.
    
    Args:
        day: Day value
        month: Month value
        year: Year value
        
    Returns:
        Tuple of (date, warnings)
    """
    warnings = []
    
    # Try to parse as integers
    try:
        year_int = int(year) if year else None
        month_int = int(month) if month else None
        day_int = int(day) if day else None
    except (ValueError, TypeError):
        warnings.append("Invalid start date components")
        return None, warnings
    
    if not year_int or not month_int:
        warnings.append("Missing year or month for start date")
        return None, warnings
    
    # If day is missing, use first day of month
    if not day_int:
        day_int = 1
        warnings.append("Start day missing, using first day of month")
    
    try:
        start_date = date(year_int, month_int, day_int)
        return start_date, warnings
    except ValueError as e:
        warnings.append(f"Invalid date: {e}")
        return None, warnings


def strip_non_digits(value: Any) -> str:
    """Strip all non-digit characters from value."""
    if not value:
        return ""
    return re.sub(r"\D", "", str(value))


def generate_username(code: str, fullname: str, existing_usernames: set) -> str:
    """
    Generate unique username from code or fullname.
    
    Args:
        code: Employee code
        fullname: Employee fullname
        existing_usernames: Set of existing usernames to avoid conflicts
        
    Returns:
        Unique username
    """
    if code:
        base_username = code.lower().strip()
    else:
        base_username = slugify(fullname).replace("-", "")
    
    username = base_username
    counter = 1
    while username in existing_usernames or User.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1
    
    existing_usernames.add(username)
    return username


def generate_email(username: str, existing_emails: set) -> str:
    """
    Generate unique email from username.
    
    Args:
        username: Username
        existing_emails: Set of existing emails to avoid conflicts
        
    Returns:
        Unique email
    """
    base_email = f"{username}@no-reply.maivietland"
    email = base_email
    counter = 1
    
    while email in existing_emails or User.objects.filter(email=email).exists():
        email = f"{username}{counter}@no-reply.maivietland"
        counter += 1
    
    existing_emails.add(email)
    return email


def lookup_or_create_branch(name: str) -> tuple[Branch | None, bool]:
    """
    Lookup or create Branch by name.
    
    Args:
        name: Branch name
        
    Returns:
        Tuple of (Branch instance or None, created flag)
    """
    if not name:
        return None, False
    
    name = name.strip()
    branch = Branch.objects.filter(name__iexact=name).first()
    
    if branch:
        return branch, False
    
    # Try to get a default province (first one, or create a placeholder)
    province = Province.objects.first()
    if not province:
        logger.warning("No Province found for branch creation, skipping")
        return None, False
    
    # Try to get a default administrative unit
    admin_unit = AdministrativeUnit.objects.first()
    if not admin_unit:
        logger.warning("No AdministrativeUnit found for branch creation, skipping")
        return None, False
    
    branch = Branch.objects.create(
        name=name,
        province=province,
        administrative_unit=admin_unit,
    )
    logger.info(f"Created branch: {branch.code} - {branch.name}")
    
    return branch, True


def lookup_or_create_block(name: str, branch: Branch = None) -> tuple[Block | None, bool]:
    """
    Lookup or create Block by name.
    
    Args:
        name: Block name
        branch: Associated branch
        
    Returns:
        Tuple of (Block instance or None, created flag)
    """
    if not name:
        return None, False
    
    name = name.strip()
    
    # Try to find existing block
    if branch:
        block = Block.objects.filter(name__iexact=name, branch=branch).first()
    else:
        block = Block.objects.filter(name__iexact=name).first()
    
    if block:
        return block, False
    
    # Determine block type from name
    block_type = Block.BlockType.BUSINESS
    if "hỗ trợ" in name.lower() or "support" in name.lower():
        block_type = Block.BlockType.SUPPORT
    
    # If no branch, try to get first branch
    if not branch:
        branch = Branch.objects.first()
        if not branch:
            logger.warning("No Branch found for block creation, skipping")
            return None, False
    
    block = Block.objects.create(
        name=name,
        branch=branch,
        block_type=block_type,
    )
    logger.info(f"Created block: {block.code} - {block.name}")
    
    return block, True


def lookup_or_create_department(
    name: str, block: Block = None, branch: Branch = None
) -> tuple[Department | None, bool]:
    """
    Lookup or create Department by name.
    
    Args:
        name: Department name
        block: Associated block
        branch: Associated branch
        
    Returns:
        Tuple of (Department instance or None, created flag)
    """
    if not name:
        return None, False
    
    name = name.strip()
    
    # Try to find existing department
    if block:
        department = Department.objects.filter(name__iexact=name, block=block).first()
    else:
        department = Department.objects.filter(name__iexact=name).first()
    
    if department:
        return department, False
    
    # If no block, try to get first block
    if not block:
        if branch:
            block = Block.objects.filter(branch=branch).first()
        else:
            block = Block.objects.first()
        
        if not block:
            logger.warning("No Block found for department creation, skipping")
            return None, False
    
    # Auto-set branch from block
    if not branch and block:
        branch = block.branch
    
    department = Department.objects.create(
        name=name,
        block=block,
        branch=branch,
    )
    logger.info(f"Created department: {department.code} - {department.name}")
    
    return department, True


def lookup_or_create_position(name: str) -> tuple[Position | None, bool]:
    """
    Lookup or create Position by name.
    
    Args:
        name: Position name
        
    Returns:
        Tuple of (Position instance or None, created flag)
    """
    if not name:
        return None, False
    
    name = name.strip()
    position = Position.objects.filter(name__iexact=name).first()
    
    if position:
        return position, False
    
    position = Position.objects.create(name=name)
    logger.info(f"Created position: {position.code} - {position.name}")
    
    return position, True


def lookup_or_create_contract_type(name: str) -> tuple[ContractType | None, bool]:
    """
    Lookup or create ContractType by name.
    
    Args:
        name: Contract type name
        
    Returns:
        Tuple of (ContractType instance or None, created flag)
    """
    if not name:
        return None, False
    
    name = name.strip()
    contract_type = ContractType.objects.filter(name__iexact=name).first()
    
    if contract_type:
        return contract_type, False
    
    contract_type = ContractType.objects.create(name=name)
    logger.info(f"Created contract type: {contract_type.name}")
    
    return contract_type, True


def lookup_or_create_nationality(name: str) -> tuple[Nationality | None, bool]:
    """
    Lookup or create Nationality by name.
    
    Args:
        name: Nationality name
        
    Returns:
        Tuple of (Nationality instance or None, created flag)
    """
    if not name:
        return None, False
    
    name = name.strip()
    nationality = Nationality.objects.filter(name__iexact=name).first()
    
    if nationality:
        return nationality, False
    
    nationality = Nationality.objects.create(name=name)
    logger.info(f"Created nationality: {nationality.name}")
    
    return nationality, True


def parse_phone(value: Any) -> tuple[str, list[str]]:
    """
    Parse and validate phone number.
    
    Args:
        value: Phone number value
        
    Returns:
        Tuple of (cleaned_phone, warnings)
    """
    warnings = []
    if not value:
        return "", warnings
    
    # Strip non-digits
    phone = strip_non_digits(value)
    
    # Check if exactly 10 digits
    if phone and len(phone) != 10:
        warnings.append(f"Phone number must be exactly 10 digits, got {len(phone)}")
        return "", warnings
    
    return phone, warnings


def lookup_or_create_bank(code: str, name: str) -> tuple[Bank | None, bool]:
    """
    Lookup or create Bank by code.
    
    Args:
        code: Bank code
        name: Bank name
        
    Returns:
        Tuple of (Bank instance or None, created flag)
    """
    if not code or not name:
        return None, False
    
    bank = Bank.objects.filter(code=code).first()
    
    if bank:
        return bank, False
    
    bank = Bank.objects.create(code=code, name=name)
    logger.info(f"Created bank: {bank.code} - {bank.name}")
    
    return bank, True


def ensure_default_banks() -> dict[str, Bank]:
    """
    Ensure default banks exist (VPBank and Vietcombank).
    
    Returns:
        dict: Dictionary with 'vpbank' and 'vietcombank' keys
    """
    vpbank, _ = lookup_or_create_bank(
        "VPBank",
        "Ngân hàng TMCP Việt Nam Thịnh Vượng"
    )
    vietcombank, _ = lookup_or_create_bank(
        "Vietcombank",
        "Ngân hàng TMCP Ngoại thương Việt Nam"
    )
    
    return {
        "vpbank": vpbank,
        "vietcombank": vietcombank,
    }


def pre_import_initialize(import_job_id: str, options: dict) -> None:
    """
    Pre-import initialization callback.
    
    Called once at the start of the import process before processing any rows.
    Use this for one-time setup operations like ensuring default data exists.
    
    Args:
        import_job_id: UUID of the import job
        options: Import options dictionary
    """
    # Ensure default banks exist once at the start
    banks = ensure_default_banks()
    
    # Store bank references in options for reuse across all rows
    options["_vpbank"] = banks["vpbank"]
    options["_vietcombank"] = banks["vietcombank"]
    
    logger.info(f"Import job {import_job_id}: Initialized default banks")


def extract_code_type(code: str) -> str:
    """
    Extract code_type from employee code.
    
    Args:
        code: Employee code like "CTV000000360" or "MV000004693"
        
    Returns:
        str: Code type ("CTV" or "MV"), defaults to "MV"
    """
    if not code:
        return Employee.CodeType.MV
    
    code_upper = code.upper().strip()
    if code_upper.startswith("CTV"):
        return Employee.CodeType.CTV
    elif code_upper.startswith("MV"):
        return Employee.CodeType.MV
    
    # Default to MV if pattern doesn't match
    return Employee.CodeType.MV


def parse_emergency_contact(value: Any) -> tuple[str, str]:
    """
    Parse emergency contact field.
    
    Handles formats like:
    - "0936998985 (Chồng)" -> phone: "0936998985", name: "Chồng"
    - "0968677128 (mẹ)" -> phone: "0968677128", name: "mẹ"
    - "0931996386/ 0829111185 (vợ)" -> phone: "0931996386", name: "vợ" (first phone)
    - "0968677128 mẹ" -> phone: "0968677128", name: "mẹ"
    - "Name - Phone" -> phone: from second part, name: from first part
    
    Args:
        value: Emergency contact value
        
    Returns:
        Tuple of (phone, name)
    """
    if not value:
        return "", ""
    
    value_str = normalize_value(value)
    
    # Pattern 1: "Phone (Name)" or "Phone1/Phone2 (Name)"
    match = re.match(r"^([\d\s/]+)\s*\(([^)]+)\)", value_str)
    if match:
        phone_part = match.group(1).strip()
        name_part = match.group(2).strip()
        # Extract first phone if multiple separated by /
        phones = re.findall(r"\d+", phone_part)
        phone = phones[0] if phones else ""
        return phone, name_part
    
    # Pattern 2: "Phone Name" (phone followed by text without parentheses)
    match = re.match(r"^([\d\s]+)\s+([^\d]+)$", value_str)
    if match:
        phone = strip_non_digits(match.group(1))
        name = match.group(2).strip()
        return phone, name
    
    # Pattern 3: "Name - Phone" (dash separator)
    if "-" in value_str:
        parts = value_str.split("-", 1)
        if len(parts) == 2:
            # Assume first part is name/description, second is phone
            return strip_non_digits(parts[1]), parts[0].strip()
    
    # Otherwise, assume it's just a phone number
    return strip_non_digits(value_str), ""


def import_handler(
    row_index: int, row: list, import_job_id: str, options: dict
) -> dict:
    """
    Import handler for HRM employees.
    
    This handler processes a single row from the employee import file.
    It maps Vietnamese column headers to Employee model fields, validates data,
    creates reference models if needed, and creates/updates employee records.
    
    Args:
        row_index: 1-based row index
        row: List of cell values from the row
        import_job_id: Import job UUID (for logging)
        options: Import options dictionary
        
    Returns:
        dict: Result with format:
            Success: {
                "ok": True,
                "row_index": int,
                "employee_code": str,
                "action": "created" | "updated" | "skipped",
                "warnings": list[str],
                "created_references": dict,
                "pk": int
            }
            Failure: {
                "ok": False,
                "row_index": int,
                "employee_code": str | None,
                "error": str | list[str],
                "action": "skipped"
            }
    """
    errors = []
    warnings = []
    created_references = {}
    
    try:
        # Get headers from options (should be set by worker)
        headers = options.get("headers", [])
        if not headers:
            return {
                "ok": False,
                "row_index": row_index,
                "error": "Headers not provided in options",
                "action": "skipped",
            }
        
        # Map row to dictionary
        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(row):
                normalized_header = normalize_header(header)
                field_name = COLUMN_MAPPING.get(normalized_header, normalized_header)
                row_dict[field_name] = row[i]
        
        # Extract and normalize values
        code = normalize_value(row_dict.get("code", ""))
        fullname = normalize_value(row_dict.get("fullname", ""))
        
        # Check if this is a section header row
        first_col = normalize_value(row[0]) if row else ""
        if is_section_header_row(row, first_col):
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "employee_code": None,
                "warnings": ["Section header row, skipped"],
            }
        
        # Required fields check
        if not code or not fullname:
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "employee_code": code or None,
                "warnings": ["Missing required fields (code or fullname)"],
            }
        
        # Use a single transaction for this row
        with transaction.atomic():
            # Parse and validate fields
            employee_data = {}
            
            # Code and fullname (required)
            employee_data["code"] = code
            employee_data["fullname"] = fullname
            
            # Extract and set code_type from code
            code_type = extract_code_type(code)
            employee_data["code_type"] = code_type
            
            # Attendance code (digits only)
            attendance_code = strip_non_digits(row_dict.get("attendance_code", ""))
            if attendance_code:
                employee_data["attendance_code"] = attendance_code
            
            # Start date (combine day, month, year)
            start_day = row_dict.get("start_day")
            start_month = row_dict.get("start_month")
            start_year = row_dict.get("start_year")
            
            start_date = None
            if start_day or start_month or start_year:
                start_date, date_warnings = combine_start_date(start_day, start_month, start_year)
                warnings.extend(date_warnings)
            
            # If no start_date from components, try parsing start_day as full date
            if not start_date and start_day:
                start_date = parse_date(start_day)
            
            if start_date:
                employee_data["start_date"] = start_date
            
            # Status and Contract type (combined logic)
            # Status code: W = Working (Active), C = Ceased (Resigned)
            status_raw = normalize_value(row_dict.get("status", "")).lower()
            contract_type_name = normalize_value(row_dict.get("contract_type", ""))
            
            # Determine status based on status code and contract type
            status = None
            contract_type_lower = contract_type_name.lower()
            
            # First check if contract type maps to a specific status
            if contract_type_lower in CONTRACT_TYPE_STATUS_MAPPING:
                status = CONTRACT_TYPE_STATUS_MAPPING[contract_type_lower]
            # Otherwise use status code mapping
            elif status_raw in STATUS_CODE_MAPPING:
                status = STATUS_CODE_MAPPING[status_raw]
            
            if status:
                employee_data["status"] = status
                # If status is RESIGNED, set resignation_date to today to pass validation
                if status == Employee.Status.RESIGNED:
                    employee_data["resignation_date"] = date.today()
            elif status_raw:
                warnings.append(f"Unknown status code: {status_raw}")
            
            # Create contract type if provided (except for special status ones)
            if contract_type_name and contract_type_lower not in CONTRACT_TYPE_STATUS_MAPPING:
                contract_type, created = lookup_or_create_contract_type(contract_type_name)
                if contract_type:
                    employee_data["contract_type"] = contract_type
                    if created:
                        created_references["contract_type"] = {
                            "id": contract_type.id,
                            "name": contract_type.name,
                        }
            
            # Branch (reference)
            branch_name = normalize_value(row_dict.get("branch", ""))
            branch = None
            if branch_name:
                branch, created = lookup_or_create_branch(branch_name)
                if branch:
                    if created:
                        created_references["branch"] = {
                            "id": branch.id,
                            "name": branch.name,
                        }
            
            # Block (reference)
            block_name = normalize_value(row_dict.get("block", ""))
            block = None
            if block_name:
                block, created = lookup_or_create_block(block_name, branch)
                if block:
                    if created:
                        created_references["block"] = {
                            "id": block.id,
                            "name": block.name,
                        }
                    # Update branch if not set
                    if not branch:
                        branch = block.branch
            
            # Department (reference, required)
            department_name = normalize_value(row_dict.get("department", ""))
            department = None
            if department_name:
                department, created = lookup_or_create_department(department_name, block, branch)
                if department:
                    employee_data["department"] = department
                    if created:
                        created_references["department"] = {
                            "id": department.id,
                            "name": department.name,
                        }
                    # Update branch and block from department
                    if not branch:
                        branch = department.branch
                    if not block:
                        block = department.block
            
            # Position (reference)
            position_name = normalize_value(row_dict.get("position", ""))
            if position_name:
                position, created = lookup_or_create_position(position_name)
                if position:
                    employee_data["position"] = position
                    if created:
                        created_references["position"] = {
                            "id": position.id,
                            "name": position.name,
                        }
            
            # Phone
            phone_raw = row_dict.get("phone", "")
            phone, phone_warnings = parse_phone(phone_raw)
            if phone:
                employee_data["phone"] = phone
            warnings.extend(phone_warnings)
            
            # Personal email
            personal_email = normalize_value(row_dict.get("personal_email", ""))
            if personal_email:
                employee_data["personal_email"] = personal_email
            
            # Email (required, generate if missing)
            email = normalize_value(row_dict.get("email", ""))
            username = normalize_value(row_dict.get("username", ""))
            
            # Get or initialize existing usernames/emails set from options
            # This maintains uniqueness across all rows in the import job
            existing_usernames = options.get("_existing_usernames", set())
            existing_emails = options.get("_existing_emails", set())
            
            # Generate username if missing
            if not username:
                username = generate_username(code, fullname, existing_usernames)
                warnings.append(f"Generated username: {username}")
            else:
                existing_usernames.add(username)
            
            employee_data["username"] = username
            
            # Generate email if missing
            if not email:
                email = generate_email(username, existing_emails)
                warnings.append(f"Generated email: {email}")
            else:
                existing_emails.add(email)
            
            employee_data["email"] = email
            
            # Tax code
            tax_code = normalize_value(row_dict.get("tax_code", ""))
            if tax_code:
                employee_data["tax_code"] = tax_code
            
            # Emergency contact
            emergency_contact_raw = row_dict.get("emergency_contact", "")
            if emergency_contact_raw:
                emergency_phone, emergency_name = parse_emergency_contact(emergency_contact_raw)
                if emergency_phone:
                    employee_data["emergency_contact_phone"] = emergency_phone
                if emergency_name:
                    employee_data["emergency_contact_name"] = emergency_name
            
            # Gender
            gender_raw = normalize_value(row_dict.get("gender", "")).lower()
            if gender_raw:
                gender = GENDER_MAPPING.get(gender_raw)
                if gender:
                    employee_data["gender"] = gender
                else:
                    warnings.append(f"Unknown gender: {gender_raw}")
            
            # Date of birth
            dob_raw = row_dict.get("date_of_birth", "")
            dob = parse_date(dob_raw)
            if dob:
                employee_data["date_of_birth"] = dob
            
            # Place of birth
            place_of_birth = normalize_value(row_dict.get("place_of_birth", ""))
            if place_of_birth:
                employee_data["place_of_birth"] = place_of_birth
            
            # Marital status
            marital_status_raw = normalize_value(row_dict.get("marital_status", "")).lower()
            if marital_status_raw:
                marital_status = MARITAL_STATUS_MAPPING.get(marital_status_raw)
                if marital_status:
                    employee_data["marital_status"] = marital_status
                else:
                    warnings.append(f"Unknown marital status: {marital_status_raw}")
            
            # Ethnicity
            ethnicity = normalize_value(row_dict.get("ethnicity", ""))
            if ethnicity:
                employee_data["ethnicity"] = ethnicity
            
            # Religion
            religion = normalize_value(row_dict.get("religion", ""))
            if religion:
                employee_data["religion"] = religion
            
            # Nationality (reference)
            nationality_name = normalize_value(row_dict.get("nationality", ""))
            if nationality_name:
                nationality, created = lookup_or_create_nationality(nationality_name)
                if nationality:
                    employee_data["nationality"] = nationality
                    if created:
                        created_references["nationality"] = {
                            "id": nationality.id,
                            "name": nationality.name,
                        }
            
            # Citizen ID (digits only)
            citizen_id = strip_non_digits(row_dict.get("citizen_id", ""))
            if citizen_id:
                employee_data["citizen_id"] = citizen_id
            
            # Citizen ID issued date
            citizen_id_issued_date_raw = row_dict.get("citizen_id_issued_date", "")
            citizen_id_issued_date = parse_date(citizen_id_issued_date_raw)
            if citizen_id_issued_date:
                employee_data["citizen_id_issued_date"] = citizen_id_issued_date
            
            # Citizen ID issued place
            citizen_id_issued_place = normalize_value(row_dict.get("citizen_id_issued_place", ""))
            if citizen_id_issued_place:
                employee_data["citizen_id_issued_place"] = citizen_id_issued_place
            
            # Residential address
            residential_address = normalize_value(row_dict.get("residential_address", ""))
            if residential_address:
                employee_data["residential_address"] = residential_address
            
            # Permanent address
            permanent_address = normalize_value(row_dict.get("permanent_address", ""))
            if permanent_address:
                employee_data["permanent_address"] = permanent_address
            
            # Note
            note = normalize_value(row_dict.get("note", ""))
            if note:
                employee_data["note"] = note
            
            # Update or create employee
            try:
                employee, created = Employee.objects.update_or_create(
                    code=code,
                    defaults=employee_data,
                )
                
                action = "created" if created else "updated"
                
                # Handle bank accounts
                vpbank_account = normalize_value(row_dict.get("vpbank_account", ""))
                vietcombank_account = normalize_value(row_dict.get("vietcombank_account", ""))
                
                if vpbank_account or vietcombank_account:
                    # Get pre-initialized banks from options (created once at import start)
                    vpbank = options.get("_vpbank")
                    vietcombank = options.get("_vietcombank")
                    
                    # Create VPBank account if provided
                    if vpbank_account and vpbank:
                        BankAccount.objects.update_or_create(
                            employee=employee,
                            bank=vpbank,
                            defaults={
                                "account_number": vpbank_account,
                                "account_name": employee.fullname,
                                "is_primary": not vietcombank_account,  # Primary if only one
                            }
                        )
                    
                    # Create Vietcombank account if provided
                    if vietcombank_account and vietcombank:
                        BankAccount.objects.update_or_create(
                            employee=employee,
                            bank=vietcombank,
                            defaults={
                                "account_number": vietcombank_account,
                                "account_name": employee.fullname,
                                "is_primary": not vpbank_account,  # Primary if only one
                            }
                        )
                
                # OrganizationChart is now handled automatically in Employee.save()
                # when position changes, so no need to manage it here
                
                return {
                    "ok": True,
                    "row_index": row_index,
                    "employee_code": code,
                    "action": action,
                    "warnings": warnings,
                    "created_references": created_references,
                    "pk": employee.pk,
                }
                
            except Exception as e:
                logger.error(f"Failed to save employee {code}: {e}")
                return {
                    "ok": False,
                    "row_index": row_index,
                    "employee_code": code,
                    "error": str(e),
                    "action": "skipped",
                }
    
    except Exception as e:
        logger.exception(f"Import handler error at row {row_index}: {e}")
        return {
            "ok": False,
            "row_index": row_index,
            "employee_code": None,
            "error": str(e),
            "action": "skipped",
        }
