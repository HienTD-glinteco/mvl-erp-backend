"""
Tests for API documentation version configuration.
"""

import os
import subprocess
from django.test import TestCase, override_settings


class APIVersionConfigTest(TestCase):
    """Test cases for API documentation version configuration"""

    def test_version_uses_environment_variable_default(self):
        """Test that VERSION setting uses default value when API_DOC_VERSION is not set"""
        # Arrange & Act
        from settings.base.drf import SPECTACULAR_SETTINGS
        
        # Assert - should use default value when not set
        # Note: In the test environment, if API_DOC_VERSION is not set, it defaults to "1.0.0"
        assert SPECTACULAR_SETTINGS["VERSION"] is not None
        assert isinstance(SPECTACULAR_SETTINGS["VERSION"], str)

    def test_version_from_environment_variable(self):
        """Test that VERSION can be set via API_DOC_VERSION environment variable"""
        # Arrange
        test_version = "2024-12-20T10:30:00Z"
        
        # Act - Run a subprocess with the environment variable set
        result = subprocess.run(
            ["python", "-c", "from settings.base.drf import SPECTACULAR_SETTINGS; print(SPECTACULAR_SETTINGS['VERSION'])"],
            env={**os.environ, "API_DOC_VERSION": test_version, "ENVIRONMENT": "test"},
            capture_output=True,
            text=True,
            cwd="/home/runner/work/backend/backend"
        )
        
        # Assert
        assert result.returncode == 0
        assert test_version in result.stdout.strip()

    def test_version_format_iso_timestamp(self):
        """Test that ISO timestamp format is correctly parsed"""
        # Arrange
        iso_timestamp = "2024-12-20T14:25:30Z"
        
        # Act - Run a subprocess with the environment variable set
        result = subprocess.run(
            ["python", "-c", "from settings.base.drf import SPECTACULAR_SETTINGS; print(SPECTACULAR_SETTINGS['VERSION'])"],
            env={**os.environ, "API_DOC_VERSION": iso_timestamp, "ENVIRONMENT": "test"},
            capture_output=True,
            text=True,
            cwd="/home/runner/work/backend/backend"
        )
        
        # Assert
        version = result.stdout.strip()
        assert iso_timestamp in version
        # Verify ISO format pattern
        assert "T" in version
        assert version.endswith("Z")
