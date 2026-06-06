"""Pipeline step registries (§6.6.2 RepStepRegistry, §6.7.2 IndexStepRegistry)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .protocols import IndexStepProtocol, ProjectorStepProtocol, RepStepProtocol


class RepStepRegistry:
    """Global RepStep registry (§6.6.2). Supports runtime dynamic registration."""

    _steps: dict[str, RepStepProtocol] = {}

    @classmethod
    def register(cls, step: RepStepProtocol) -> None:
        """Register a RepStep. Third-party plugins inject through this interface."""
        cls._steps[step.step_id] = step

    @classmethod
    def get(cls, step_id: str) -> RepStepProtocol:
        """Get a registered RepStep by ID."""
        if step_id not in cls._steps:
            raise KeyError(f"RepStep '{step_id}' not registered")
        return cls._steps[step_id]

    @classmethod
    def all_steps(cls) -> dict[str, RepStepProtocol]:
        """Return all registered steps."""
        return dict(cls._steps)

    @classmethod
    def steps_for_entity_type(cls, entity_type: str) -> list[RepStepProtocol]:
        """Return all steps that support this entity_type."""
        return [s for s in cls._steps.values() if entity_type in s.supported_entity_types]

    @classmethod
    def steps_producing_rep(cls, rep_type: str) -> list[RepStepProtocol]:
        """Return all steps that can produce this rep_type."""
        return [s for s in cls._steps.values() if rep_type in s.output_reps]

    @classmethod
    def clear(cls) -> None:
        """Clear all registered steps (for testing)."""
        cls._steps = {}


class IndexStepRegistry:
    """Global IndexStep registry (§6.7.2). Supports runtime dynamic registration."""

    _steps: dict[str, IndexStepProtocol] = {}

    @classmethod
    def register(cls, step: IndexStepProtocol) -> None:
        cls._steps[step.step_id] = step

    @classmethod
    def get(cls, step_id: str) -> IndexStepProtocol:
        if step_id not in cls._steps:
            raise KeyError(f"IndexStep '{step_id}' not registered")
        return cls._steps[step_id]

    @classmethod
    def all_steps(cls) -> dict[str, IndexStepProtocol]:
        return dict(cls._steps)

    @classmethod
    def steps_for_reps(cls, available_reps: list[str]) -> list[IndexStepProtocol]:
        """Return all steps whose required_reps are satisfied."""
        return [s for s in cls._steps.values() if all(r in available_reps for r in s.required_reps)]

    @classmethod
    def clear(cls) -> None:
        cls._steps = {}


class ProjectorStepRegistry:
    """Global ProjectorStep registry (§11)."""

    _steps: dict[str, ProjectorStepProtocol] = {}

    @classmethod
    def register(cls, step: ProjectorStepProtocol) -> None:
        cls._steps[step.step_id] = step

    @classmethod
    def get(cls, step_id: str) -> ProjectorStepProtocol:
        if step_id not in cls._steps:
            raise KeyError(f"ProjectorStep '{step_id}' not registered")
        return cls._steps[step_id]

    @classmethod
    def all_steps(cls) -> dict[str, ProjectorStepProtocol]:
        return dict(cls._steps)

    @classmethod
    def steps_for_target(cls, target: str) -> list[ProjectorStepProtocol]:
        """Return all projectors targeting a specific consumer."""
        return [s for s in cls._steps.values() if s.target == target]

    @classmethod
    def clear(cls) -> None:
        cls._steps = {}
