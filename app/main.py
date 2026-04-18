import os
import socket
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


DB_HOST = os.environ.get("DB_HOST", "10.10.10.20")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "appdb")
DB_USER = os.environ.get("DB_USER", "appuser")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "changeme-locally")

# Use APP_HOST from env if set (Compose passes in the VM hostname),
# otherwise fall back to the container's own hostname.
HOST = os.environ.get("APP_HOST", socket.gethostname())

DSN = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"


def db_conn():
    return psycopg.connect(DSN)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1;")
    yield


app = FastAPI(lifespan=lifespan)


class ItemIn(BaseModel):
    name: str


@app.get("/health")
def health():
    return {"status": "ok", "host": HOST}


@app.get("/whoami")
def whoami():
    return {"host": HOST}


@app.get("/items")
def list_items():
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, name, created_at FROM items ORDER BY id;")
        rows = cur.fetchall()
    return [
        {"id": r[0], "name": r[1], "created_at": r[2].isoformat()}
        for r in rows
    ]


@app.post("/items", status_code=201)
def create_item(item: ItemIn):
    if not item.name.strip():
        raise HTTPException(status_code=400, detail="name must not be empty")
    with db_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO items (name) VALUES (%s) RETURNING id, name, created_at;",
            (item.name,),
        )
        row = cur.fetchone()
        conn.commit()
    return {"id": row[0], "name": row[1], "created_at": row[2].isoformat()}
