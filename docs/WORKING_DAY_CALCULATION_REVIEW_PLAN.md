# Kế Hoạch Tổng Thể: Rà Soát & Chuẩn Hóa Logic Tính Ngày Công

**Trạng thái:** Draft
**Dựa trên:** `docs/TÀI LIỆU QUY TẮC NGHIỆP VỤ_ TÍNH TOÁN VÀ LƯU TRỮ NGÀY CÔNG.md` (v2.9)
**Mục tiêu:** Đồng bộ codebase hiện tại với tài liệu nghiệp vụ đã chuẩn hóa, đảm bảo tính chính xác cho dữ liệu tính lương.

---

## 1. Tóm Tắt Khoảng Cách (Gap Analysis)

Hệ thống hiện tại thiếu các trường lưu trữ giá trị tại thời điểm tính toán (Snapshot), thiếu phân loại OT chi tiết (TC1/TC2/TC3), và logic xử lý phạt/check-in thiếu chưa triệt để. Ngoài ra, cần bổ sung cơ chế xác định thời gian OT thực tế và chốt trạng thái cuối ngày.

---

## 2. Kế Hoạch Triển Khai

### Giai đoạn 1: Cập Nhật Cấu Trúc Dữ Liệu (Database Schema)
**Mục tiêu:** Bổ sung các trường thiếu để lưu snapshot và đổi tên các trường OT cho đúng nghiệp vụ.

1.  **Chỉnh sửa `TimeSheetEntry` (Bảng ngày công):**
    *   **Nhóm Snapshot (Lưu giá trị đầu vào tại thời điểm tạo):**
        *   `contract`: ForeignKey tới Contract (null=True, on_delete=SET_NULL).
        *   `wage_rate`: Integer (default 100) - Tỷ lệ hưởng lương.
        *   `is_full_salary`: Boolean (default True).
        *   `day_type`: Đảm bảo cover đủ các loại: `official` (Ngày thường), `holiday` (Lễ), `compensatory` (Làm bù).
        *   `is_exempt`: Boolean (default False) - Miễn chấm công.
    *   **Nhóm Kết Quả Tính Toán (Calculated Metrics):**
        *   `compensation_value`: Decimal (default 0) - Giá trị công bù trừ.
        *   `paid_leave_hours`: Decimal (default 0) - Giờ nghỉ phép có lương.
        *   `ot_tc1_hours`: Decimal (default 0) - OT Ngày thường.
        *   `ot_tc2_hours`: Decimal (default 0) - OT Cuối tuần.
        *   `ot_tc3_hours`: Decimal (default 0) - OT Ngày lễ.
        *   `ot_start_time`: DateTime (null=True) - Giờ bắt đầu OT thực tế (Giao thoa giữa Log & Đề xuất).
        *   `ot_end_time`: DateTime (null=True) - Giờ kết thúc OT thực tế (Giao thoa giữa Log & Đề xuất).
        *   `late_minutes`: Integer (default 0) - Số phút đi muộn thực tế.
        *   `early_minutes`: Integer (default 0) - Số phút về sớm thực tế.
        *   `is_punished`: Boolean (default False) - Cờ xác định có bị phạt chuyên cần không (Dựa trên Ân hạn).

2.  **Chỉnh sửa `EmployeeMonthlyTimesheet` (Tổng hợp tháng):**
    *   **Đổi tên (Rename)** `saturday_in_week_overtime_hours` -> `tc1_overtime_hours`.
    *   **Đổi tên (Rename)** `sunday_overtime_hours` -> `tc2_overtime_hours`.
    *   **Đổi tên (Rename)** `holiday_overtime_hours` -> `tc3_overtime_hours`.
    *   **Thêm mới** `late_coming_minutes`, `early_leaving_minutes`.
    *   **Thêm mới** `total_penalty_count`.

### Giai đoạn 2: Tái Cấu Trúc Kiến Trúc & Logic
**Mục tiêu:** Tách biệt "Lưu trữ đầu vào" (Snapshot) và "Tính toán hàng ngày" (Calculation), đảm bảo tính cập nhật (Reactive).

