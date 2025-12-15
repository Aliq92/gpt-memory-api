from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./memory.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class MemoryItem(Base):
    __tablename__ = "memory_items"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    key = Column(String, index=True, nullable=False)
    value = Column(Text, nullable=False)
    tags = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="GPT Memory API", version="1.0.0")

class MemoryCreate(BaseModel):
    user_id: str = Field(...)
    key: str
    value: str
    tags: Optional[List[str]] = None

class MemoryOut(BaseModel):
    id: int
    user_id: str
    key: str
    value: str
    tags: Optional[List[str]] = None
    created_at: datetime

def tags_to_str(tags: Optional[List[str]]) -> Optional[str]:
    return ",".join([t.strip() for t in tags if t.strip()]) if tags else None

def tags_from_str(s: Optional[str]) -> Optional[List[str]]:
    if not s:
        return None
    return [t for t in (x.strip() for x in s.split(",")) if t]

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/memory", response_model=MemoryOut)
def add_memory(m: MemoryCreate):
    db = SessionLocal()
    try:
        item = MemoryItem(user_id=m.user_id, key=m.key, value=m.value, tags=tags_to_str(m.tags))
        db.add(item)
        db.commit()
        db.refresh(item)
        return MemoryOut(
            id=item.id, user_id=item.user_id, key=item.key, value=item.value,
            tags=tags_from_str(item.tags), created_at=item.created_at
        )
    finally:
        db.close()

@app.get("/memory", response_model=List[MemoryOut])
def list_memory(user_id: str, key: Optional[str] = None, tag: Optional[str] = None, limit: int = 50):
    db = SessionLocal()
    try:
        q = db.query(MemoryItem).filter(MemoryItem.user_id == user_id)
        if key:
            q = q.filter(MemoryItem.key == key)
        if tag:
            q = q.filter(MemoryItem.tags.like(f"%{tag}%"))
        items = q.order_by(MemoryItem.created_at.desc()).limit(limit).all()
        return [
            MemoryOut(
                id=i.id, user_id=i.user_id, key=i.key, value=i.value,
                tags=tags_from_str(i.tags), created_at=i.created_at
            )
            for i in items
        ]
    finally:
        db.close()

@app.delete("/memory/{memory_id}")
def delete_memory(memory_id: int):
    db = SessionLocal()
    try:
        item = db.query(MemoryItem).filter(MemoryItem.id == memory_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Not found")
        db.delete(item)
        db.commit()
        return {"deleted": True, "id": memory_id}
    finally:
        db.close()
