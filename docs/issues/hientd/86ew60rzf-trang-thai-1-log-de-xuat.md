# Hiển thị không đúng trạng thái với ngày có 1 log chấm công và được duyệt đề xuất

| Property | Value |
|----------|-------|
| **Task ID** | 86ew60rzf |
| **Status** | Open |
| **Priority** | None |
| **Points** | 8 |
| **URL** | https://app.clickup.com/t/86ew60rzf |
| **Created** | 2026-01-12 |
| **Assignees** | Lê Sơn Duy, TD Hien |
| **Creator** | Lê Sơn Duy |
| **List** | Sprint 8 (7/1 - 20/1) |

## Description

**Flow:** Với ngày có ca làm việc và nhân viên chỉ có 1 lần chấm công, đồng thời ngày công nhân viên được duyệt 1 số đề xuất

**Reality:**
Với từng đề xuất, tại màn chi tiết ngày công, hệ thống hiển thị "Trạng thái" & "Số ngày công":
- Miễn trừ trễ: "Không đúng giờ" & rỗng
- Chế độ làm việc hậu thai sản: "Không đúng giờ" & rỗng
- Nghỉ thai sản: "Vắng" & 0
- Nghỉ không lương: "Vắng" & 0
- Nghỉ có lương: "Vắng" & 1

**Expected Outcome:**
Với tất cả các đề xuất, tại màn chi tiết ngày công hiển thị:
- Trạng thái (tại màn xem chi tiết): "Quên check-in/out"
- Trạng thái (tại màn danh sách bảng công): "Không đúng giờ"
- Số ngày công: = 1/2 số ngày công tối đa của ngày

**FYI:** Có thể hiểu là tính giá trị công và trạng thái giống như ngày không được duyệt đề xuất

## Clarification

**Các đề xuất ảnh hưởng đến cách tính:**
1. Miễn trừ trễ
2. Chế độ làm việc hậu thai sản
3. Nghỉ thai sản
4. Nghỉ không lương
5. Nghỉ có lương

**Lưu ý quan trọng:** Cần follow rule ưu tiên khi tính toán (Priority: `Attendance > Events > Proposals` - Thấp → Cao)

Với trường hợp **có 1 log chấm công + đề xuất được duyệt**:
- Các đề xuất trên **KHÔNG làm thay đổi** cách tính trạng thái và số ngày công
- Kết quả tính toán phải **giống như ngày không có đề xuất** (chỉ có 1 log)
- Trạng thái: "Quên check-in/out" (chi tiết) / "Không đúng giờ" (danh sách)
- Số ngày công: = 1/2 số ngày công tối đa của ngày

## Attachments

Không có attachments
