# Issue: Refactor & Implement Advanced Contract Import Strategies

## Clickup link:
https://app.clickup.com/t/86evx9c1n

## 1. Mô tả bài toán (Task Description)

Hệ thống cần nâng cấp tính năng Import Hợp đồng để hỗ trợ nhiều kịch bản nghiệp vụ khác nhau, thay vì một luồng import chung chung như hiện tại. Mục tiêu là tách biệt luồng tạo mới, cập nhật và phụ lục hợp đồng, đồng thời tự động hóa các tác động phụ (side-effects) liên quan đến quản lý nhân sự.

### Các trường hợp cần xử lý:
1.  **Logic Mới (Tạo mới/Chuyển đổi hợp đồng)**:
    *   Sử dụng file mẫu: `addition_contract_template.xlsx`.
    *   Tự động tính toán Trạng thái hợp đồng theo Ngày hiệu lực.
    *   Cập nhật Loại nhân viên (`Employee.employee_type`) tương ứng.
    *   Tạo Lịch sử công tác (`EmployeeWorkHistory`) cho nhân viên.
    *   Cơ chế chống trùng lặp an toàn.
2.  **Logic Hiện tại (Cập nhật hợp đồng)**:
    *   Sử dụng file mẫu: `contract_template.xlsx`.
    *   Chỉ cho phép cập nhật các hợp đồng đang ở trạng thái **DRAFT**.
    *   Loại bỏ logic tự động tạo mới trong luồng này.
3.  **Luồng Phụ lục hợp đồng**:
    *   Tách riêng thành handler độc lập chỉ hỗ trợ loại Phụ lục (`Appendix`).

---

## 2. Bối cảnh hệ thống (Context)

### Models liên quan:
*   **Contract**: Chứa thông tin hợp đồng, trạng thái (`DRAFT`, `ACTIVE`, `NOT_EFFECTIVE`, ...). Có method `get_status_from_dates()` để tính status.
*   **Employee**: Cần cập nhật trường `employee_type` khi có hợp đồng mới.
*   **EmployeeWorkHistory**: Cần tạo bản ghi mới khi chuyển đổi hợp đồng (Event: `CHANGE_CONTRACT`).
*   **ContractType**: Phân loại theo `category` (`contract` hoặc `appendix`).

### ViewSets & Mixins:
*   **ContractViewSet**: Sử dụng `AsyncImportProgressMixin` để xử lý import không đồng bộ.
*   **AsyncImportProgressMixin**: Cung cấp action `/import/`, cho phép định nghĩa `import_row_handler`.

---

## 3. Yêu cầu chi tiết (Detailed Requirements)

### A. Luồng Tạo mới (Creation/Transition)
*   **Handler**: `contract_creation.py`
*   **Validate**:
    *   Chỉ chấp nhận loại hợp đồng có `category='contract'`.
    *   **Chống trùng lặp**: Nếu nhân viên đã có một hợp đồng (không phải Draft) có cùng [Loại hợp đồng] và [Ngày hiệu lực] -> Báo lỗi để tránh import trùng.
*   **Xử lý nghiệp vụ**:
    *   Tạo mới bản ghi `Contract`.
    *   `status`: Tính toán tự động bằng `get_status_from_dates()`.
    *   `Employee.employee_type`: Cập nhật theo giá trị từ cột `employee_type` trong file excel.
    *   `EmployeeWorkHistory`: Tạo bản ghi mới liên kết với nhân viên và hợp đồng vừa tạo.

### B. Luồng Cập nhật (Update)
*   **Handler**: `contract_update.py`
*   **Validate**:
    *   Chỉ chấp nhận update nếu `contract.status == 'draft'`.
    *   Nếu không tìm thấy hợp đồng hoặc hợp đồng đã ký/hiệu lực -> Báo lỗi.
*   **Xử lý nghiệp vụ**: Cập nhật các thông tin field trên bản ghi hiện có. Không tạo mới.

### C. Luồng Phụ lục (Appendix)
*   **Handler**: `contract_appendix.py`
*   **Validate**: Chỉ chấp nhận loại hợp đồng có `category='appendix'`.
*   **Xử lý nghiệp vụ**: Giữ nguyên logic liên kết với hợp đồng gốc (parent_contract).

---

## 4. Kế hoạch triển khai (Technical Plan)

1.  **Handler Refactoring**:
    *   Rename `apps/hrm/import_handlers/contract.py` -> `apps/hrm/import_handlers/contract_appendix.py`.
    *   Tạo `apps/hrm/import_handlers/contract_creation.py`.
    *   Tạo `apps/hrm/import_handlers/contract_update.py`.
2.  **ViewSet Dispatcher**:
    *   Trong `ContractViewSet`, override `get_import_handler_path`.
    *   Sử dụng `options.get('mode')` để trả về đường dẫn handler tương ứng (`create` hoặc `update`).
    *   Mặc định nếu không có mode hợp lệ -> Trả về lỗi 400.
3.  **Appendix ViewSet**:
    *   Cấu hình `import_row_handler` cho `ContractAppendixViewSet` trỏ về `contract_appendix.py`.

---

## 5. Danh sách Test Cases (Text Version)

### Group 1: Tạo mới (Creation)
*   **TC_CR_01**: Import thành công 1 hợp đồng mới. Kiểm tra status tự động nhảy sang `ACTIVE` (nếu ngày hiệu lực là hôm nay), `Employee` đổi loại thành công, có tạo `WorkHistory`.
*   **TC_CR_02**: Import trùng thông tin (NV + Loại HĐ + Ngày hiệu lực) đã có trong hệ thống -> Mong đợi: Báo lỗi trùng lặp.
*   **TC_CR_03**: Import với loại hợp đồng là "Phụ lục" vào luồng tạo mới Hợp đồng -> Mong đợi: Báo lỗi sai loại dữ liệu.
*   **TC_CR_04**: Kiểm tra conflict: Loại nhân viên trong file và loại hợp đồng không phù hợp (nếu có logic check).

### Group 2: Cập nhật (Update)
*   **TC_UP_01**: Cập nhật thành công thông tin lương cho 1 hợp đồng đang ở trạng thái `DRAFT`.
*   **TC_UP_02**: Cố gắng cập nhật 1 hợp đồng đang ở trạng thái `ACTIVE` -> Mong đợi: Báo lỗi "Chỉ cho phép update bản nháp".
*   **TC_UP_03**: File import chứa mã hợp đồng không tồn tại -> Mong đợi: Báo lỗi không tìm thấy.

### Group 3: Phụ lục (Appendix)
*   **TC_AP_01**: Import phụ lục thành công thông qua handler chuyên biệt.
*   **TC_AP_02**: Dùng handler phụ lục để import hợp đồng chính thức -> Mong đợi: Báo lỗi.

### Group 4: Hệ thống (Routing)
*   **TC_RT_01**: Gọi API import với `mode=create` -> Kiểm tra hệ thống gọi đúng handler creation.
*   **TC_RT_02**: Gọi API import với `mode=update` -> Kiểm tra hệ thống gọi đúng handler update.
*   **TC_RT_03**: Gọi API import không truyền `mode` hoặc `mode` sai -> Mong đợi: Trả về lỗi 400 Bad Request.

### Notes:
- skeleton test file: apps/hrm/tests/test_contract_import_strategies.py
