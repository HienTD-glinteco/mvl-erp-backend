# TÀI LIỆU QUY TẮC NGHIỆP VỤ: TÍNH TOÁN VÀ LƯU TRỮ NGÀY CÔNG (WORKING DAY)

**Phiên bản:** 3.1 (Cập nhật Priority Rule & logic hoàn phép)
**Mục đích:** Chuẩn hóa logic xử lý dữ liệu chấm công thô thành dữ liệu tính lương (Snapshot Data).

* * *

## 1\. Nguồn Dữ Liệu & Tham Chiếu UC

| Nguồn Dữ Liệu | Mã UC (SRS) | Ghi chú |
| ---| ---| --- |
| Hợp đồng lao động | UC 7.2.4, UC 7.2.5 | Lấy `% Thực nhận` (85/100) và `Ngày hiệu lực` để xác định loại công. |
| Phụ lục hợp đồng | UC 7.3.3, UC 7.3.4 | Ghi đè thông tin lương/hợp đồng nếu có hiệu lực mới hơn. |
| Lịch làm việc | UC 6.4.1 | Cấu hình ca làm việc (Sáng/Chiều), giờ chuẩn (08:00-17:30). |
| Ngày Lễ | UC 6.5.1, UC 6.5.2 | Định nghĩa các ngày nghỉ được hưởng nguyên lương. |
| Ngày làm bù | UC 6.5.3 | Biến ngày nghỉ (T7/CN) thành ngày làm việc và ngược lại. |
| Dữ liệu Chấm công | UC 6.6.3 | Log Check-in/Check-out thực tế từ máy chấm công/Wifi/GPS. |
| Đề xuất (Proposals) | Phân hệ 9 | Các đề xuất Nghỉ phép, OT, Công tác, Miễn trừ trễ... |

* * *
## 2\. Logic Xác Định "Khung Ngày Công Chuẩn" (Standard Framework)
Trước khi tính toán, hệ thống phải xác định ngày hôm đó nhân viên **được giao** làm gì để xác định `day_type`.
**Quy tắc:** Mỗi ca làm việc chuẩn = **4 giờ**.
*   **Ca Sáng:** 08:00 - 12:00.
*   **Ca Chiều:** 13:30 - 17:30.
### Kịch bản 1: Ngày làm việc tiêu chuẩn (Thứ 2 - Thứ 6)
*   **UC tham chiếu:** UC 6.6.1.1
*   **Cấu hình:** 2 Ca (Sáng + Chiều).
*   **Định mức (`working_days` Max):** `1.0`.
*   **Loại ngày (`day_type`):** `null` (Để trống - ngày thường không có day_type đặc biệt).
### Kịch bản 2: Ngày làm việc ngắn (Thường là Thứ 7)
*   **UC tham chiếu:** UC 6.6.1.1
*   **Cấu hình:** 1 Ca (Sáng hoặc Chiều).
*   **Định mức (`working_days` Max):** `0.5`.
*   **Loại ngày (`day_type`):** `null` (Để trống - ngày thường không có day_type đặc biệt).
* * *
## 3\. Chi Tiết Logic Tính Toán Giá Trị Công (Complex Calculation)
### 3.1. Tính Thời Gian Làm Việc Thực Tế (Official Hours)
**UC tham chiếu:** **UC 6.6.1.2** (Quy tắc tính số giờ), **UC 6.6.4** (Admin sửa), **UC 6.8.4** (Duyệt khiếu nại)
**Đầu vào:**
*   `T_In`: Giờ bắt đầu (`start_time`). Ưu tiên: Admin/Khiếu nại > Log Máy chấm công.
*   `T_Out`: Giờ kết thúc (`end_time`). Ưu tiên: Admin/Khiếu nại > Log Máy chấm công.
*   `Ca_Sáng_Start` (08:00), `Ca_Sáng_End` (12:00).
*   `Ca_Chiều_Start` (13:30), `Ca_Chiều_End` (17:30).
**Thuật toán từng bước:**
1. **Bước 1: Xác định khung thời gian thực tế**
    *   Sử dụng `start_time` và `end_time` (đã qua xử lý ưu tiên) làm mốc.
    *   **Lưu ý:** Hệ thống KHÔNG clamp (cắt) thời gian, mà sử dụng **intersection logic** để tính giờ làm thực tế trong từng ca.
