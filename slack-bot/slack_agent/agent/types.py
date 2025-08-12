from typing import Literal
from pydantic import BaseModel, Field

class MessageClassification(BaseModel):
    """
    Classification of a message.
    """
    reasoning: str = Field(
        description="Step-by-step reasoning behind the classification."
    )
    category: Literal["documentation", "bug", "feature_request"] = Field(
        description="""
        The classification of the message: 'documentation' when a user is looking for information, 
        'bug' when a user is reporting an issue, or 'feature_request' when a user is suggesting a new feature.
        """
    )