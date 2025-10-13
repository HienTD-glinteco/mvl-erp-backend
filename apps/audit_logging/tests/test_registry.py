"""
Tests for the AuditLogRegistry.
"""

import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.test import TestCase

from apps.audit_logging import AuditLogRegistry, audit_logging_register
from libs.models import create_dummy_model

User = get_user_model()


class TestAuditLogRegistry(TestCase):
    """Test cases for the AuditLogRegistry class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.TestModel = create_dummy_model(
            base_name="TestAuditLogRegistryModel",
            fields={
                "name": models.CharField(max_length=100),
                "value": models.IntegerField(default=0),
            },
        )

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

        DecoratedModel = create_dummy_model(
            base_name="TestAuditLogRegistryDecoratedModel",
            fields={"name": models.CharField(max_length=100)},
        )
        DecoratedModel = audit_logging_register(DecoratedModel)

        self.assertTrue(AuditLogRegistry.is_registered(DecoratedModel))

    def test_is_registered_returns_false_for_unregistered(self):
        """Test that is_registered returns False for unregistered models."""

        UnregisteredModel = create_dummy_model(
            base_name="UnregisteredModel",
            fields={"name": models.CharField(max_length=100)},
        )

        self.assertFalse(AuditLogRegistry.is_registered(UnregisteredModel))

    def test_get_all_models(self):
        """Test getting all registered models."""

        Model1 = create_dummy_model(base_name="Model1")
        Model1 = audit_logging_register(Model1)

        Model2 = create_dummy_model(base_name="Model2")
        Model2 = audit_logging_register(Model2)

        registered = AuditLogRegistry.get_all_models()
        self.assertEqual(len(registered), 2)
        self.assertIn(Model1, registered)
        self.assertIn(Model2, registered)

    def test_get_model_info(self):
        """Test getting information about a registered model."""

        # Create Meta class with verbose names
        meta_attrs = {
            "app_label": "audit_logging",
            "verbose_name": "Info Model",
            "verbose_name_plural": "Info Models",
        }
        meta_class = type("Meta", (), meta_attrs)

        InfoModel = type(
            f"InfoModel_{uuid.uuid4().hex}",
            (models.Model,),
            {"__module__": __name__, "Meta": meta_class},
        )
        InfoModel = audit_logging_register(InfoModel)

        info = AuditLogRegistry.get_model_info(InfoModel)

        self.assertIsNotNone(info)
        self.assertEqual(info["app_label"], "audit_logging")
        self.assertIn("infomodel", info["model_name"])
        self.assertEqual(info["verbose_name"], "Info Model")
        self.assertEqual(info["verbose_name_plural"], "Info Models")

    def test_get_model_info_returns_none_for_unregistered(self):
        """Test that get_model_info returns None for unregistered models."""

        UnregisteredModel = create_dummy_model(base_name="UnregisteredModel")

        info = AuditLogRegistry.get_model_info(UnregisteredModel)
        self.assertIsNone(info)

    def test_get_all_model_info(self):
        """Test getting information about all registered models."""

        Model1 = create_dummy_model(base_name="Model1")
        Model1 = audit_logging_register(Model1)

        Model2 = create_dummy_model(base_name="Model2")
        Model2 = audit_logging_register(Model2)

        all_info = AuditLogRegistry.get_all_model_info()

        self.assertEqual(len(all_info), 2)
        self.assertIn(Model1, all_info)
        self.assertIn(Model2, all_info)

    def test_get_content_type(self):
        """Test getting ContentType for a registered model."""

        CTModel = create_dummy_model(base_name="CTModel")
        CTModel = audit_logging_register(CTModel)

        content_type = AuditLogRegistry.get_content_type(CTModel)

        self.assertIsNotNone(content_type)
        self.assertIsInstance(content_type, ContentType)
        self.assertEqual(content_type.app_label, "audit_logging")
        self.assertIn("ctmodel", content_type.model.lower())

    def test_get_content_type_returns_none_for_unregistered(self):
        """Test that get_content_type returns None for unregistered models."""

        UnregisteredModel = create_dummy_model(base_name="UnregisteredModel")

        content_type = AuditLogRegistry.get_content_type(UnregisteredModel)
        self.assertIsNone(content_type)

    def test_clear_registry(self):
        """Test clearing the registry."""

        Model1 = create_dummy_model(base_name="Model1")
        Model1 = audit_logging_register(Model1)

        self.assertTrue(AuditLogRegistry.is_registered(Model1))

        AuditLogRegistry.clear()

        self.assertFalse(AuditLogRegistry.is_registered(Model1))
        self.assertEqual(len(AuditLogRegistry.get_all_models()), 0)

    def test_register_same_model_twice(self):
        """Test that registering the same model twice doesn't create duplicates."""

        TestModelTwice = create_dummy_model(base_name="TestModelTwice")

        AuditLogRegistry.register(TestModelTwice)
        AuditLogRegistry.register(TestModelTwice)

        self.assertEqual(len(AuditLogRegistry.get_all_models()), 1)
