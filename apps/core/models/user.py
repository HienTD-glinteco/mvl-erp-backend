import random
import string
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from libs.base_model_mixin import BaseModel
from apps.core.querysets import UserManager


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    username = models.CharField(
        max_length=100, unique=True, verbose_name="Tên đăng nhập"
    )
    email = models.EmailField(unique=True, verbose_name="Email")
    phone_number = models.CharField(
        max_length=15, blank=True, null=True, verbose_name="Số điện thoại"
    )
    first_name = models.CharField(max_length=30, blank=True, verbose_name="Tên")
    last_name = models.CharField(max_length=30, blank=True, verbose_name="Họ")

    is_active = models.BooleanField(default=True, verbose_name="Hoạt động")
    is_staff = models.BooleanField(default=False, verbose_name="Nhân viên")
    date_joined = models.DateTimeField(
        default=timezone.now, verbose_name="Ngày tham gia"
    )

    # Login attempt tracking
    failed_login_attempts = models.IntegerField(
        default=0, verbose_name="Số lần đăng nhập thất bại"
    )
    locked_until = models.DateTimeField(
        null=True, blank=True, verbose_name="Khóa tài khoản đến"
    )

    # OTP fields
    otp_code = models.CharField(max_length=6, blank=True, verbose_name="Mã OTP")
    otp_expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="OTP hết hạn lúc"
    )
    otp_verified = models.BooleanField(default=False, verbose_name="OTP đã xác thực")

    # Session management
    active_session_key = models.CharField(
        max_length=255, blank=True, verbose_name="Phiên hoạt động"
    )

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"
        db_table = "core_user"

    def __str__(self):
        return f"{self.username} - {self.get_full_name()}"

    def get_full_name(self):
        return f"{self.last_name} {self.first_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_locked(self):
        """Check if account is currently locked"""
        if self.locked_until:
            return timezone.now() < self.locked_until
        return False

    def lock_account(self):
        """Lock account for 5 minutes after 5 failed attempts"""
        self.locked_until = timezone.now() + timedelta(minutes=5)
        self.save(update_fields=["locked_until"])

    def unlock_account(self):
        """Unlock account and reset failed login attempts"""
        self.failed_login_attempts = 0
        self.locked_until = None
        self.save(update_fields=["failed_login_attempts", "locked_until"])

    def increment_failed_login(self):
        """Increment failed login attempts and lock if necessary"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.lock_account()
        else:
            self.save(update_fields=["failed_login_attempts"])

    def generate_otp(self):
        """Generate a new OTP code valid for 5 minutes"""
        self.otp_code = "".join(random.choices(string.digits, k=6))
        self.otp_expires_at = timezone.now() + timedelta(minutes=5)
        self.otp_verified = False
        self.save(update_fields=["otp_code", "otp_expires_at", "otp_verified"])
        return self.otp_code

    def invalidate_all_sessions(self):
        """Invalidate all user sessions after password change"""
        # Clear the active session key to force logout
        self.active_session_key = ""
        self.save(update_fields=["active_session_key"])

    def verify_otp(self, otp_code):
        """Verify OTP code"""
        if not self.otp_code or not self.otp_expires_at:
            return False

        if timezone.now() > self.otp_expires_at:
            return False

        if self.otp_code == otp_code:
            self.otp_verified = True
            self.unlock_account()  # Reset failed attempts on successful login
            self.save(
                update_fields=["otp_verified", "failed_login_attempts", "locked_until"]
            )
            return True

        return False

    def clear_otp(self):
        """Clear OTP data after successful verification"""
        self.otp_code = ""
        self.otp_expires_at = None
        self.otp_verified = False
        self.save(update_fields=["otp_code", "otp_expires_at", "otp_verified"])
