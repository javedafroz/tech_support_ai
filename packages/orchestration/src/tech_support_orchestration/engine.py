from __future__ import annotations

from pathlib import Path

from tech_support_orchestration.mapping import FieldMappingConfig, load_field_mapping
from tech_support_orchestration.models import (
    OrchestrationResult,
    PolicyOutcome,
    StructuredIntent,
    UserContext,
)
from tech_support_orchestration.policy import PolicyValidator
from tech_support_orchestration.workflow import WorkflowEngine


class OrchestrationEngine:
    def __init__(
        self,
        *,
        validator: PolicyValidator | None = None,
        workflow: WorkflowEngine | None = None,
        mapping: FieldMappingConfig | None = None,
    ) -> None:
        mapping = mapping or load_field_mapping()
        self._validator = validator or PolicyValidator()
        self._workflow = workflow or WorkflowEngine(mapping)

    @classmethod
    def from_mapping_path(cls, path: Path) -> OrchestrationEngine:
        mapping = load_field_mapping(path)
        return cls(mapping=mapping, workflow=WorkflowEngine(mapping))

    def process(self, intent: StructuredIntent, user: UserContext) -> OrchestrationResult:
        validation = self._validator.validate(intent, user)
        if not validation.passed:
            return OrchestrationResult(
                outcome=PolicyOutcome.REJECTED,
                reason_code=validation.reason_code,
                rule_id=validation.rule_id,
                validation=validation,
            )

        command = self._workflow.build_command(intent, user)
        return OrchestrationResult(
            outcome=PolicyOutcome.APPROVED,
            approved_command=command,
            validation=validation,
            rule_id=validation.rule_id,
        )
