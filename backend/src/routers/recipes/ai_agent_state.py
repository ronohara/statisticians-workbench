"""
Agent State Pydantic Model — Phase 2.1

Tracks the accumulated decisions made during an AI recipe conversation.
Serialised as JSONB in the AIRecipeSession.state column.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


class AgentState(BaseModel):
    """Mutable state accumulated across conversation turns.

    Holds the conversational fields (goal, expertise) plus the recipe draft in
    the canonical stage shape (data_selection / statistics / visualisation),
    matching the manual editor's ``recipe.stages``. The AI reads and writes the
    draft through the tools (``validate_recipe`` / ``save_recipe`` capture
    ``stages``).
    """

    goal: Optional[str] = Field(
        default=None,
        description="What the user wants to discover, in their own words",
    )
    expertise_level: str = Field(
        default="novice",
        description="Detected user expertise: novice, intermediate, or expert",
    )
    completion_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How close the conversation is to a complete recipe (0.0–1.0), "
        "derived from the scoreboard — complete when nothing is next and nothing blocks",
    )
    stages: list[dict] = Field(
        default_factory=list,
        description="Canonical recipe draft: data_selection / statistics / visualisation stages",
    )
    schema_snapshot: Optional[list[dict]] = Field(
        default=None,
        description="Last-known dataset column schema for change detection",
    )
    saved_recipe_id: Optional[str] = Field(
        default=None,
        description="Id of the Recipe this session was saved as, once saved",
    )