2. **Bước 2: Tính giờ làm Ca Sáng (Intersection)**
    *   Nếu không có check-in/out trong khung sáng -> `H_Sáng` = 0.
    *   Ngược lại:
        *   `Start_S` = Max(`start_time`, 08:00).
        *   `End_S` = Min(`end_time`, 12:00).
        *   Nếu `Start_S` < `End_S`: `H_Sáng` = `End_S` - `Start_S`.
        *   Ngược lại: `H_Sáng` = 0.
3. **Bước 3: Tính giờ làm Ca Chiều (Intersection)**
    *   Tương tự:
        *   `Start_C` = Max(`start_time`, 13:30).
        *   `End_C` = Min(`end_time`, 17:30).
        *   Nếu `Start_C` < `End_C`: `H_Chiều` = `End_C` - `Start_C`.
        *   Ngược lại: `H_Chiều` = 0.
4. **Bước 4: Tổng hợp & Làm tròn**
    *   `official_hours` = `H_Sáng` + `H_Chiều`.
    *   `working_days` (Raw) = `official_hours` / 8
### 3.2. Xử lý "Check-in Thiếu" (Single Check-in Logic)
**UC tham chiếu:** **UC 6.6.3.2** (Mục 13)
*   **Logic Tính Công (****`working_days`****):**
    *   Nếu chỉ có 1 log chấm công (hoặc `start_time` hoặc `end_time` bị Null/Không hợp lệ):
    *   **Gán cứng (Force Set):** `working_days` = 1/2 Giá trị Định mức của ngày hôm đó.
        *   Ngày 2 Ca (Định mức 1.0) -> `working_days` = **0.5**.
        *   Ngày 1 Ca (Định mức 0.5) -> `working_days` = **0.25**.
*   **Logic Tính OT (Hard-Rule):**
    *   `overtime_hours` = 0: Trong mọi trường hợp chỉ có 1 lần chấm công, hệ thống mặc định ghi nhận 0 giờ OT, bất kể có đề xuất được duyệt hay không.
    *   _Lý do:_ Không đủ dữ liệu đối soát. Yêu cầu nhân viên khiếu nại bổ sung công.
        *   Backend lưu thông tin giờ vào giờ ra riêng cho OT, trước mắt tự động tính, sau này cho HR sửa sau thì sửa API thôi
### 3.3. Xử lý Đi muộn / Về sớm (Penalty Logic)
**UC tham chiếu:** **UC 6.6.1.3** Cần phân biệt rõ giữa việc **Tính công** (trừ lương theo giờ) và **Xác định lỗi** (phạt chuyên cần).
1. **Xác định Ân hạn:**
    *   Mặc định: **5 phút**.
    *   Hậu thai sản: **65 phút**. (Bao gồm 60 phút theo luật định + 5 phút theo cấu hình công ty). Áp dụng cho cả ngày có **1 ca hoặc 2 ca** làm việc.
    *   Miễn trừ trễ (UC 9.5): Theo số phút duyệt.
2. **Tính toán:**
    *   **Tính công:** Trừ trực tiếp vào `official_hours` mọi phút đi muộn/về sớm (không áp dụng ân hạn).
    *   **Xác định lỗi (****`is_punished`****):** True nếu `(late_minutes + early_minutes) > Ân hạn`.
### 3.4. Logic Kích Hoạt Tính Toán (is_finalizing)
**Mục đích:** Tránh tính toán sai cho các ngày chưa kết thúc (nhân viên vẫn đang làm việc).

