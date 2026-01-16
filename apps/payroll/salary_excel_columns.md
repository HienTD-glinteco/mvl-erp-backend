tôi cần formular cho những cột sau: (ở đây số 5 sau cột là ví dụ cho excel_row ví dụ V5 là dòng V cột 5)
cột A: STT, Fill data - index
cột B: Mã NV, fill data - employee_code
cột C: Họ và tên, fill data - employee_name
cột D: Phòng/Ban, fill data - department_name
cột E: Vị trí/chức danh, fill - position_name
cột F: Tình trạng HD, fill - employment_status
cột G: Nhân viên sale, fill - is_sale_employee (True/False)
cột H: Email, fill - employee_email
cột I: Doanh số, fill - sales_revenue
cột J: số giao dịch, fill - sales_transaction_count
cột K: Lương vị trí, fill - base_salary
cột L: ăn trưa, fill - lunch_allowance
cột M: điện thoại, fill - phone_allowance
cột N: công tác, fill - travel_expense_by_working_days
cột O: lương KPI, fill - kpi_salary
cột P: mức KPI, fill - kpi_grade
cột Q: lương đạt KPI, fill - kpi_bonus
cột R: thưởng doanh số, fill - business_progressive_salary
cột S: tổng, formular = K5+L5+M5+N5+O5+Q5+R5
cột T: ngày công tiêu chuẩn, fill - standard_working_days
cột U: ngày công thực tế, fill - total_working_days
cột V: ngày công thử việc, fill - probation_working_days
cột W: ngày công chính thức, fill - official_working_days
cột X: % lương thử việc, fill - net_percentage == 85 ? 0.85 : 1
cột Y: Thu nhập theo ngày công thực tế, formular = (W5*S5+V5*S5*X5)/T5
cột Z: làm thêm thứ 7 và trong tuần, fill - tc1_overtime_hours
cột AA: làm thêm chủ nhật, fill - tc2_overtime_hours
cột AB: làm thêm ngày lễ, fill - tc3_overtime_hours
cột AC: tổng giờ làm thêm, fill - total_overtime_hours
cột AD: đơn giá giờ lương (hourly_rate), formular =IF(F="PROBATION";S5*0.85/T5/8;S5/T5/8)
cột AE: Tổng tiền ngoài giờ tham chiếu, formular =(Z5*1.5+AA5*2+AB5*3)*AD5
cột AF: phụ cấp vượt tiến độ tham chiếu, formular =AE5-AH5
cột AG: số giờ làm thêm, formular =AC5
cột AH: Lương ngoài giờ chịu thuế, formular =AG5*AD5
cột AI: Lương ngoài giờ k chịu thuế, formular =IF(AF5>AH5*2;AH5*2;AE5-AH5)
cột AJ: tổng thu nhập, formular =Y5+AH5+AI5
cột AK: có đóng BHXH?, fill - has_social_insurance (True/False)
cột AL: Lương đóng BHXH, formular =IF(AK5=TRUE;K5;0)
cột AM: BHXH trích DN, formular =AL5*17% (% này lấy trong salary config)
cột AN: BHYT trích DN, formular =AL5*3% (% này lấy trong salary config)
cột AO: BH TNLĐ-BNN(0.5%) trích DN, formular =AL5*0.5% (% này lấy trong salary config)
cột AP: BHTN trích DN, formular =AL5*1% (% này lấy trong salary config)
cột AQ: Đoàn phí Công đoàn (2%) trích DN, formular =AL5*2% (% này lấy trong salary config)
cột AR: BHXH trích lương, formular =AL5*8% (% này lấy trong salary config)
cột AS: BHYT trích lương, formular =AL5*1.5% (% này lấy trong salary config)
cột AT: BHTN trích lương, formular =AL5*1% (% này lấy trong salary config)
cột AU: Đoàn phí Công đoàn (1%) trích lương, formular =AL5*1% (% này lấy trong salary config)
cột AV: mã số thuế, fill - tax_code
cột AW: Cách tính thuế, fill - tax_calculation_method (nhớ dùng gettext để translate)
cột AX: số người phụ thuộc, fill - dependent_count
cột AY: tổng giảm trừ, formular =11000000+AX5*4400000 (số tiền giảm trừ lấy trong salary config)
cột AZ: phụ cấp không tính thuế TNCN, formular =SUM(L5:M5)/T5*(V5*X5+W5)
cột BA: mức min khấu trừ 10%, fill - salary_period.salary_config_snapshot.personal_income_tax.minimum_flat_tax_threshold
cột BB: thu nhập tính thuế, formular:
   - nếu cột AW là "progressive" =IF(AJ5-SUM(AR5:AT5)-AY5-AI5-AZ5>0;AJ5-SUM(AR5:AT5)-AY5-AI5-AZ5;0)
   - nếu cột AW là "flat_10" điền =AJ5 (tổng thu nhập - gross)
   - nếu cột AW là "none" = 0
cột BC: Thuế TNCN, formular:
   - nếu cột AW là "progressive" =IF(BB5<=5000000;BB5*0.05;IF(BB5<=10000000;BB5*0.1-250000;IF(BB5<=18000000;BB5*0.15-750000;IF(BB5<=32000000;BB5*0.2-1650000;IF(BB5<=52000000;BB5*0.25-3250000;IF(BB5<=80000000;BB5*0.3-5850000;BB5*0.35-9850000))))))
   - nếu cột AW là "flat_10" điền =IF(BB5>=BA5;BB5*10%;0)
   - nếu cột AW là "none" = 0
cột BD: truy lĩnh, fill - back_pay_amount
cột BE: truy thu, fill - recovery_amount
cột BF: tổng lương, formular =ROUND(AJ5-SUM(AR5:AT5)-AU5+BD5-BE5-BC5;0)
cột BG: STK, fill - employee.default_bank_account.account_number or ""
