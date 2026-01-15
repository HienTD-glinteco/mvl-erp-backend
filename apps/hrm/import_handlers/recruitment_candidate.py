"""Import handler for Recruitment Candidates."""

import logging
import re
from datetime import date, datetime
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from apps.hrm.models import (
    Block,
    Branch,
    Department,
    Employee,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentRequest,
    RecruitmentSource,
)
from libs.strings import normalize_header

logger = logging.getLogger(__name__)

# Column mapping for import template (Vietnamese headers to field names)
COLUMN_MAPPING = {
    "số thứ tự": "row_number",
    "họ và tên": "name",
    "cmnd/cccd": "citizen_id",
    "email": "email",
    "số điện thoại": "phone",
    "tên yêu cầu tuyển dụng": "recruitment_request_name",
    "tên nguồn tuyển dụng": "recruitment_source_name",
    "tên kênh tuyển dụng": "recruitment_channel_name",
    "tên phòng ban": "department_name",
    "tên khối": "block_name",
    "tên chi nhánh": "branch_name",
    "mã nhân viên giới thiệu": "referrer_code",
    "số tháng kinh nghiệm": "months_experience",
    "ngày nộp hồ sơ": "submitted_date",
    "trạng thái": "status_code",
    "ngày onboard": "onboard_date",
    "ghi chú": "note",
}

# Status code mapping (1-7 to Status enum)
STATUS_CODE_MAPPING = {
    1: RecruitmentCandidate.Status.CONTACTED,
    2: RecruitmentCandidate.Status.INTERVIEW_SCHEDULED_1,
    3: RecruitmentCandidate.Status.INTERVIEWED_1,
    4: RecruitmentCandidate.Status.INTERVIEW_SCHEDULED_2,
    5: RecruitmentCandidate.Status.INTERVIEWED_2,
    6: RecruitmentCandidate.Status.HIRED,
    7: RecruitmentCandidate.Status.REJECTED,
}


def normalize_value(value: Any) -> str:
    """Normalize cell value by converting to string and stripping."""
    if value is None:
        return ""
    return str(value).strip()


def normalize_text(text: Any) -> str:
    """
    Normalize text for consistent lookups.

    - Strips leading/trailing whitespace
    - Converts to lowercase
    - Removes extra internal spaces (multiple spaces → single space)
    - Returns empty string if input is None or whitespace-only

    Args:
        text: Input string to normalize

    Returns:
        Normalized string

    Example:
        >>> normalize_text("  Phòng IT  ")
        "phòng it"
        >>> normalize_text("CHI  NHÁNH   HÀ NỘI")
        "chi nhánh hà nội"
    """
    if not text:
        return ""
    # Strip, lowercase, and replace multiple spaces with single space
    normalized = str(text).strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def parse_integer_field(
    value: Any,
    field_name: str,
    min_value: int | None = None,
    max_value: int | None = None,
) -> tuple[int | None, str | None]:
    """
    Parse and validate integer field.

    Args:
        value: Input value to parse
        field_name: Name of field for error messages
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)

    Returns:
        Tuple of (parsed_value, error_message)
        If parsing succeeds: (int_value, None)
        If parsing fails: (None, error_message)

    Example:
        >>> parse_integer_field("84", "months", min_value=0)
        (84, None)
        >>> parse_integer_field("-5", "months", min_value=0)
        (None, "months must be at least 0")
    """
    if value is None or str(value).strip() == "":
        return None, None

    try:
        int_value = int(value)

        if min_value is not None and int_value < min_value:
            return None, _("%(field)s must be at least %(min)d") % {"field": field_name, "min": min_value}

        if max_value is not None and int_value > max_value:
            return None, _("%(field)s must be at most %(max)d") % {"field": field_name, "max": max_value}

        return int_value, None

    except (ValueError, TypeError):
        return None, _("Invalid integer value for %(field)s: %(value)s") % {"field": field_name, "value": value}