**Quy tắc:** Hệ thống CHỈ tính toán `official_hours`, `overtime_hours`, `working_days`, và các field liên quan khi thỏa mãn một trong các điều kiện sau:

1. **Ngày đã qua (Past Date):**
   - Nếu `entry.date < today` → Luôn tính toán (ngày đã kết thúc).

2. **Ngày hôm nay đã hết giờ làm việc:**
   - Nếu `entry.date == today` VÀ `current_time >= schedule_end_time` → Kích hoạt tính toán.
   - `schedule_end_time` lấy từ `WorkSchedule.afternoon_end_time` (thường là 17:30).

**Chế độ Preview (is_finalizing = False):**
- Áp dụng cho ngày tương lai hoặc ngày hôm nay chưa hết giờ.
- `working_days` = `null` (chưa xác định).
- `status` = `null` hoặc `NOT_ON_TIME` (nếu chỉ có single punch).
- Không tính `calculate_hours()`, `calculate_overtime()`, `calculate_penalties()`.

**Chế độ Finalized (is_finalizing = True):**
- Áp dụng khi ngày đã kết thúc hoặc entry được sửa thủ công.
- Tính toán đầy đủ tất cả các field.
- `status` có thể là `ABSENT` nếu không có chấm công.
* * *
## 4\. Xử Lý Các Loại Đề Xuất & Sự Kiện Đặc Biệt
### 4.1. Ngày Làm Bù (Compensation Day)
**UC tham chiếu:** **UC 6.5.3**
Ngày làm bù được coi là ngày "trả nợ" cho ngày Lễ đã nghỉ trước đó.
*   **Nguyên tắc:** `compensation_value` = `working_days` (Thực tế) - `working_days` (Định mức).
*   **Các kịch bản:**
    *   Đi làm đủ (Ngày định mức 1.0): `1.0 - 1.0 = 0` (Đã bù xong).
    *   Nghỉ không làm (Ngày định mức 1.0): `0 - 1.0 = -1.0` (Nợ công).
    *   Đi làm thiếu giờ: Sẽ ra số âm lẻ (Ví dụ: `-0.12`).
*   **Lưu trữ:** Lưu vào trường `compensation_value`.
### 4.2. Làm Việc Thêm Giờ (Overtime - OT)
**UC tham chiếu:** **UC 9.4**
Hệ thống lưu trữ độc lập **Giá trị ngày công (****`working_days`** **<= 1.0)** và **Giờ OT** (không giới hạn). OT không bao giờ được cộng dồn vào `working_hours` để làm tăng công chuẩn.
**Quy tắc tính toán:**
1. **Cửa sổ thời gian (Overlap):** Giờ OT = Khoảng thời gian giao nhau giữa `[Start_OT, End_OT]` (trên đề xuất đã duyệt) và `[start_time, end_time]` (thực tế).
2. **Giới hạn:** Mọi thời gian làm việc nằm ngoài khung giờ đã duyệt sẽ không được tính.
3. **Hard-Rule:** Nếu chỉ chấm công 1 lần trong ngày -> `OT = 0`.
*   **Phân loại:**
    *   `ot_tc1_hours`: Ngày thường (Bao gồm thứ 7) & Ngày làm bù.
    *   `ot_tc2_hours`: Ngày nghỉ tuần (Chủ nhật).
    *   `ot_tc3_hours`: Ngày lễ.
