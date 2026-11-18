"""
Request/Response models for recipe operations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, field_serializer
from src.utils.timestamps import iso_utc


class RecipeStage(BaseModel):
    """A single stage in a recipe."""
    id: Optional[str] = None
    type: str  # "data_selection", "data_preparation", "statistics", "visualisation"
    config: Dict[str, Any]  # Stage-specific configuration


class CreateRecipeRequest(BaseModel):
    """Request model for creating a recipe."""
    name: str
    description: Optional[str] = None
    datasetId: Optional[str] = None
    stages: List[RecipeStage]
    shared: bool = False
    recipeGroup: str = "00"
    preparationRuleIds: List[str] = []
    forkedFrom: Optional[str] = None
    forkedFromName: Optional[str] = None


class UpdateRecipeRequest(BaseModel):
    """Request model for updating a recipe."""
    name: Optional[str] = None
    description: Optional[str] = None
    datasetId: Optional[str] = None
    stages: Optional[List[RecipeStage]] = None
    shared: Optional[bool] = None
    recipeGroup: Optional[str] = None
    preparationRuleIds: Optional[List[str]] = None
    forkedFrom: Optional[str] = None
    forkedFromName: Optional[str] = None
    status: Optional[str] = None


class ExecuteRecipeRequest(BaseModel):
    """Request model for executing a recipe."""
    recipe_id: str


class RecipeResponse(BaseModel):
    """Response model for a single recipe."""
    id: str
    name: str
    description: Optional[str] = None
    datasetId: Optional[str] = None
    datasetName: Optional[str] = None
    stages: List[RecipeStage]
    recipeGroup: str
    userId: str
    user_name: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    isOwn: bool
    # Whether the caller may see this recipe because its owner shared it with their
    # group. The list query returns own-plus-shared and nothing else, and the
    # recipes page files the two apart by this flag — so it has to be in the body,
    # not merely in the query.
    isShared: bool = False
    # Whether the executor would accept the recipe as it stands, judged by the same
    # validation the runner's pre-flight uses. Computed by the list endpoint
    # (`crud._recipe_ready`); the single-recipe response leaves it unset because
    # nothing needs it there.
    ready: Optional[bool] = None
    # Whether the caller may save this recipe — `can_edit_recipe`, the same rule the
    # update and delete endpoints enforce (the owner, or an administrator when the
    # recipe is shared to the administrator's group). The editor's read-only state
    # follows this rather than `isOwn`, so an administrator opening a shared recipe is
    # offered the save the backend would accept. Computed by the single-recipe
    # response; the list leaves it unset because nothing needs it there — the mirror
    # image of `ready`.
    canEdit: Optional[bool] = None
    createdAt: datetime
    updatedAt: datetime
    preparation_rules: List[Dict[str, Any]] = []
    status: Optional[str] = None
    forkedFrom: Optional[str] = None
    forkedFromName: Optional[str] = None

    # The fields stay `datetime`, because that is what a `timestamptz` column
    # carries and the type is the guarantee that a string never wanders into a
    # column comparison. What changes is the **output**.
    #
    # This was a `@field_validator(mode='before')` returning `iso_utc(v)`. That
    # looked right and did nothing: `mode='before'` runs before Pydantic's own
    # validation, and the field is declared `datetime`, so Pydantic took the
    # correctly-formatted string and coerced it straight back into a datetime.
    # `iso_utc`'s return value was discarded on arrival and the wire form came
    # from Pydantic's default encoder — `isoformat()`, six fraction digits, or
    # none at all for a whole second. Measured 2026-11-10: this route emitted
    # `…032000Z` while Go emitted `…032Z`, and the timestamp plan's wire-form
    # test did not catch it because it asserts `iso_utc`'s return value and never
    # passes one through this model.
    #
    # A serializer runs on the way out instead, so the parsed value keeps its
    # type and the rendering goes through the one canonical function — the form
    # `project-design.md` §4 states: three fraction digits, `Z` for UTC.
    @field_serializer('createdAt', 'updatedAt')
    def serialize_datetime(self, v: datetime) -> str:
        return iso_utc(v)


class RecipeListResponse(BaseModel):
    """Response model for listing recipes."""
    recipes: List[RecipeResponse]


class ExecutionResponse(BaseModel):
    """Response model for a recipe execution."""
    id: str
    recipeId: str
    status: str  # "pending", "running", "completed", "failed", "cancelled"
    progress: int
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    startedAt: Optional[str] = None
    completedAt: Optional[str] = None
    createdAt: str