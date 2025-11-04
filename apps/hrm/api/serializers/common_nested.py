"""Reusable nested serializers for HRM models.

This module provides a factory function and predefined nested serializers
to reduce duplication across HRM serializers. All nested serializers are
read-only and provide compact representations of related models.
"""

from rest_framework import serializers

from apps.hrm.models import (
    Block,
    Branch,
    ContractType,
    Department,
    Employee,
    JobDescription,
    Position,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentRequest,
    RecruitmentSource,
)


def SimpleNestedSerializerFactory(model, fields):
    """Factory function to create simple read-only nested serializers.

    Args:
        model: Django model class
        fields: List of field names to include in the serializer

    Returns:
        A ModelSerializer class with specified fields as read-only
    """
    meta_attrs = {
        "model": model,
        "fields": fields,
        "read_only_fields": fields,
    }
    Meta = type("Meta", (), meta_attrs)
    serializer_name = f"{model.__name__}NestedSerializer"
    cls = type(serializer_name, (serializers.ModelSerializer,), {"Meta": Meta})
    return cls


# Predefined nested serializers for common use cases
EmployeeNestedSerializer = SimpleNestedSerializerFactory(
    Employee,
    ["id", "code", "fullname"],
)

BranchNestedSerializer = SimpleNestedSerializerFactory(
    Branch,
    ["id", "name", "code"],
)

BlockNestedSerializer = SimpleNestedSerializerFactory(
    Block,
    ["id", "name", "code"],
)

DepartmentNestedSerializer = SimpleNestedSerializerFactory(
    Department,
    ["id", "name", "code"],
)

PositionNestedSerializer = SimpleNestedSerializerFactory(
    Position,
    ["id", "name", "code"],
)

ContractTypeNestedSerializer = SimpleNestedSerializerFactory(
    ContractType,
    ["id", "name"],
)

JobDescriptionNestedSerializer = SimpleNestedSerializerFactory(
    JobDescription,
    ["id", "code", "title", "requirement", "benefit"],
)

RecruitmentSourceNestedSerializer = SimpleNestedSerializerFactory(
    RecruitmentSource,
    ["id", "code", "name", "allow_referral"],
)

RecruitmentChannelNestedSerializer = SimpleNestedSerializerFactory(
    RecruitmentChannel,
    ["id", "code", "name"],
)

RecruitmentRequestNestedSerializer = SimpleNestedSerializerFactory(
    RecruitmentRequest,
    ["id", "code", "name"],
)

RecruitmentCandidateNestedSerializer = SimpleNestedSerializerFactory(
    RecruitmentCandidate,
    ["id", "code", "name"],
)
