import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Blogpost

app = FastAPI(title="Radio Africa Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Helpers ----------
class BlogCreate(Blogpost):
    pass

class BlogOut(BaseModel):
    id: str
    title: str
    content: str
    author: str
    tags: List[str] = []
    cover_image: Optional[str] = None
    published_at: Optional[datetime] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


def serialize_blog(doc) -> BlogOut:
    return BlogOut(
        id=str(doc.get("_id")),
        title=doc.get("title"),
        content=doc.get("content"),
        author=doc.get("author"),
        tags=doc.get("tags", []),
        cover_image=doc.get("cover_image"),
        published_at=doc.get("published_at"),
    )


# ---------- Root & Health ----------
@app.get("/")
def read_root():
    return {"message": "Radio Africa API running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


# ---------- Blog Endpoints ----------
@app.get("/api/blogs", response_model=List[BlogOut])
def list_blogs(limit: int = 20):
    docs = db["blogpost"].find({}).sort("published_at", -1).limit(limit)
    return [serialize_blog(d) for d in docs]


@app.post("/api/blogs", response_model=BlogOut)
def create_blog(post: BlogCreate):
    data = post.model_dump()
    # set publish time if not provided
    data["published_at"] = data.get("published_at") or datetime.now(timezone.utc)
    inserted_id = db["blogpost"].insert_one({
        **data,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }).inserted_id
    doc = db["blogpost"].find_one({"_id": inserted_id})
    return serialize_blog(doc)


@app.get("/api/blogs/{post_id}", response_model=BlogOut)
def get_blog(post_id: str):
    try:
        oid = ObjectId(post_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid blog id")
    doc = db["blogpost"].find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return serialize_blog(doc)


# ---------- Stats & Presence ----------
class HeartbeatIn(BaseModel):
    visitor_id: str


@app.post("/api/heartbeat")
def heartbeat(payload: HeartbeatIn):
    now = datetime.now(timezone.utc)
    vid = payload.visitor_id

    # Upsert session last_seen
    prev = db["session"].find_one({"visitor_id": vid})
    db["session"].update_one(
        {"visitor_id": vid},
        {"$set": {"visitor_id": vid, "last_seen": now}, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )

    # If first time seeing this visitor, increment total views in sitestat
    if prev is None:
        db["sitestat"].update_one(
            {"key": "global"},
            {"$inc": {"total_views": 1}, "$setOnInsert": {"key": "global", "created_at": now}},
            upsert=True,
        )

    return {"ok": True}


@app.get("/api/stats")
def get_stats(window_seconds: int = 120):
    now = datetime.now(timezone.utc)
    since = now - timedelta(seconds=window_seconds)

    active = db["session"].count_documents({"last_seen": {"$gte": since}})
    stat = db["sitestat"].find_one({"key": "global"}) or {"total_views": 0}
    total = int(stat.get("total_views", 0))

    return {"active": active, "total": total}


# ---------- Diagnostics ----------
@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