*   **Tổng hợp:** `overtime_hours` = TC1 + TC2 + TC3.
### 4.3. Miễn Chấm Công (Exempt)
**UC tham chiếu:** **UC 6.7.1**
*   **Logic:** `working_days` = Max định mức. `is_exempt` = True.
### 4.4. Chế độ Hậu Thai Sản (Post-Maternity)
**UC tham chiếu:** **UC 9.6**, **UC 6.6.3.2** (Mục 13)
**Logic:**
*   **Điều kiện:** Có đề xuất "Chế độ hậu thai sản" hiệu lực và nhân viên có chấm công ít nhất 2 lần/ngày.
*   **Quyền lợi:**
    1. **Cộng bù công:** Bất kể ngày có **1 ca hay 2 ca** làm việc, hệ thống đều cộng thêm **1 giờ làm việc** (tương đương 0.125 công) vào tổng thời gian làm thực tế.
    2. **Miễn phạt:** Áp dụng mức ân hạn **65 phút** cho việc xác định lỗi vi phạm chuyên cần, bất kể ngày làm việc đó có **1 ca hay 2 ca**.
*   **Giới hạn:** `working_days` = Min(`working_days` + 0.125, `Max định mức`).
    *   _Ví dụ:_ Ngày Thứ 7 (định mức 0.5), nhân viên làm 3 giờ thực tế (0.375) -> Cộng 1 giờ thành 4 giờ -> Đạt đủ **0.5 công**.
* * *
## 5\. Thứ Tự Ưu Tiên Dữ Liệu (Priority Rule)

### 5.1. Nguyên tắc chung
```
Đề xuất (Proposal) < Sự kiện (Events) < Lịch sử chấm công (Attendance)
```

| Layer | Ví dụ | Ý nghĩa |
|-------|-------|---------|
| Đề xuất | Xin nghỉ phép, WFH, OT | Kế hoạch - có thể thay đổi |
| Sự kiện | Thay đổi HĐ, miễn CC | Thực tế đã xảy ra |
| Chấm công | Log check-in/out | Bằng chứng đi làm |

### 5.2. Quy tắc xử lý xung đột

| Trường hợp | Xử lý | Kết quả |
|------------|-------|---------|
| Nghỉ phép + Có chấm công | Attendance wins | Tính công bình thường |
| Nghỉ phép CÓ LƯƠNG + Có CC | Clear absent_reason | Phép tự động hoàn |
| Nghỉ phép KHÔNG lương + Có CC | Clear absent_reason | Tính công bình thường |

### 5.3. Cơ chế hoàn phép tự động

Khi nhân viên có đề xuất nghỉ phép được duyệt nhưng vẫn đi làm:

1. `TimesheetCalculator` phát hiện có attendance logs
2. Xóa `absent_reason` khỏi entry
3. Khi `EmployeeMonthlyTimesheet.refresh_for_employee_month()` chạy:
   - `consumed_leave_days` = COUNT(absent_reason = PAID_LEAVE)
   - Entry không còn PAID_LEAVE → không bị count
   - `remaining_leave_days` tự động tăng
4. **Kết quả:** Phép được hoàn mà không cần xử lý riêng

## 6\. Ma Trận Ưu Tiên Dữ Liệu (Legacy Conflict Handling)
Khi một buổi làm việc có nhiều loại dữ liệu chồng lấn, áp dụng thứ tự ưu tiên sau để đạt **Giá trị tối đa được hưởng**:

| Loại dữ liệu chồng lấn | Ưu tiên tính Công | Giải thích |
| ---| ---| --- |
| Lễ trùng ngày nghỉ (chủ nhật) | Ngày nghỉ (Chủ nhật) | `day_type` = Trống. `working_days` = 0. |
| Đi làm trùng ngày Phép | Chấm công | Tính công bình thường, xóa absent_reason, phép tự động hoàn |
| Làm bù trùng Nghỉ phép | Nghỉ phép (P) | Dùng P để triệt tiêu giá trị âm của ngày làm bù (`1.0 - 1.0 = 0`). |
| Miễn trừ trễ trùng Đi muộn | Miễn trừ | Không đánh dấu lỗi (`is_punished` = False), nhưng công vẫn trừ theo phút thực tế. |

* * *
## 7\. Cấu Trúc Dữ Liệu Lưu Trữ "Snapshot" (TimeSheetEntry)
Bảng ngày công (`hrm_timesheet`) cần lưu trữ giá trị tĩnh tại thời điểm tính. Các field cần tuân thủ convention của model `TimeSheetEntry`.