def parse_date_field(value: Any, field_name: str) -> tuple[date | None, str | None]:
    """
    Parse date from string in YYYY-MM-DD format.

    Args:
        value: Date value (string, date, or datetime)
        field_name: Name of field for error messages

    Returns:
        Tuple of (date_object, error_message)

    Example:
        >>> parse_date_field("2025-11-01", "submitted_date")
        (date(2025, 11, 1), None)
        >>> parse_date_field("invalid", "submitted_date")
        (None, "Invalid date format for submitted_date...")
    """
    if not value:
        return None, None

    # If already a date object
    if isinstance(value, date):
        return value, None

    # If datetime object
    if isinstance(value, datetime):
        return value.date(), None

    # Try parsing string in YYYY-MM-DD format
    value_str = str(value).strip()
    if not value_str:
        return None, None

    try:
        parsed = datetime.strptime(value_str, "%Y-%m-%d")
        return parsed.date(), None
    except (ValueError, TypeError):
        return (
            None,
            _("Invalid date format for %(field)s. Expected YYYY-MM-DD, got: %(value)s")
            % {"field": field_name, "value": value_str},
        )


def validate_citizen_id(citizen_id: str) -> str | None:
    """
    Validate citizen ID is exactly 12 digits.

    Args:
        citizen_id: Citizen ID string

    Returns:
        Error message if invalid, None if valid

    Example:
        >>> validate_citizen_id("123456789012")
        None
        >>> validate_citizen_id("12345")
        "Citizen ID must be exactly 12 digits..."
    """
    if not citizen_id:
        return _("Citizen ID is required")

    # Strip non-digits
    digits_only = re.sub(r"\D", "", citizen_id)

    if len(digits_only) != 12:
        return _("Citizen ID must be exactly 12 digits (column 3), got %(count)d digits") % {"count": len(digits_only)}

    return None


def validate_email(email: str) -> str | None:
    """
    Validate email format.

    Args:
        email: Email string

    Returns:
        Error message if invalid, None if valid
    """
    if not email:
        return _("Email is required (column 4)")

    # Simple email validation
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email.strip()):
        return _("Invalid email format (column 4): %(email)s") % {"email": email}

    return None


def convert_months_to_experience(months: int) -> str:
    """
    Convert months to YearsOfExperience enum.

    Args:
        months: Number of months of experience

    Returns:
        YearsOfExperience enum value

    Conversion table:
        0 → NO_EXPERIENCE
        1-11 → LESS_THAN_ONE_YEAR
        12-36 → ONE_TO_THREE_YEARS
        37-60 → THREE_TO_FIVE_YEARS
        61+ → MORE_THAN_FIVE_YEARS
    """
    if months == 0:
        return RecruitmentCandidate.YearsOfExperience.NO_EXPERIENCE
    elif months <= 11:
        return RecruitmentCandidate.YearsOfExperience.LESS_THAN_ONE_YEAR
    elif months <= 36:
        return RecruitmentCandidate.YearsOfExperience.ONE_TO_THREE_YEARS
    elif months <= 60:
        return RecruitmentCandidate.YearsOfExperience.THREE_TO_FIVE_YEARS
    else:
        return RecruitmentCandidate.YearsOfExperience.MORE_THAN_FIVE_YEARS


def get_or_create_recruitment_source(name: str, cache: dict) -> tuple[RecruitmentSource | None, str | None]:
    """
    Get or create RecruitmentSource by name (case-insensitive).

    Args:
        name: Source name
        cache: Cache dictionary for storing created sources

    Returns:
        Tuple of (source_instance, error_message)
    """
    if not name:
        return None, _("Recruitment source name is required (column 7)")

    normalized_name = normalize_text(name)

    # Check cache first
    cache_key = f"source_{normalized_name}"
    if cache_key in cache:
        return cache[cache_key], None

    # Try to find existing source (case-insensitive)
    source = RecruitmentSource.objects.filter(name__iexact=name.strip()).first()

    if not source:
        # Create new source
        try:
            source = RecruitmentSource.objects.create(
                name=name.strip(),
                allow_referral=False,
                description="Auto-created from import",
            )
            logger.info(f"Created new recruitment source: {source.code} - {source.name}")
        except Exception as e:
            return None, _("Failed to create recruitment source '%(name)s': %(error)s") % {
                "name": name,
                "error": str(e),
            }

    # Cache for future lookups
    cache[cache_key] = source
    return source, None


