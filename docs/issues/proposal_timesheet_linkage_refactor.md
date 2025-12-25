# Refactor ProposalTimeSheetEntry for Multi-Type Support

## 1. Objective
Refactor the `ProposalTimeSheetEntry` model to serve as a universal junction table between **Proposals** and **TimeSheetEntries** for all proposal types (not just Complaints), while refining the validation logic to allow re-submission of Complaints if previous attempts were rejected.

## 2. Context
Currently, `ProposalTimeSheetEntry` is restricted to link only `TIMESHEET_ENTRY_COMPLAINT` proposals. The system is evolving to link *all* affecting proposals (Leaves, Late Exemptions, Overtime, etc.) to their respective TimeSheet entries immediately upon creation, approval, or rejection. This allows for more efficient lookup during timesheet calculation.

## 3. Requirements

### A. Schema Changes
- **File**: `apps/hrm/models/proposal.py`
- **Model**: `ProposalTimeSheetEntry`
- **Action**: Remove the `limit_choices_to={"proposal_type": ProposalType.TIMESHEET_ENTRY_COMPLAINT}` attribute from the `proposal` ForeignKey.
- **Goal**: Allow this model to store links for any `ProposalType`.

### B. Validation Logic Update (`clean()` method)
The current validation enforces a strict **1-1 relationship** between a `TimeSheetEntry` and a `Proposal` of type `TIMESHEET_ENTRY_COMPLAINT`. This blocks users from submitting a new complaint if a previous one exists, even if the previous one was **REJECTED**.

**New Logic Requirements:**
1.  **Scope**: Validation still *only* applies when `self.proposal.proposal_type == PropsalToype.TIMESHEET_ENTRY_COMPLAINT`. Other types (Leaves, etc.) allow M-N relationships and should bypass this check.
2.  **Constraint Relaxing**: When checking for existing links to a TimeSheetEntry:
    - Ignore existing links where the related Proposal is in a "Terminal" state.
    - **Terminal States**: `ProposalStatus.REJECTED`, `ProposalStatus.CANCELLED` (if applicable).
    - **Rule**: A TimeSheetEntry can have at most **ONE** `PENDING` or `APPROVED` Complaint Proposal at a time.

**Scenario:**
- User creates Complaint A for TimeSheet X -> **Allowed**.
- Manager REJECTS Complaint A.
- User creates Complaint B for TimeSheet X -> **Allowed** (Previous check would have failed).
- User creates Complaint C for TimeSheet X -> **Blocked** (Because B is still Pending/Approved).

### C. Signals / Service Logic (Implementation Notes)
*Note: This specific task only covers the Model/Validation changes. The implementation of the synchronization logic (creating these records) is handled separately.*

## 4. Implementation Details

### `clean()` Method Refactoring
Modify `apps/hrm/models/proposal.py`:

```python
def clean(self) -> None:
    super().clean()

    # Only validate for TIMESHEET_ENTRY_COMPLAINT type proposals
    if self.proposal_id and self.proposal.proposal_type == ProposalType.TIMESHEET_ENTRY_COMPLAINT:

        # Terminal states that allow a new complaint to supersede the old one
        TERMINAL_STATUSES = [ProposalStatus.REJECTED, ProposalStatus.CANCELLED]

        # Build base queryset excluding self if this is an update
        base_qs = ProposalTimeSheetEntry.objects.all()
        if self.pk:
            base_qs = base_qs.exclude(pk=self.pk)

        # Check 1: Proposal can only have one timesheet entry (No change needed here ideally, but good to keep)
        existing_for_proposal = base_qs.filter(proposal_id=self.proposal_id)
        if existing_for_proposal.exists():
            raise ValidationError(
                {"proposal": _("A timesheet entry complaint proposal can only be linked to one timesheet entry.")}
            )

        # Check 2: TimeSheetEntry can only have one ACTIVE (Non-Terminal) complaint proposal
        existing_for_timesheet = base_qs.filter(
            timesheet_entry_id=self.timesheet_entry_id,
            proposal__proposal_type=ProposalType.TIMESHEET_ENTRY_COMPLAINT
        ).exclude(
            proposal__proposal_status__in=TERMINAL_STATUSES
        )

        if existing_for_timesheet.exists():
            raise ValidationError(
                {"timesheet_entry": _("This timesheet entry already has a pending or approved complaint proposal.")}
            )
```

## 5. Verification
Create/Run tests to verify:
1.  **Multi-Type Support**: Can successfully create a `ProposalTimeSheetEntry` for a `PAID_LEAVE` proposal.
2.  **Complaint Blocking**: Cannot create two `PENDING` complaints for the same TimeSheet.
3.  **Complaint Re-submission**:
    - Create Complaint A (Pending) -> Link.
    - Change A to Rejected.
    - Create Complaint B (Pending) -> Link (Should Succeed).
    - Try to create Complaint C -> Fail.

## 6. Out of Scope
- Data migration for existing records (handled via separate shell command).
- Logic for `TimesheetCalculator`.
- Automatic creation of these links (handled in Service/Signals layer, separate task).
