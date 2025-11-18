"""
Database Schemas for the Radio + Blog app

Each Pydantic model represents a collection in your database.
Model name lowercased is used as collection name.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Blogpost(BaseModel):
    """
    Blog posts about African culture, music, stories, and news
    Collection name: "blogpost"
    """
    title: str = Field(..., description="Post title")
    content: str = Field(..., description="Rich text/markdown content")
    author: str = Field(..., description="Author display name")
    tags: List[str] = Field(default_factory=list, description="Topic tags")
    cover_image: Optional[str] = Field(None, description="Optional cover image URL")
    published_at: Optional[datetime] = Field(None, description="Publish date; set by backend if omitted")

class Session(BaseModel):
    """
    Visitor session heartbeat to compute active users online
    Collection name: "session"
    """
    visitor_id: str = Field(..., description="Stable anonymous client id")
    last_seen: datetime = Field(default_factory=datetime.utcnow, description="Last heartbeat timestamp (UTC)")

class Sitestat(BaseModel):
    """
    Aggregate counters for the site
    Collection name: "sitestat"
    """
    key: str = Field(..., description="Document key, e.g. 'global'")
    total_views: int = Field(0, description="Total unique visits recorded")
