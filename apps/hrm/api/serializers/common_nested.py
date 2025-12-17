"""Reusable nested serializers for HRM models.

This module provides predefined nested serializers to reduce duplication
across HRM serializers. All nested serializers are read-only and provide
compact representations of related models.
"""

from apps.core.api.serializers.common_nested import SimpleNestedSerializerFactory
from apps.hrm.models import (
    Bank,
    Block,
    Branch,
    Contract,
    ContractType,
    Decision,
    Department,
    Employee,
    JobDescription,
    Position,
    RecruitmentCandidate,
    RecruitmentChannel,
    RecruitmentRequest,
    RecruitmentSource,
)

# Predefined nested serializers for common use cases
EmployeeNestedSerializer = SimpleNestedSerializerFactory(
    Employee,
    ["id", "code", "fullname"],
)

BankNestedSerializer = SimpleNestedSerializerFactory(
    Bank,
    ["id", "name", "code"],
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

ContractNestedSerializer = SimpleNestedSerializerFactory(
    Contract,
    ["id", "code"],
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

DecisionNestedSerializer = SimpleNestedSerializerFactory(
    Decision,
    ["id", "decision_number", "name", "signing_date"],
)
