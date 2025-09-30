from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ItemInput(BaseModel):
    sku: str
    name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)

class MarketplaceCategoryResult(BaseModel):
    marketplace: str
    category_name: str
    category_id: str
    category_path: str                 # <-- NEW (always present; "N/A" when unmapped or skipped)
    confidence: Optional[float] = None # Optional confidence score from the LLM when test mode enabled
    note: Optional[str] = None         # (already added earlier)

class CategorizationResponse(BaseModel):
    sku: str
    categories: List[MarketplaceCategoryResult]
