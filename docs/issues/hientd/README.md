# Open Bug Issues - hien.trandoan@glinteco.com

This folder contains bug issues that are currently **OPEN** or **RE-OPEN** and assigned to hien.trandoan@glinteco.com.

## Summary

**Total: 17 tasks** (4 RE-OPEN + 13 OPEN) → **6 PRs**

---

## 📊 Phân nhóm Issues theo PR

### 🔴 PR 1: Timesheet Calculator - Tính số ngày công & trạng thái (10 issues)

> **Core issue:** Logic tính `working_days` và `status` trong bảng chấm công
>
> **Files liên quan:** `apps/hrm/services/timesheet_calculator.py`, `apps/hrm/models/attendance.py`

| # | Task ID | Title | Status | Mô tả ngắn |
|---|---------|-------|--------|------------|
| 1 | [86ew4zetx](./86ew4zetx-logic-nv-nghi-van-cham-cong.md) | NV nghỉ hưởng lương nhưng vẫn chấm công | 🟢 OPEN | NV được duyệt nghỉ nhưng có log CC → tính như đi làm |
| 2 | [86ew50mhq](./86ew50mhq-loi-ngay-tuong-lai-mien-cc.md) | Ngày tương lai NV miễn CC | 🟢 OPEN | Ngày làm bù tương lai hiển thị sai trạng thái |
| 3 | [86ew50tk2](./86ew50tk2-xoa-nv-mien-cham-cong.md) | Xóa NV miễn chấm công | 🟢 OPEN | Sau xóa, ngày công vẫn hiển thị "Đúng giờ" |
| 4 | [86ew54a72](./86ew54a72-trang-thai-ngay-khong-co-ca.md) | Ngày không có ca nhưng duyệt đề xuất | 🟢 OPEN | Ngày CN không có ca → số ngày công phải = 0 |
| 5 | [86ew54m1w](./86ew54m1w-so-ngay-cong-lam-bu.md) | Số ngày công ngày làm bù | 🟢 OPEN | Ngày làm bù + Vắng → số ngày công sai |
| 6 | [86ew56gt2](./86ew56gt2-xem-chi-tiet-cham-cong-ngay-le.md) | Số ngày công ngày lễ | 🟢 OPEN | Không hiển thị số ngày công cho ngày lễ |
| 7 | [86ew5cxen](./86ew5cxen-cap-nhat-trang-thai-sang-ngay-moi.md) | Cập nhật trạng thái sang ngày mới | 🟢 OPEN | NV không có log CC → không update "Vắng" |
| 8 | [86ew60rzf](./86ew60rzf-trang-thai-1-log-de-xuat.md) | Trạng thái 1 log + duyệt đề xuất | 🟢 OPEN | Chỉ có 1 log + được duyệt đề xuất → trạng thái sai |
| 9 | [86ew61yj8](./86ew61yj8-cong-sau-duyet-hau-thai-san.md) | Công sau duyệt hậu thai sản | 🟢 OPEN | Không cộng thêm 1 giờ công cho hậu thai sản |
| 10 | [86ew614qt](./86ew614qt-cong-thu-viec-chinh-thuc-hop-dong.md) | Công thử việc/chính thức sau đổi HĐ | 🟢 OPEN | Thay đổi HĐ → không update công thử/chính thức |
| 11 | [86evyq66n](./86evyq66n-duyet-de-xuat-nghi-phep.md) | **[MOVED]** Duyệt đề xuất nghỉ phép - working_days | 🔴 RE-OPEN | Nghỉ phép có lương: working_days = max |
| 12 | [86ew5yu1x](./86ew5yu1x-chi-tiet-ngay-cong-so-ngay-cong.md) | **[MOVED]** Số ngày công sau duyệt hậu thai sản | 🔴 RE-OPEN | working_days rỗng sau duyệt hậu thai sản |

---

### 🟠 PR 2: Đề xuất + Ngày công - Response API ~~(2 issues)~~ → MERGED TO PR1

> **⚠️ Các issues đã được move vào PR1** vì root cause liên quan đến `timesheet_calculator.py`
>
> ~~**Core issue:** API response sau khi duyệt đề xuất~~
>
> ~~**Files liên quan:** `apps/hrm/views/proposal.py`, `apps/hrm/serializers/working_day.py`~~

| # | Task ID | Title | Status | Note |
|---|---------|-------|--------|------|
| ~~1~~ | ~~[86evyq66n](./86evyq66n-duyet-de-xuat-nghi-phep.md)~~ | ~~Duyệt đề xuất nghỉ không lương/có lương~~ | - | **→ Moved to PR1 #11** |
| ~~2~~ | ~~[86ew5yu1x](./86ew5yu1x-chi-tiet-ngay-cong-so-ngay-cong.md)~~ | ~~Reload sau duyệt đề xuất~~ | - | **→ Moved to PR1 #12** |

---

### 🟡 PR 3: Dashboard Tuyển dụng (2 issues)

> **Core issue:** Biểu đồ dashboard module tuyển dụng
>
> **Files liên quan:** `apps/hrm/views/dashboard.py`, `apps/hrm/services/recruitment_dashboard.py`

