"""Employee services module."""

from .work_history import (
    # create_contract_change_event,  # TODO: Uncomment when Contract model is implemented
    create_position_change_event,
    create_state_change_event,
    create_transfer_event,
)

__all__ = [
    "create_state_change_event",
    "create_position_change_event",
    "create_transfer_event",
    # "create_contract_change_event",  # TODO: Uncomment when Contract model is implemented
]