def get_or_create_recruitment_channel(name: str, cache: dict) -> tuple[RecruitmentChannel | None, str | None]:
    """
    Get or create RecruitmentChannel by name (case-insensitive).

    Args:
        name: Channel name
        cache: Cache dictionary for storing created channels

    Returns:
        Tuple of (channel_instance, error_message)
    """
    if not name:
        return None, _("Recruitment channel name is required (column 8)")

    normalized_name = normalize_text(name)

    # Check cache first
    cache_key = f"channel_{normalized_name}"
    if cache_key in cache:
        return cache[cache_key], None

    # Try to find existing channel (case-insensitive)
    channel = RecruitmentChannel.objects.filter(name__iexact=name.strip()).first()

    if not channel:
        # Create new channel with default belong_to
        try:
            channel = RecruitmentChannel.objects.create(
                name=name.strip(),
                belong_to=RecruitmentChannel.BelongTo.JOB_WEBSITE,
                description="Auto-created from import",
            )
            logger.info(f"Created new recruitment channel: {channel.code} - {channel.name}")
        except Exception as e:
            return None, _("Failed to create recruitment channel '%(name)s': %(error)s") % {
                "name": name,
                "error": str(e),
            }

    # Cache for future lookups
    cache[cache_key] = channel
    return channel, None


def get_default_proposer() -> Employee | None:
    """
    Get default proposer for auto-created recruitment requests.

    Returns the first active employee, or None if no employees exist.

    Returns:
        Employee instance or None
    """
    return Employee.objects.filter(status=Employee.Status.ACTIVE).first()


def find_or_create_recruitment_request(
    name: str, department: Department, cache: dict
) -> tuple[RecruitmentRequest | None, str | None]:
    """
    Find RecruitmentRequest by name.

    Args:
        name: Request name
        department: Department for the request
        cache: Cache dictionary for storing found requests

    Returns:
        Tuple of (request_instance, error_message)
    """
    if not name:
        return None, _("Recruitment request name is required (column 6)")

    # Normalize for cache lookup
    normalized_name = normalize_text(name)
    cache_key = f"request_{normalized_name}"

    # Check cache first
    if cache_key in cache:
        return cache[cache_key], None

    # Try to find existing request by name
    request = RecruitmentRequest.objects.filter(name__iexact=name.strip()).first()

    if not request:
        return None, _("Recruitment request '%(name)s' not found (column 6)") % {"name": name.strip()}

    # Cache for future lookups
    cache[cache_key] = request
    return request, None