| # | Task ID | Title | Status | Mô tả ngắn |
|---|---------|-------|--------|------------|
| 1 | [86ew3cqzd](./86ew3cqzd-chi-phi-tuyen-dung-binh-quan.md) | Chi phí tuyển dụng bình quân | 🔴 RE-OPEN | Chưa tính bình quân theo số ứng viên đã nhận việc |
| 2 | [86ew3h4bh](./86ew3h4bh-bieu-do-so-lieu-tuyen-moi.md) | Số liệu tuyển mới theo nguồn/kênh | 🟢 OPEN | Dữ liệu lấy lên chưa chính xác |

---

### 🟢 PR 4: Dashboard HRM - Chất lượng nhân sự (2 issues)

> **Core issue:** Biểu đồ chất lượng nhân sự cho quản lý
>
> **Files liên quan:** `apps/hrm/views/manager_dashboard.py`, `apps/hrm/services/hr_quality_report.py`

| # | Task ID | Title | Status | Mô tả ngắn |
|---|---------|-------|--------|------------|
| 1 | [86ew5cye2](./86ew5cye2-bc-chat-luong-nhan-su-chua-hien-thi.md) | BC chất lượng nhân sự | 🟢 OPEN | Không hiển thị dữ liệu cho TP HCNS |
| 2 | [86ew5da4f](./86ew5da4f-bieu-do-chat-luong-nhan-su-khoi-kd.md) | Biểu đồ chất lượng NS khối KD | 🟢 OPEN | Biểu đồ không hiển thị dữ liệu |

---

### 🔵 PR 5: Báo cáo tăng trưởng NS (1 issue)

> **Core issue:** Đếm trùng nhân viên nghỉ việc nhiều lần
>
> **Files liên quan:** `apps/hrm/services/growth_report.py`

| # | Task ID | Title | Status | Mô tả ngắn |
|---|---------|-------|--------|------------|
| 1 | [86ew457ta](./86ew457ta-bc-tang-truong-ns-nghi-nhieu-lan.md) | BC tăng trưởng NS đếm nhiều lần | 🟢 OPEN | NV nghỉ 2 lần → đếm 2 lần thay vì 1 |

---

### 🟣 PR 6: Audit Log Translation (1 issue)

> **Core issue:** Dịch nội dung audit log sang tiếng Việt
>
> **Files liên quan:** `apps/audit_logging/`

| # | Task ID | Title | Status | Mô tả ngắn |
|---|---------|-------|--------|------------|
| 1 | [86evq6gmy](./86evq6gmy-dich-noi-dung-audit-log.md) | Dịch nội dung audit log | 🔴 RE-OPEN | Dịch đối tượng + hiển thị thông tin thay đổi |

---

## 📈 Tổng kết theo PR

| PR | Tên | Issues | Độ ưu tiên | Status |
|----|-----|--------|------------|--------|
| **PR 1** | Timesheet Calculator | **12** | 🔴 **Cao nhất** | 📋 [PLAN](./PR1-TIMESHEET-CALCULATOR-PLAN.md) |
| ~~PR 2~~ | ~~Đề xuất + API Response~~ | ~~2~~ → 0 | - | ⤴️ Merged to PR1 |
| **PR 3** | Dashboard Tuyển dụng | 2 | 🟡 Trung bình | 📋 [PLAN](./PR3-RECRUITMENT-DASHBOARD-PLAN.md) |
| **PR 4** | Dashboard Chất lượng NS | 2 | 🟢 Trung bình | ⏳ Pending |
| **PR 5** | Báo cáo tăng trưởng | 1 | 🔵 Thấp | ⏳ Pending |
| **PR 6** | Audit Log | 1 | 🟣 Thấp | ⏳ Pending |

**Khuyến nghị:** Bắt đầu với **PR 1** vì có 12 issues liên quan đến cùng service `timesheet_calculator.py`.

---

## Attachments

All attachments are downloaded locally to the [attachments/](./attachments/) folder.

**Total attachments: 31 files**

| Task ID | Files |
|---------|-------|
| 86evq6gmy | 86evq6gmy-1.png, 86evq6gmy-2.png |
| 86evyq66n | 86evyq66n-1.png → 86evyq66n-6.png |
| 86ew3cqzd | 86ew3cqzd-1.png, 86ew3cqzd-2.png |
| 86ew3h4bh | 86ew3h4bh-1.png → 86ew3h4bh-4.png |
| 86ew457ta | 86ew457ta-1.png |
| 86ew4zetx | 86ew4zetx-1.png |
| 86ew50mhq | 86ew50mhq-1.png |
| 86ew50tk2 | 86ew50tk2-1.png |
| 86ew56gt2 | 86ew56gt2-1.png → 86ew56gt2-3.png |
| 86ew5cxen | 86ew5cxen-1.png |
| 86ew5cye2 | 86ew5cye2-1.png → 86ew5cye2-3.png |
| 86ew5da4f | 86ew5da4f-1.png, 86ew5da4f-2.png |
| 86ew5yu1x | 86ew5yu1x-1.png |
| 86ew61yj8 | 86ew61yj8-1.png |

---

*Generated on: 2026-01-13*
*Filter: Bug issues with OPEN/RE-OPEN status assigned to hien.trandoan@glinteco.com*
