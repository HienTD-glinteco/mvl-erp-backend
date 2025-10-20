def prepare_request_info(log_data: dict, request):
    # Get IP address
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(",")[0].strip()
    else:
        ip_address = request.META.get("REMOTE_ADDR")
    log_data["ip_address"] = ip_address

    # Get user agent
    log_data["user_agent"] = request.META.get("HTTP_USER_AGENT", "")

    # Get session key if available
    if hasattr(request, "session") and request.session.session_key:
        log_data["session_key"] = request.session.session_key


def prepare_user_info(log_data: dict, user=None):
    log_data["user_id"] = str(user.pk) if hasattr(user, "pk") else None
    log_data["username"] = getattr(user, "username", None) or getattr(user, "email", None) or str(user)

    # Add employee code, full name, and department if user has an associated employee record
    try:
        employee = user.employee
        log_data["employee_code"] = employee.code
        log_data["full_name"] = employee.fullname

        # Add department information
        if employee.department:
            log_data["department_id"] = str(employee.department.pk)
            log_data["department_name"] = employee.department.name
        else:
            log_data["department_id"] = None
            log_data["department_name"] = None

    except Exception:
        # User doesn't have an employee record or it's not accessible
        log_data["employee_code"] = ""
        log_data["full_name"] = ""
        log_data["department_id"] = None
        log_data["department_name"] = None