def import_handler(row_index: int, row: list, import_job_id: str, options: dict) -> dict:  # noqa: C901
    """
    Import handler for recruitment candidates.

    Processes a single row from the XLSX import file and creates a RecruitmentCandidate.

    Args:
        row_index: 1-based row index (excluding header)
        row: List of cell values from the row
        import_job_id: UUID string of the ImportJob record
        options: Import options dictionary

    Returns:
        dict: Result with format:
            Success: {"ok": True, "result": {...}, "action": "created"|"updated"|"skipped"}
            Failure: {"ok": False, "error": "..."}
    """
    try:
        # Initialize cache from options if not present
        if "_cache" not in options:
            options["_cache"] = {}
        cache = options["_cache"]

        # STEP 1: Parse Row Data using COLUMN_MAPPING
        # Get headers from options (should be set by worker)
        headers = options.get("headers", [])
        if not headers:
            return {
                "ok": False,
                "row_index": row_index,
                "error": _("Headers not provided in options"),
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
        name = normalize_value(row_dict.get("name", ""))
        citizen_id = normalize_value(row_dict.get("citizen_id", ""))
        email = normalize_value(row_dict.get("email", ""))
        phone = normalize_value(row_dict.get("phone", ""))
        request_name = normalize_value(row_dict.get("recruitment_request_name", ""))
        source_name = normalize_value(row_dict.get("recruitment_source_name", ""))
        channel_name = normalize_value(row_dict.get("recruitment_channel_name", ""))
        department_name = normalize_value(row_dict.get("department_name", ""))
        block_name = normalize_value(row_dict.get("block_name", ""))
        branch_name = normalize_value(row_dict.get("branch_name", ""))
        referrer_code = normalize_value(row_dict.get("referrer_code", ""))
        months_raw = row_dict.get("months_experience")
        submitted_date_raw = row_dict.get("submitted_date")
        status_code_raw = row_dict.get("status_code")
        onboard_date_raw = row_dict.get("onboard_date")
        note = normalize_value(row_dict.get("note", ""))

        # STEP 2: Validate Row Data

        # If name is empty, skip the row (like employee.py)
        if not name:
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "warnings": [_("Missing required field (name)")],
            }

        if not citizen_id:
            return {"ok": False, "error": _("Citizen ID is required")}

        # Validate citizen ID format (exactly 12 digits)
        citizen_id_error = validate_citizen_id(citizen_id)
        if citizen_id_error:
            return {"ok": False, "error": citizen_id_error}

        # Clean citizen ID (digits only)
        citizen_id_clean = re.sub(r"\D", "", citizen_id)

        # Check if candidate already exists and handle allow_update
        allow_update = options.get("allow_update", False)
        existing_candidate = RecruitmentCandidate.objects.filter(citizen_id=citizen_id_clean).first()

        if existing_candidate and not allow_update:
            return {
                "ok": True,
                "row_index": row_index,
                "action": "skipped",
                "candidate_code": existing_candidate.code,
                "warnings": [
                    _("Candidate with Citizen ID '%(citizen_id)s' already exists (allow_update=False)")
                    % {"citizen_id": citizen_id_clean}
                ],
            }

        # Validate email
        email_error = validate_email(email)
        if email_error:
            return {"ok": False, "error": email_error}

        if not phone:
            return {"ok": False, "error": _("Phone number is required (column 5)")}

        # Parse months of experience
        months, months_error = parse_integer_field(months_raw, _("Months of experience"), min_value=0)
        if months_error:
            return {"ok": False, "error": _("%(error)s (column 13)") % {"error": months_error}}

        if months is None:
            months = 0  # Default to 0 if not provided

        # Parse submission date
        submitted_date, date_error = parse_date_field(submitted_date_raw, _("Submission date"))
        if date_error:
            return {"ok": False, "error": _("%(error)s (column 14)") % {"error": date_error}}

        if not submitted_date:
            return {"ok": False, "error": _("Submission date is required (column 14)")}

        # Parse and validate status code
        status_code, status_error = parse_integer_field(status_code_raw, _("Status code"), min_value=1, max_value=7)
        if status_error:
            return {"ok": False, "error": _("%(error)s (column 15)") % {"error": status_error}}

        if status_code is None:
            return {"ok": False, "error": _("Status code is required (column 15)")}

        # Map status code to Status enum
        status = STATUS_CODE_MAPPING.get(status_code)
        if not status:
            return {
                "ok": False,
                "error": _("Invalid status code. Must be 1-7, got %(code)d") % {"code": status_code},
            }

        # Parse onboard_date (required if status is HIRED)
        onboard_date = None
        if onboard_date_raw:
            onboard_date, onboard_date_error = parse_date_field(onboard_date_raw, _("Onboard date"))
            if onboard_date_error:
                return {"ok": False, "error": onboard_date_error}

        # Validate onboard_date is required when status_code is 6 (HIRED)
        if status_code == 6 and not onboard_date:
            return {
                "ok": False,
                "error": _("Onboard date is required when status is HIRED (status code 6)"),
            }

        # STEP 3: Find Organizational Structure (Must Exist)

        # Find Branch
        if not branch_name:
            return {"ok": False, "error": _("Branch name is required (column 11)")}

        branch = Branch.objects.filter(name__iexact=branch_name).first()
        if not branch:
            return {"ok": False, "error": _("Branch '%(name)s' not found (column 11)") % {"name": branch_name}}

        # Find Block within Branch
        if not block_name:
            return {"ok": False, "error": _("Block name is required (column 10)")}

        block = Block.objects.filter(name__iexact=block_name, branch=branch).first()
        if not block:
            return {
                "ok": False,
                "error": _("Block '%(block)s' not found in branch '%(branch)s' (column 10)")
                % {"block": block_name, "branch": branch_name},
            }

        # Find Department within Block
        if not department_name:
            return {"ok": False, "error": _("Department name is required (column 9)")}

        department = Department.objects.filter(name__iexact=department_name, block=block).first()
        if not department:
            return {
                "ok": False,
                "error": _("Department '%(dept)s' not found in block '%(block)s' (column 9)")
                % {"dept": department_name, "block": block_name},
            }

        # STEP 4: Get or Create Recruitment Source
        source, source_error = get_or_create_recruitment_source(source_name, cache)
        if source_error:
            return {"ok": False, "error": source_error}

        # STEP 5: Get or Create Recruitment Channel
        channel, channel_error = get_or_create_recruitment_channel(channel_name, cache)
        if channel_error:
            return {"ok": False, "error": channel_error}

        # STEP 6: Find or Create Recruitment Request
        request, request_error = find_or_create_recruitment_request(request_name, department, cache)
        if request_error:
            return {"ok": False, "error": request_error}

        # STEP 7: Find Employee Referrer (Optional)
        referrer = None
        if referrer_code:
            referrer = Employee.objects.filter(code=referrer_code).first()
            if not referrer:
                logger.warning(
                    f"Referrer employee '{referrer_code}' not found for row {row_index}, continuing without referrer"
                )

        # STEP 8: Convert and Map Data
        years_of_experience = convert_months_to_experience(months)

        # STEP 9: Create or Update RecruitmentCandidate (Within Transaction)
        with transaction.atomic():
            candidate_data = {
                "name": name,
                "email": email,
                "phone": phone,
                "recruitment_request": request,
                "recruitment_source": source,
                "recruitment_channel": channel,
                "referrer": referrer,
                "years_of_experience": years_of_experience,
                "submitted_date": submitted_date,
                "status": status,
                "note": note,
                # branch, block, department will be auto-set from recruitment_request in save()
            }

            # Add onboard_date if provided
            if onboard_date:
                candidate_data["onboard_date"] = onboard_date

            if existing_candidate:
                # Update existing candidate
                for key, value in candidate_data.items():
                    setattr(existing_candidate, key, value)
                existing_candidate.save()
                candidate = existing_candidate
                action = "updated"
                logger.info(f"Updated candidate {candidate.code} - {candidate.name}")
            else:
                # Create new candidate
                candidate_data["citizen_id"] = citizen_id_clean
                candidate = RecruitmentCandidate.objects.create(**candidate_data)
                action = "created"
                logger.info(f"Created candidate {candidate.code} - {candidate.name}")

        # STEP 10: Return Success Result
        return {
            "ok": True,
            "row_index": row_index,
            "action": action,
            "result": {
                "candidate_id": str(candidate.id),
                "candidate_code": candidate.code,
                "candidate_name": candidate.name,
            },
        }

    except Exception as e:
        logger.exception(f"Import handler error at row {row_index}: {e}")
        return {
            "ok": False,
            "error": str(e),
        }
