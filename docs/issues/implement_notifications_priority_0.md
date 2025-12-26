# Implement Priority 0 Notifications (Complaints, Proposals, KPI)

## Context
We need to implement push notifications for high-priority scenarios regarding the status of employee requests (Timekeeping Complaints, Proposals) and performance evaluations (KPI).

## Core Requirements
1.  **Code Language:** All code (variable names, comments, logic) must be written in **English**.
2.  **Delivery Method:** Push notification (Mobile/App).
3.  **Mechanism:** Use `apps.notifications.utils.create_notification` and `create_bulk_notifications`.
4.  **Localization (Crucial):
    *   Notification messages in the code must be wrapped in `gettext` (e.g., `_("Message content")`).
    *   **You must update the Vietnamese translation file** (`apps/{module}/locale/vi/LC_MESSAGES/django.po`) with the specific Vietnamese content provided below.
    *   Run `django-admin makemessages` or manually edit the `.po` file, then compile if necessary.

## Implementation Details

### 1. Infrastructure Requirements (Priority 1)
Before implementing the scenarios, you must update the notification infrastructure to support specific device targeting.

#### 1.1 Model Update
*   **File:** `apps/notifications/models.py`
*   **Action:** Add a `target_device` field to the `Notification` model.
    ```python
    target_device = models.ForeignKey(
        "core.UserDevice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Target device",
        help_text="Specific device to send the notification to. If null, send to all active devices."
    )
    ```
*   **Migration:** Create and run the migration.

#### 1.2 Helper Functions Update
*   **File:** `apps/notifications/utils.py`
*   **Action:** Update `create_notification` and `create_bulk_notifications` to accept `target_device` (UserDevice) and `client` (UserDevice.Client) arguments.
*   **Logic:**
    *   If `client` is provided (e.g., "mobile") and `target_device` is not, resolve the active device for that client (e.g., `recipient.devices.filter(client=client, state='active').first()`) and set it as `target_device`.
    *   **Constraint:** The system enforces unique active mobile device per user, so `client='mobile'` safely maps to a single device.

#### 1.3 Service Update
*   **File:** `apps/notifications/fcm_service.py`
*   **Action:** Update `send_notification` logic.
    *   **IF** `notification.target_device` is set: Send ONLY to that device's token.
    *   **ELSE**: Fetch ALL active devices for the recipient and send to all of them.

### 2. Scenarios & Translations (Priority 0 Logic)

**IMPORTANT:** For all scenarios below, you must ensure the notification is targeted at **Mobile** devices (pass `client='mobile'` to the helper functions).

#### Scenario A: Timekeeping Complaint (Khiếu nại chấm công)
**Model:** `apps.hrm.models.Proposal`
**Proposal Type:** `ProposalType.TIMESHEET_ENTRY_COMPLAINT`
**Recipient:** `created_by`

| Trigger | English Source (Code) | Vietnamese Translation (PO File) | Dynamic Variables |
| :--- | :--- | :--- | :--- |
| **Confirmed** by Manager | "Your timekeeping complaint has been confirmed by %(manager_name)s." | "Khiếu nại chấm công của bạn đã được \"Xác nhận\" bởi %(manager_name)s." | `manager_name` |
| **Rejected** by Manager | "Your timekeeping complaint was rejected by %(manager_name)s with note: \"%(note)s\".." | "Khiếu nại chấm công của bạn đã bị \"Từ chối\" bởi %(manager_name)s cùng Ghi chú \"%(note)s\"." | `manager_name`, `note` |
| **Approved** by HR | "Your timekeeping complaint has been approved by HR." | "Khiếu nại chấm công của bạn đã được \"Duyệt\" bởi phòng nhân sự." | None |
| **Rejected** by HR | "Your timekeeping complaint was rejected by HR with note: \"%(note)s\".." | "Khiếu nại chấm công của bạn đã bị \"Từ chối\" bởi Phòng nhân sự cùng Ghi chú \"%(note)s\"." | `note` |

**Implementation Hint:**
*   **Manager Name:** Use the full name of the `verifier` or the department leader.
*   **Note:** If `approval_note` is empty, handle gracefully.

#### Scenario B: General Proposal (Đề xuất)
**Model:** `apps.hrm.models.Proposal`
**Proposal Type:** All other types (e.g., `LATE_EXEMPTION`, `LEAVE`, etc.)
**Recipient:** `created_by`

| Trigger | English Source (Code) | Vietnamese Translation (PO File) | Dynamic Variables |
| :--- | :--- | :--- | :--- |
| **Confirmed** by Manager | "Your %(proposal_type)s proposal has been confirmed by %(manager_name)s." | "Đề xuất %(proposal_type)s của bạn đã được \"Xác nhận\" bởi %(manager_name)s." | `proposal_type`, `manager_name` |
| **Rejected** by Manager | "Your %(proposal_type)s proposal was rejected by %(manager_name)s with note: \"%(note)s\".." | "Đề xuất %(proposal_type)s của bạn đã bị \"Từ chối\" bởi %(manager_name)s cùng Ghi chú \"%(note)s\"." | `proposal_type`, `manager_name`, `note` |
| **Approved** by HR | "Your %(proposal_type)s proposal has been approved by HR." | "Đề xuất %(proposal_type)s của bạn đã được \"Duyệt\" bởi phòng nhân sự." | `proposal_type` |
| **Rejected** by HR | "Your %(proposal_type)s proposal was rejected by HR with note: \"%(note)s\".." | "Đề xuất %(proposal_type)s của bạn đã bị \"Từ chối\" bởi Phòng nhân sự cùng Ghi chú \"%(note)s\"." | `proposal_type`, `note` |

**Implementation Hint:**
*   **Proposal Type:** Ensure `proposal.get_proposal_type_display()` is used and itself translated, OR pass the translated type name to the string.

#### Scenario C: KPI Evaluation Created
**Model:** `apps.payroll.models.EmployeeKPIAssessment`
**Recipient:** `employee`

| Trigger | English Source (Code) | Vietnamese Translation (PO File) | Dynamic Variables |
| :--- | :--- | :--- | :--- |
| System creates assessment | "KPI Assessment for period %(period)s has been created. Please access KPI Assessment to complete." | "Phiếu đánh giá kỳ %(period)s đã được tạo. Vui lòng truy cập Đánh giá KPI để hoàn tất." | `period` |

**Implementation Hint:**
*   **Period:** Format as "MM/YYYY" (e.g., "01/2024").

## Technical Notes

1.  **HR Identification:**
    *   To label actions by "HR", simply use the translated string for "HR" or "Human Resources Department" where applicable.

2.  **Manager Identification:**
    *   Typically `proposal.created_by.department.leader`.

3.  **Signal/Service Location:**
    *   Create `apps/{module}/signals/notifications.py` (or similar).
    *   Connect signals in `apps/{module}/apps.py`.

## Action Items
1.  **INFRASTRUCTURE:** Update `Notification` model, migrations, `utils.py`, and `fcm_service.py` as described in Section 1.
2.  **LOGIC:** Implement signal handlers for `Proposal` status changes and `EmployeeKPIAssessment` creation.
3.  **LOCALIZATION:** Manually update `apps/{module}/locale/vi/LC_MESSAGES/django.po` with provided translations.
