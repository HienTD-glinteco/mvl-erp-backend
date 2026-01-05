import pytest
from django.core.exceptions import ValidationError

from apps.core.models import Role


@pytest.mark.django_db
class TestRoleModel:
    def test_create_first_default_role(self):
        """Test creating the first default role succeeds"""
        role = Role.objects.create(code="VT_DEFAULT", name="Default Role", is_default_role=True)
        assert role.is_default_role is True
        assert Role.objects.filter(is_default_role=True).count() == 1

    def test_create_second_default_role_fails(self):
        """Test creating a second default role raises ValidationError"""
        # Create first default role
        Role.objects.create(code="VT_DEFAULT_1", name="Default Role 1", is_default_role=True)

        # Try to create second default role
        with pytest.raises(ValidationError) as exc:
            Role.objects.create(code="VT_DEFAULT_2", name="Default Role 2", is_default_role=True)

        assert "Only one role can be set as default" in str(exc.value)

    def test_update_role_to_default_fails_if_exists(self):
        """Test updating a role to be default fails if one already exists"""
        # Create first default role
        Role.objects.create(code="VT_DEFAULT_1", name="Default Role 1", is_default_role=True)

        # Create normal role
        role2 = Role.objects.create(code="VT_NORMAL", name="Normal Role", is_default_role=False)

        # Try to update normal role to default
        role2.is_default_role = True
        with pytest.raises(ValidationError) as exc:
            role2.save()

        assert "Only one role can be set as default" in str(exc.value)

    def test_update_existing_default_role_succeeds(self):
        """Test updates to the default role itself succeed"""
        role = Role.objects.create(code="VT_DEFAULT", name="Default Role", is_default_role=True)

        # Update name
        role.name = "Updated Default Role"
        role.save()

        role.refresh_from_db()
        assert role.name == "Updated Default Role"
        assert role.is_default_role is True

    def test_multiple_non_default_roles_allowed(self):
        """Test multiple non-default roles are allowed"""
        Role.objects.create(code="VT001", name="Role 1", is_default_role=False)
        Role.objects.create(code="VT002", name="Role 2", is_default_role=False)
        Role.objects.create(code="VT003", name="Role 3", is_default_role=False)

        assert Role.objects.filter(is_default_role=False).count() == 3

    def test_unsetting_default_role(self):
        """Test checking if a default role can be unset"""
        role = Role.objects.create(code="VT_DEFAULT", name="Default Role", is_default_role=True)

        role.is_default_role = False
        role.save()

        assert Role.objects.filter(is_default_role=True).count() == 0
