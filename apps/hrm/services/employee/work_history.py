"""Employee work history service functions.

This module provides helper functions for creating employee work history records.
"""

from datetime import date

from django.utils.translation import gettext_lazy as _

from apps.hrm.models import EmployeeWorkHistory


def create_state_change_event(
    employee,
    old_status,
    new_status,
    effective_date,
    start_date=None,
    end_date=None,
    note=None,
    extra_detail=None,
    decision=None,
):
    """Create a state change event in employee work history.

    Args:
        employee: Employee instance
        old_status: Previous employee status (can be None for new employees)
        new_status: New employee status
        effective_date: Date when the status change takes effect
        start_date: Optional start date for the event period (e.g., leave start date)
        end_date: Optional end date for the event period (e.g., leave end date)
        note: Optional additional notes
        extra_detail: Optional string to append to the detail description
        decision: Optional Decision instance associated with this event

    Returns:
        EmployeeWorkHistory: The created work history record
    """
    previous_data = {"status": old_status}

    if old_status is None:
        old_status_display = _("None")
    else:
        old_status_display = _(old_status)

    new_status_display = _(new_status)
    detail = _("Status changed from {old_status} to {new_status}").format(
        old_status=old_status_display, new_status=new_status_display
    )

    if extra_detail:
        detail = f"{detail}. {extra_detail}"

    return EmployeeWorkHistory.objects.create(
        employee=employee,
        name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
        date=effective_date,
        status=new_status,
        from_date=start_date,
        to_date=end_date,
        note=note or "",
        detail=detail,
        previous_data=previous_data,
        decision=decision,
    )


def create_position_change_event(
    employee,
    old_position,
    new_position,
    effective_date,
    note=None,
    decision=None,
):
    """Create a position change event in employee work history.

    Args:
        employee: Employee instance
        old_position: Previous position (Position instance or None)
        new_position: New position (Position instance)
        effective_date: Date when the position change takes effect
        note: Optional additional notes
        decision: Optional Decision instance associated with this event

    Returns:
        EmployeeWorkHistory: The created work history record
    """
    old_position_name = old_position.name if old_position else _("None")
    new_position_name = new_position.name if new_position else _("None")

    previous_data = {"position_id": old_position.id if old_position else None}

    return EmployeeWorkHistory.objects.create(
        employee=employee,
        name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
        date=effective_date,
        note=note or "",
        detail=_("Position changed from {old_position} to {new_position}").format(
            old_position=old_position_name, new_position=new_position_name
        ),
        previous_data=previous_data,
        decision=decision,
    )


def create_transfer_event(
    employee,
    old_department,
    new_department,
    old_position=None,
    new_position=None,
    effective_date=None,
    note=None,
    decision=None,
):
    """Create a transfer event in employee work history.

    Args:
        employee: Employee instance
        old_department: Previous department (Department instance or None)
        new_department: New department (Department instance)
        old_position: Previous position (Position instance or None)
        new_position: New position (Position instance or None)
        effective_date: Date when the transfer takes effect
        note: Optional additional notes
        decision: Optional Decision instance associated with this event

    Returns:
        EmployeeWorkHistory: The created work history record
    """
    if effective_date is None:
        effective_date = date.today()

    # Build detailed organizational hierarchy information
    old_branch_name = old_department.branch.name if old_department else _("None")
    new_branch_name = new_department.branch.name if new_department else _("None")
    old_block_name = old_department.block.name if old_department else _("None")
    new_block_name = new_department.block.name if new_department else _("None")
    old_dept_name = old_department.name if old_department else _("None")
    new_dept_name = new_department.name if new_department else _("None")

    detail_parts = [
        _("Transferred from {old_branch}/{old_block}/{old_dept} to {new_branch}/{new_block}/{new_dept}").format(
            old_branch=old_branch_name,
            old_block=old_block_name,
            old_dept=old_dept_name,
            new_branch=new_branch_name,
            new_block=new_block_name,
            new_dept=new_dept_name,
        )
    ]

    previous_data = {
        "branch_id": old_department.branch_id if old_department else None,
        "block_id": old_department.block_id if old_department else None,
        "department_id": old_department.id if old_department else None,
    }

    if old_position != new_position and new_position is not None:
        old_pos_name = old_position.name if old_position else _("None")
        new_pos_name = new_position.name if new_position else _("None")
        detail_parts.append(
            _("Position changed from {old_position} to {new_position}").format(
                old_position=old_pos_name, new_position=new_pos_name
            )
        )
        previous_data["position_id"] = old_position.id if old_position else None

    detail = ". ".join(detail_parts)

    return EmployeeWorkHistory.objects.create(
        employee=employee,
        name=EmployeeWorkHistory.EventType.TRANSFER,
        date=effective_date,
        note=note or "",
        detail=detail,
        previous_data=previous_data,
        decision=decision,
    )


def create_employee_type_change_event(
    employee,
    old_employee_type,
    new_employee_type,
    effective_date,
    note=None,
    decision=None,
):
    """Create an employee type change event in work history.

    Args:
        employee: Employee instance
        old_employee_type: Previous EmployeeType value
        new_employee_type: New EmployeeType value
        effective_date: Date when the type change takes effect
        note: Optional note
        decision: Optional Decision instance associated with this event

    Returns:
        EmployeeWorkHistory: The created work history record
    """
    old_type_display = old_employee_type if old_employee_type is not None else _("None")
    new_type_display = new_employee_type if new_employee_type is not None else _("None")

    previous_data = {"employee_type": old_employee_type}

    detail = _("Employee type changed from {old_type} to {new_type}").format(
        old_type=old_type_display, new_type=new_type_display
    )

    return EmployeeWorkHistory.objects.create(
        employee=employee,
        name=EmployeeWorkHistory.EventType.CHANGE_EMPLOYEE_TYPE,
        date=effective_date,
        from_date=effective_date,
        note=note or "",
        detail=detail,
        previous_data=previous_data,
        decision=decision,
    )


def create_contract_change_event(
    employee,
    old_contract,
    new_contract,
    effective_date,
    note=None,
    decision=None,
):
    """Create a contract change event in employee work history.

    Args:
        employee: Employee instance
        old_contract: Previous contract (Contract instance or None)
        new_contract: New contract (Contract instance)
        effective_date: Date when the contract change takes effect
        note: Optional additional notes
        decision: Optional Decision instance associated with this event

    Returns:
        EmployeeWorkHistory: The created work history record
    """
    old_contract_display = old_contract.contract_number if old_contract else _("None")
    new_contract_display = new_contract.contract_number if new_contract else _("None")

    previous_data = {
        "contract_id": old_contract.id if old_contract else None,
        "contract_code": old_contract.code if old_contract else None,
        "contract_number": old_contract.contract_number if old_contract else None,
    }

    return EmployeeWorkHistory.objects.create(
        employee=employee,
        name=EmployeeWorkHistory.EventType.CHANGE_CONTRACT,
        date=effective_date,
        contract=new_contract,
        note=note or "",
        detail=_("Contract changed from {old_contract} to {new_contract}").format(
            old_contract=old_contract_display, new_contract=new_contract_display
        ),
        previous_data=previous_data,
        decision=decision,
    )