#### 2.1. Cơ chế Snapshot (Mới)
*   **Nguyên tắc:** `TimeSheetEntry` là nguồn sự thật duy nhất (Source of Truth) cho các "Luật" áp dụng trong ngày đó. Calculator **KHÔNG** query lại WorkSchedule, Holiday, CompensatoryWorkday, Contract, Proposal tables, mà tin tưởng vào dữ liệu đã snapshot lưu trong `TimeSheetEntry`.
*   **Thời điểm Trigger:** Khi tạo mới `TimeSheetEntry` hoặc khi dữ liệu đầu vào (WorkSchedule, Holiday, CompensatoryWorkday, Contract, Proposal) thay đổi (tạo mới, sửa, xóa. Tuy nhiên cần xác định rõ là có ảnh hưởng đến TimeSheetEntry nào thì mới trigger cho TimeSheetEntry đó).
*   **Service xử lý (`TimesheetSnapshotService`):**
    1.  WorkSchedule, Holiday, CompensatoryWorkday: Xác định `day_type` (Lễ/Bù/Thường).
    2.  Contract: Lấy Hợp đồng hiệu lực & `wage_rate`.
    3.  Proposal: chỉ lấy từ các Proposal được duyệt, các thông tin sau: thời gian OT, miễn trừ chấm công, đi sớm về muộn, hậu thai sản, nghỉ phép có lương, ...
    4.  Lưu vào `TimeSheetEntry`.

#### 2.2. Cơ chế Tự động cập nhật (Signal Trigger)
**Mục tiêu:** Đảm bảo `TimeSheetEntry` luôn phản ánh đúng cấu hình mới nhất.
*   **Các Trigger Events:**
    *   `WorkSchedule` (Thay đổi): Tìm nhân viên bị ảnh hưởng -> Trigger Snapshot & Recalculate.
    *   `Holiday`, `CompensatoryWorkday`: Trigger Snapshot `day_type`.
    *   `Contract`: Trigger Snapshot `contract` & `wage_rate`.
    *   `Proposal` Duyệt
    *   `AttendanceRecord`: Chỉ Trigger Recalculate (Tính toán lại giờ).

#### 2.3. Viết lại hoàn toàn `TimesheetCalculator`
**Mục tiêu:** Xây dựng lại logic từ đầu để đảm bảo chuẩn hóa, tránh "vá víu".
*   **Input:** Instance `TimeSheetEntry` (đã có đủ dữ liệu Snapshot).
*   **Trách nhiệm:**
    *   **Tính Giờ (Hours):** Morning, Afternoon.
    *   **Tính OT:**
        *   Xác định giao thoa giữa (Giờ làm thực tế) và (Đề xuất OT đã duyệt).
        *   Lưu `ot_start_time`, `ot_end_time` dựa trên giao thoa này.
        *   Phân loại vào TC1/TC2/TC3 dựa trên `day_type`.
    *   **Tính Phạt:** Tính `late_minutes`, `early_minutes` và set `is_punished` dựa trên ân hạn (5p hoặc 65p thai sản).
    *   **Single Check-in (Check-in thiếu):** Áp dụng Hard Rule: Chỉ tính 1/2 công định mức, OT = 0.
    *   **Công Bù:** Tính `compensation_value`.

### Giai đoạn 3: Chiến Lược Chốt Trạng Thái (Status Finalization)

**Vấn đề:** Trạng thái (`status`) trong ngày phản ánh giá trị nhất thời. Cần chốt trạng thái cuối cùng để xác định vắng mặt hoặc quên chấm công.

1.  **Cơ chế hoạt động:**
    *   Sử dụng Scheduled Task (Celery Beat) chạy cố định vào lúc **17:30 hàng ngày**.

2.  **Logic thiết lập Status:**
    *   **Trạng thái mặc định (Đầu ngày):** Khi tạo mới bằng Batch Job, mặc định để trống. SRS quy định nếu chưa có log thì hiển thị rỗng.
    *   **Trong ngày (Real-time - Preview):**
        *   Chưa có log: Hiển thị rỗng.
        *   Có 1 log: `single_punch` (Màu vàng).
        *   Có 2 log: So sánh với ân hạn (5p/65p) để set `on_time` (Màu xanh) hoặc `not_on_time` (Màu vàng).
    *   **Tại thời điểm chốt (17:30 - Finalize):**
        *   Nếu không có Log nào: Chốt `absent` (Vắng mặt - Màu hồng).
        *   Nếu chỉ có 1 Log: Chốt `single_punch`. **Thực thi Hard Rule:** Gán công = 1/2 định mức ngày (0.5 hoặc 0.25), buộc Overtime = 0.
        *   Nếu đã có đủ 2 Log: Giữ nguyên trạng thái `on_time` hoặc `not_on_time` đã tính.

3.  **Sau khi chốt:**
    *   Vẫn cho phép cập nhật `TimeSheetEntry` nếu có phát sinh (Admin sửa, duyệt Khiếu nại). Khi đó `status` sẽ được tính toán lại dựa trên dữ liệu mới.

### Giai đoạn 4: Tổng Hợp & Migration
1.  **Cập nhật `EmployeeMonthlyTimesheet`:**
    *   Map lại logic tổng hợp theo tên trường mới (`tc*`).
    *   Tổng hợp thêm các trường phạt.
2.  **Migration:**
    *   Tạo file migration đổi tên trường (RenameField) để bảo toàn dữ liệu cũ.
    *   Thêm các trường mới.

---
