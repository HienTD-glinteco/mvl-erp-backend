"""
Tests for the AuditLogRegistry.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.test import TestCase

from apps.audit_logging import AuditLogRegistry, audit_logging_register

User = get_user_model()


class TestAuditLogRegistry(TestCase):
    """Test cases for the AuditLogRegistry class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        class TestAuditLogRegistryModel(models.Model):
            name = models.CharField(max_length=100)
            value = models.IntegerField(default=0)

            class Meta:
                app_label = "audit_logging"

        cls.TestModel = TestAuditLogRegistryModel

    def setUp(self):
        """Set up test environment."""
        # Clear the registry before each test
        AuditLogRegistry.clear()

    def test_register_model(self):
        """Test registering a model manually."""

        AuditLogRegistry.register(self.TestModel)

        self.assertTrue(AuditLogRegistry.is_registered(self.TestModel))

    def test_register_via_decorator(self):
        """Test that decorator automatically registers models."""

        @audit_logging_register
        class TestAuditLogRegistryDecoratedModel(models.Model):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "audit_logging"

        self.assertTrue(AuditLogRegistry.is_registered(TestAuditLogRegistryDecoratedModel))

    def test_is_registered_returns_false_for_unregistered(self):
        """Test that is_registered returns False for unregistered models."""

        class UnregisteredModel(models.Model):
            name = models.CharField(max_length=100)

            class Meta:
                app_label = "audit_logging"

        self.assertFalse(AuditLogRegistry.is_registered(UnregisteredModel))

    def test_get_all_models(self):
        """Test getting all registered models."""

        @audit_logging_register
        class Model1(models.Model):
            class Meta:
                app_label = "audit_logging"

        @audit_logging_register
        class Model2(models.Model):
            class Meta:
                app_label = "audit_logging"

        registered = AuditLogRegistry.get_all_models()
        self.assertEqual(len(registered), 2)
        self.assertIn(Model1, registered)
        self.assertIn(Model2, registered)

    def test_get_model_info(self):
        """Test getting information about a registered model."""

        @audit_logging_register
        class InfoModel(models.Model):
            class Meta:
                app_label = "audit_logging"
                verbose_name = "Info Model"
                verbose_name_plural = "Info Models"

        info = AuditLogRegistry.get_model_info(InfoModel)

        self.assertIsNotNone(info)
        self.assertEqual(info["app_label"], "audit_logging")
        self.assertEqual(info["model_name"], "infomodel")
        self.assertEqual(info["verbose_name"], "Info Model")
        self.assertEqual(info["verbose_name_plural"], "Info Models")

    def test_get_model_info_returns_none_for_unregistered(self):
        """Test that get_model_info returns None for unregistered models."""

        class UnregisteredModel(models.Model):
            class Meta:
                app_label = "audit_logging"

        info = AuditLogRegistry.get_model_info(UnregisteredModel)
        self.assertIsNone(info)

    def test_get_all_model_info(self):
        """Test getting information about all registered models."""

        @audit_logging_register
        class Model1(models.Model):
            class Meta:
                app_label = "audit_logging"

        @audit_logging_register
        class Model2(models.Model):
            class Meta:
                app_label = "audit_logging"

        all_info = AuditLogRegistry.get_all_model_info()

        self.assertEqual(len(all_info), 2)
        self.assertIn(Model1, all_info)
        self.assertIn(Model2, all_info)

    def test_get_content_type(self):
        """Test getting ContentType for a registered model."""

        @audit_logging_register
        class CTModel(models.Model):
            class Meta:
                app_label = "audit_logging"

        content_type = AuditLogRegistry.get_content_type(CTModel)

        self.assertIsNotNone(content_type)
        self.assertIsInstance(content_type, ContentType)
        self.assertEqual(content_type.app_label, "audit_logging")
        self.assertEqual(content_type.model, "ctmodel")

    def test_get_content_type_returns_none_for_unregistered(self):
        """Test that get_content_type returns None for unregistered models."""

        class UnregisteredModel(models.Model):
            class Meta:
                app_label = "audit_logging"

        content_type = AuditLogRegistry.get_content_type(UnregisteredModel)
        self.assertIsNone(content_type)

    def test_clear_registry(self):
        """Test clearing the registry."""

        @audit_logging_register
        class Model1(models.Model):
            class Meta:
                app_label = "audit_logging"

        self.assertTrue(AuditLogRegistry.is_registered(Model1))

        AuditLogRegistry.clear()

        self.assertFalse(AuditLogRegistry.is_registered(Model1))
        self.assertEqual(len(AuditLogRegistry.get_all_models()), 0)

    def test_register_same_model_twice(self):
        """Test that registering the same model twice doesn't create duplicates."""

        class TestModelTwice(models.Model):
            class Meta:
                app_label = "audit_logging"

        AuditLogRegistry.register(TestModelTwice)
        AuditLogRegistry.register(TestModelTwice)

        self.assertEqual(len(AuditLogRegistry.get_all_models()), 1)