| Field Name | Data Type | Logic / Nguồn Dữ Liệu | Mapping với TimeSheetEntry |
| ---| ---| ---| --- |
| Định danh |  |  |  |
| `date` | Date | Ngày ghi nhận | `date` |
| `employee_id` | Long | ID Nhân viên | `employee` |
| `contract_id` | Long | Snapshot: ID Hợp đồng/Phụ lục đang hiệu lực. | `contract` (ForeignKey) |
| Phân loại Ngày |  |  |  |
| `day_type` | String | Loại ngày: `null` (ngày thường), `holiday`, `compensatory`. | `day_type` |
| `count_for_payroll` | Boolean | Có tính lương không? (Dựa trên loại HĐ/Nhân viên). | `count_for_payroll` |
| `is_manually_corrected` | Boolean | Có phải do Admin sửa thủ công không? | `is_manually_corrected` |
| Giá trị Công |  |  |  |
| `working_days` | Decimal | Giá trị công tính lương (Max 1.0 hoặc 0.5). Không bao gồm OT. | `working_days` |
| `official_hours` | Decimal | Tổng số giờ làm việc chính thức (Sáng + Chiều). | `official_hours` |
| `compensation_value` | Decimal | Mới: Giá trị công ngày làm bù (thường âm hoặc bằng 0). | `compensation_value` |
| Phân loại Lương (Snapshot) |  |  |  |
| `net_percentage` | Int | Snapshot: Tỷ lệ hưởng lương (85 hoặc 100). | `net_percentage` |
| `is_full_salary` | Boolean | True nếu hưởng 100% lương (Mapping từ net_percentage). | `is_full_salary` |
| Chi tiết Nghỉ & Lễ |  |  |  |
| `paid_leave_hours` | Decimal | Số giờ nghỉ phép có lương quy đổi. | `paid_leave_hours` |
| OT & Vi phạm |  |  |  |
| `overtime_hours` | Decimal | Tổng số giờ OT (TC1 + TC2 + TC3). | `overtime_hours` |
| `ot_tc1_hours` | Decimal | Giờ OT hệ số 1.5 (Ngày thường & Làm bù). | `ot_tc1_hours` |
| `ot_tc2_hours` | Decimal | Giờ OT hệ số 2.0 (Ngày nghỉ tuần). | `ot_tc2_hours` |
| `ot_tc3_hours` | Decimal | Giờ OT hệ số 3.0 (Ngày lễ). | `ot_tc3_hours` |
| `late_minutes` | Int | Phút đi muộn thực tế (dùng để trừ công). | `late_minutes` |
| `early_minutes` | Int | Phút về sớm thực tế (dùng để trừ công). | `early_minutes` |
| `is_punished` | Boolean | Mới: Có bị phạt chuyên cần hay không (xét theo ân hạn). | `is_punished` |
| Trạng thái |  |  |  |
| `status` | String | Mã trạng thái: `on_time`, `not_on_time`, `single_punch`, `absent`. | `status` |
| `is_exempt` | Boolean | True nếu thuộc diện Miễn chấm công. | `is_exempt` |

* * *
### 7.1. Chi tiết Logic Mapping & Tính toán Field
Dưới đây là công thức cụ thể để populate (điền dữ liệu) cho từng field trong quá trình xử lý (ETL/Calculation Job):
#### Nhóm 1: Field Định danh & Phân loại
*   **`contract_id`**:
    *   Query bảng `Contract` và `ContractAppendice`.
    *   Lấy ID của bản ghi có `effective_date <= current_date` và `expiration_date >= current_date` (hoặc null).
    *   Ưu tiên Phụ lục mới nhất > Hợp đồng gốc.
