tôi cần formular cho những cột sau: (ở đây số 5 sau cột là ví dụ cho excel_row ví dụ V5 là dòng V cột 5)
cột A: STT, Fill data - index
cột B: Mã NV, fill data - employee_code
cột C: Họ và tên, fill data - employee_name
cột D: Phòng/Ban, fill data - department_name
cột E: Vị trí/chức danh, fill - position_name
cột F: Tình trạng HD, fill - employment_status
cột G: Email, fill - employee_email
cột H: Doanh số, fill - sales_revenue
cột I: Doanh số, fill - sales_transaction_count
cột J: Lương vị trí, fill - base_salary
cột K: ăn trưa, fill - lunch_allowance
cột L: điện thoại, fill - phone_allowance
cột M: công tác, fill - travel_expense_by_working_days
cột N: lương KPI, fill - kpi_salary
cột O: mức KPI, fill - kpi_grade
cột P: lương đạt KPI, fill - kpi_bonus
cột Q: thưởng doanh số, fill - business_progressive_salary
cột R: tổng, formular = J5+K5+L5+M5+N5+P5+Q5
cột S: ngày công tiêu chuẩn, fill - standard_working_days
cột T: ngày công thực tế, fill - total_working_days
cột U: ngày công thử việc, fill - probation_working_days
cột V: ngày công chính thức, fill - official_working_days
cột W: Thu nhập theo ngày công thực tế, formular = IF(E5="NVKD";(V5*R5+U5*R5)/S5;(V5*R5+U5*R5*0,85)/S5)
cột X: làm thêm thứ 7 và trong tuần, fill - tc1_overtime_hours
cột Y: làm thêm chủ nhật, fill - tc2_overtime_hours
cột Z: làm thêm ngày lễ, fill - tc3_overtime_hours
cột AA: tổng giờ làm thêm, fill - total_overtime_hours
cột AB: đơn giá giờ lương (hourly_rate), formular =IF(F5="Thử việc";R5*0,85/S5/8;R5/S5/8)
cột AC: Tổng tiền ngoài giờ tham chiếu, formular =(X5*150%+Y5*200%+Z5*300%)*AB5
cột AD: phụ cấp vượt tiến độ tham chiếu, formular =AC5-AF5
cột AE: số giờ làm thêm, formular =AA5
cột AF: Lương ngoài giờ chịu thuế, formular =AE5*AB5
cột AG: Lương ngoài giờ k chịu thuế, formular =IF(AD5>AF5*2;AF5*2;(AC5-AF5))
cột AH: tổng thu nhập, formular =W5+AF5+AG5
cột AI: Lương đóng BHXH, formular =IF(F5="Chính thức";J5;0)
cột AJ: BHXH trích DN, formular =AI5*17% (% này lấy trong salary config)
cột AK: BHYT trích DN, formular =AI5*3% (% này lấy trong salary config)
cột AL: BH TNLĐ-BNN(0,5%) trích DN, formular =AI5*0.5% (% này lấy trong salary config)
cột AM: BHTN trích DN, formular =AI5*1% (% này lấy trong salary config)
cột AN: Đoàn phí Công đoàn (2%) trích DN, formular =AI5*2% (% này lấy trong salary config)
cột AO: BHXH trích lương, formular =AI5*8% (% này lấy trong salary config)
cột AP: BHYT trích lương, formular =AI5*1.5% (% này lấy trong salary config)
cột AQ: BHTN trích DN, formular =AI5*1% (% này lấy trong salary config)
cột AR: Đoàn phí Công đoàn (1%) trích lương, formular =AI5*1% (% này lấy trong salary config)
cột AS: mã số thuế, fill - tax_code
cột AT: số người phụ thuộc, fill - dependent_count
cột AU: tổng giảm trừ, formular =11000000+AT5*4400000 (số tiền giảm trừ lấy trong salary config)
cột AV: phục cấp không tính thuế TNCN, formular =SUM(K5:L5)/S5*(U5*0,85+V5)
cột AW: thu nhập tính thuế, formular, cột F là chính thức, thì điền =IF(AH5-SUM(AO5:AQ5)-AU5-AG5-AV5>0;AH5-SUM(AO5:AQ5)-AU5-AG5-AV5;IF(AH5-SUM(AO5:AQ5)-AU5-AG5-AV5<0;0;0)), nếu cột F khác chính thức, điền   =AH5
cột AX: Thuế TNCN, formular, nếu cột F chính thức điền formular =IF(AW8<=5000000;AW8*0,05;IF(AW8<=10000000;AW8*0,1-250000;IF(AW8<=18000000;AW8*0,15-750000;IF(AW8<=32000000;AW8*0,2-1650000;IF(AW8<=52000000;AW8*0,25-3250000;IF(AW8<=80000000;AW8*0,3-5850000;AW8*0,35-9850000)))))), nếu cột F khác chính thức, điền formular =IF(AW9>=2000000;AW9*10%;0)
cột AY: truy lĩnh, fill - back_pay_amount
cột AZ: truy thu, fill - recovery_amount
cột BA: tổng lương, formular =ROUND(AH5-SUM(AO5:AQ5)-AR5+AY5-AZ5-AX5;0)
cột BB: STK, fill - employee.default_bank_account.account_number or ""

từ export trên thì cần cập nhật công thức tính cho personal_income_tax, trong trường hợp # Non-official employee: taxable_income_base = gross_income, tax = 10% thì phải check số tiền >= 2000000 thì mới tính 10% còn không thì là 0
