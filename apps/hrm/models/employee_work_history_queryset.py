from django.db import models
from django.utils.translation import gettext_lazy as _


class EmployeeWorkHistoryQuerySet(models.QuerySet):
    """Custom QuerySet for EmployeeWorkHistory with helper methods for creating different event types."""

    def create_state_change_event(
        self,
        employee,
        old_status,
        new_status,
        effective_date,
        start_date=None,
        end_date=None,
        note=None,
    ):
        """Create a state change event in employee work history.

        Args:
            employee: Employee instance
            old_status: Previous employee status
            new_status: New employee status
            effective_date: Date when the status change takes effect
            start_date: Optional start date for the event period (e.g., leave start date)
            end_date: Optional end date for the event period (e.g., leave end date)
            note: Optional additional notes

        Returns:
            EmployeeWorkHistory: The created work history record
        """
        from .employee_work_history import EmployeeWorkHistory

        previous_data = {"status": old_status}

        return self.create(
            employee=employee,
            name=EmployeeWorkHistory.EventType.CHANGE_STATUS,
            date=effective_date,
            status=new_status,
            from_date=start_date,
            to_date=end_date,
            note=note or "",
            detail=_("Status changed from {old_status} to {new_status}").format(
                old_status=old_status, new_status=new_status
            ),
            previous_data=previous_data,
        )

    def create_position_change_event(
        self,
        employee,
        old_position,
        new_position,
        effective_date,
        note=None,
    ):
        """Create a position change event in employee work history.

        Args:
            employee: Employee instance
            old_position: Previous position (Position instance or None)
            new_position: New position (Position instance)
            effective_date: Date when the position change takes effect
            note: Optional additional notes

        Returns:
            EmployeeWorkHistory: The created work history record
        """
        from .employee_work_history import EmployeeWorkHistory

        old_position_name = old_position.name if old_position else _("None")
        new_position_name = new_position.name if new_position else _("None")

        previous_data = {"position_id": old_position.id if old_position else None}

        return self.create(
            employee=employee,
            name=EmployeeWorkHistory.EventType.CHANGE_POSITION,
            date=effective_date,
            note=note or "",
            detail=_("Position changed from {old_position} to {new_position}").format(
                old_position=old_position_name, new_position=new_position_name
            ),
            previous_data=previous_data,
        )

    def create_transfer_event(
        self,
        employee,
        old_department,
        new_department,
        old_position=None,
        new_position=None,
        effective_date=None,
        note=None,
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

        Returns:
            EmployeeWorkHistory: The created work history record
        """
        from datetime import date

        from .employee_work_history import EmployeeWorkHistory

        if effective_date is None:
            effective_date = date.today()

        old_dept_name = old_department.name if old_department else _("None")
        new_dept_name = new_department.name if new_department else _("None")

        detail_parts = [
            _("Transferred from {old_dept} to {new_dept}").format(old_dept=old_dept_name, new_dept=new_dept_name)
        ]

        previous_data = {
            "department_id": old_department.id if old_department else None,
            "branch_id": old_department.branch_id if old_department else None,
            "block_id": old_department.block_id if old_department else None,
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

        return self.create(
            employee=employee,
            name=EmployeeWorkHistory.EventType.TRANSFER,
            date=effective_date,
            note=note or "",
            detail=detail,
            previous_data=previous_data,
        )

    def create_contract_change_event(
        self,
        employee,
        old_contract,
        new_contract,
        effective_date,
        note=None,
    ):
        """Create a contract change event in employee work history.

        Args:
            employee: Employee instance
            old_contract: Previous contract type (ContractType instance or None)
            new_contract: New contract type (ContractType instance)
            effective_date: Date when the contract change takes effect
            note: Optional additional notes

        Returns:
            EmployeeWorkHistory: The created work history record
        """
        from .employee_work_history import EmployeeWorkHistory

        old_contract_name = old_contract.name if old_contract else _("None")
        new_contract_name = new_contract.name if new_contract else _("None")

        previous_data = {
            "contract_id": old_contract.id if old_contract else None,
            "contract_type": str(old_contract_name),  # Convert lazy translation to string for JSON
        }

        return self.create(
            employee=employee,
            name=EmployeeWorkHistory.EventType.CHANGE_CONTRACT,
            date=effective_date,
            contract=new_contract,
            note=note or "",
            detail=_("Contract changed from {old_contract} to {new_contract}").format(
                old_contract=old_contract_name, new_contract=new_contract_name
            ),
            previous_data=previous_data,
        )