*   **`day_type`**:
    *   Check danh sách `Holidays` -> Nếu có: `holiday`.
    *   Check danh sách `CompensatoryDays` -> Nếu có: `compensatory`.
    *   Còn lại: `null` (để trống cho ngày thường).
*   **`count_for_payroll`**:
    *   Lấy từ `Employee.type`.
    *   Nếu là: `Chính thức`, `Thử việc` , `Học việc` , `Thực tập sinh` , `Thử việc loại 1` > `True`.
    *   Nếu là: `Không lương chính thức` \`, `Không lương thử việc` \` -> `False`.
#### Nhóm 2: Field Giá trị Công (Core Value)
*   **`official_hours`**:
    *   `Sum(Morning_Hours + Afternoon_Hours)` (đã qua xử lý logic vào/ra ở Mục 3.1).
        *   NOTE: `Morning_Hours, Afternoon_Hours` đã xử lý chuẩn, và phản ánh đúng thời gian đi làm thực tế.
*   **`working_days`**:
    *   Công thức: `(official_hours / 8) + (các khoản bù khác như phép, lễ...)`.
    *   Cộng bù 0.5/0.25 nếu Single Check-in.
    *   Cộng bù 0.125 nếu Hậu thai sản.
    *   **Max Cap:** Không vượt quá định mức ngày (1.0 hoặc 0.5).
*   **`compensation_value`**:
    *   Chỉ tính nếu `day_type == compensatory`.
    *   `= working_days (Thực tế) - working_days (Định mức)`.
#### Nhóm 3: Field Lương & Chế độ
*   **`net_percentage`**:
    *   Lấy từ `Contract.net_percentage` hoặc `ContractType.net_percentage`.
    *   Thường là `85` hoặc `100`.
*   **`is_full_salary`**:
    *   `True` nếu `net_percentage == 100`. `False` nếu khác.
*   **`paid_leave_hours`**:
    *   Tổng giờ của các đề xuất `PaidLeave` (P, P/2) đã duyệt trong ngày.
#### Nhóm 4: Field OT & Vi phạm
*   **`late_minutes`** **/** **`early_minutes`**:
    *   Tính toán dựa trên chênh lệch giữa Log thực tế và Khung giờ chuẩn.
    *   **Không** áp dụng trừ ân hạn ở bước này (lưu giá trị thực).
*   **`is_punished`**:
    *   `True` nếu `(late_minutes + early_minutes) > Grace_Period`.
*   **`ot_tc1_hours`**:
    *   Overlap(Log, Đề xuất OT) nếu ngày là ngày thường (bao gồm thứ 7) hoặc `compensatory`.
    *   **Lưu ý:** `day_type = null` hoặc `day_type = compensatory`.
*   **`ot_tc2_hours`**:
    *   Overlap(Log, Đề xuất OT) nếu ngày là Chủ nhật và `day_type != compensatory`.
*   **`ot_tc3_hours`**:
    *   Overlap(Log, Đề xuất OT) nếu `day_type == holiday`.
* * *
## 8\. Luồng Dữ Liệu & Trigger (Data Flow)
### 8.1. Input & Output
*   **Input (Đầu vào):**
    1. **Static Data:** Cấu hình Lịch làm việc, Ngày lễ, Ngày làm bù.
    2. **HR Data:** Hợp đồng, Phụ lục hợp đồng, Hồ sơ nhân viên.
    3. **Dynamic Data:** Log chấm công, Các Đề xuất đã duyệt (OT, Leave, Exempt...).
*   **Output (Đầu ra cho Payroll):**
    *   Payroll **KHÔNG** đọc trực tiếp từ `TimeSheetEntry`.
    *   `TimeSheetEntry` sau khi tính toán xong sẽ đẩy dữ liệu tổng hợp sang **`EmployeeMonthlyTimesheet`**.
    *   Payroll Service sẽ sử dụng `EmployeeMonthlyTimesheet` làm nguồn dữ liệu đầu vào duy nhất.
### 8.2. Luồng Tạo Mới (Create Flow)
1. **Batch Job Hàng Tháng (****`prepare_monthly_timesheets`****):**
    *   **Thời điểm:** Chạy vào đầu tháng (VD: 00:00 ngày mùng 1).
    *   **Đối tượng:** Tất cả nhân viên có trạng thái `ACTIVE` hoặc `ONBOARDING`.
    *   **Hành động:** Tạo sẵn các record `TimeSheetEntry` cho từng ngày trong tháng. Tính toán ngay lập tức các giá trị Snapshot (contract\_id, wage\_rate, day\_type) dựa trên dữ liệu hiện có.
2. **Ad-hoc Trigger (Nhân sự mới/Active lại):**
    *   **Sự kiện:** Khi tạo mới nhân viên hoặc chuyển từ 1 trong các trạng thái sau \[`Resigned`, `Maternity Leave`, `Unpaid Leave`\] -> `Active`.
    *   **Hành động:** Trigger chạy job tạo `TimeSheetEntry` cho tháng hiện tại.
### 8.3. Luồng Cập Nhật (Update Flow)
Nguyên tắc: **Real-time Recalculation & Propagation**.
1. **Trigger Update** **`TimeSheetEntry`****:**
    *   Khi Log chấm công thay đổi.
    *   Khi Đề xuất Khiếu nại chấm công được duyệt.
    *   Khi Hợp đồng thay đổi (Update lại Snapshot).
    *   Khi Admin sửa thủ công (Update bằng `is_manually_corrected`).
2. **Trigger Update** **`EmployeeMonthlyTimesheet`****:**
    *   Mỗi khi `TimeSheetEntry` được `save()`, hệ thống sẽ kích hoạt job (hoặc signal) để tính toán lại Aggregate cho tháng tương ứng.
    *   Cập nhật các cột tổng (Total Working Days, Total OT, Leave Balance) trong `EmployeeMonthlyTimesheet`.
* * *
## 9\. Cấu Trúc Tổng Hợp Tháng (EmployeeMonthlyTimesheet)
Đây là bảng Input trực tiếp cho Module Tính Lương.
### 9.1. Logic Mapping Field

| Field (Monthly) | Logic Tổng Hợp (Aggregation) |
| ---| --- |
| Công Hưởng Lương |  |
| `probation_working_days` | `Sum(working_days)` WHERE `is_full_salary = False` |
| `official_working_days` | `Sum(working_days)` WHERE `is_full_salary = True` |
| `total_working_days` | `probation_working_days` + `official_working_days` |
| Giờ OT (Chi tiết) |  |
| `overtime_hours` | `Sum(overtime_hours)` |
| `tc1_overtime_hours` | `Sum(ot_tc1_hours)` (Mapping TC1 vào đây) |
| `tc2_overtime_hours` | `Sum(ot_tc2_hours)` (Mapping TC2 vào đây) |
| `tc3_overtime_hours` | `Sum(ot_tc3_hours)` (Mapping TC3 vào đây) |
| Nghỉ phép |  |
| `paid_leave_days` | `Sum(paid_leave_hours) / 8` (Quy đổi ra ngày) |
| Vi phạm |  |
| `late_coming_minutes` | `Sum(late_minutes)` (New Field - Cần thêm vào Model) |
| `early_leaving_minutes` | `Sum(early_minutes)` (New Field - Cần thêm vào Model) |
| `total_penalty_count` | `Count(date)` WHERE `is_punished = True` (New Field) |

### 9.2. Yêu cầu update Model `EmployeeMonthlyTimesheet`
Hiện tại Model đang thiếu các field phạt chuyên cần để phục vụ trừ lương. Cần bổ sung:
*   `late_coming_minutes` (Integer/Decimal)
*   `early_leaving_minutes` (Integer/Decimal)
*   `total_penalty_count` (Integer) - Số lần vi phạm để xét thưởng/phạt.
