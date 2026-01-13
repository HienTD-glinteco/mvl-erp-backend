# Tính không đúng số ngày công của ngày làm bù

## Thông tin task

| Field | Value |
|-------|-------|
| **Task ID** | 86ew54m1w |
| **Status** | Open |
| **Priority** | - |
| **Points** | 8 |
| **Sprint** | Sprint 8 (7/1 - 20/1) |
| **List** | Sprint 8 (7/1 - 20/1) |
| **URL** | https://app.clickup.com/t/86ew54m1w |

## Assignees

- Lê Sơn Duy (duyleson76@gmail.com)
- TD Hien (hien.trandoan@glinteco.com)
- Nhung Nguyễn (nhungnguyen.neu.ktc@gmail.com)

## Mô tả

**Flow:** Tạo ngày làm bù (trong ảnh là ngày 28/12/2026)

**Reality:**
- Ngày làm bù nhân viên "Vắng" nhưng Số ngày công = 0

**Expected Outcome:**

Với ngày làm bù mà nhân viên "Vắng", số ngày công =

Nếu làm bù vào Chủ nhật:
- Số ngày công = -1 hoặc -0.5 phụ thuộc vào làm bù 1 hay 2 ca

Nếu làm bù vào Thứ bảy:
- Số ngày công = -0.5

TH trong ảnh, hệ thống cài đặt làm bù cả ngày chủ nhật 28/12/2025 nên số ngày công = -1

Số ngày công được cộng thêm tương ứng với số giờ nhân viên làm trong ngày

## Attachments

Không có attachments
