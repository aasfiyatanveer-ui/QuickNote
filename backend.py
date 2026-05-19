"""
Quick Notes - FastAPI Backend
Run: pip install fastapi uvicorn
Start: uvicorn backend:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import time
import os

app = FastAPI(title="Quick Notes API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "notes.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            title    TEXT NOT NULL,
            content  TEXT NOT NULL,
            color    TEXT DEFAULT '#FEFCE8',
            pinned   INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()


class NoteCreate(BaseModel):
    title: str
    content: str
    color: Optional[str] = "#FEFCE8"

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    color: Optional[str] = None
    pinned: Optional[bool] = None

class NoteResponse(BaseModel):
    id: int
    title: str
    content: str
    color: str
    pinned: bool
    created_at: int
    updated_at: int


def row_to_note(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "color": row["color"],
        "pinned": bool(row["pinned"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.get("/notes", response_model=list[NoteResponse])
def get_notes():
    """Fetch all notes — pinned first, then newest."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notes ORDER BY pinned DESC, created_at DESC"
    ).fetchall()
    conn.close()
    return [row_to_note(r) for r in rows]


@app.post("/notes", response_model=NoteResponse, status_code=201)
def create_note(note: NoteCreate):
    """Create a new note."""
    now = int(time.time() * 1000)
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO notes (title, content, color, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (note.title.strip(), note.content.strip(), note.color, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return row_to_note(row)


@app.patch("/notes/{note_id}", response_model=NoteResponse)
def update_note(note_id: int, note: NoteUpdate):
    """Partially update a note (title, content, color, pinned)."""
    conn = get_db()
    existing = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Note not found")

    fields = {}
    if note.title is not None:
        fields["title"] = note.title.strip()
    if note.content is not None:
        fields["content"] = note.content.strip()
    if note.color is not None:
        fields["color"] = note.color
    if note.pinned is not None:
        fields["pinned"] = 1 if note.pinned else 0
    fields["updated_at"] = int(time.time() * 1000)

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [note_id]
    conn.execute(f"UPDATE notes SET {set_clause} WHERE id = ?", values)
    conn.commit()

    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    conn.close()
    return row_to_note(row)


@app.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int):
    """Delete a note by ID."""
    conn = get_db()
    existing = conn.execute("SELECT id FROM notes WHERE id = ?", (note_id,)).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(status_code=404, detail="Note not found")
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()


@app.get("/health")
def health():
    return {"status": "ok", "db": os.path.exists(DB_PATH)}
