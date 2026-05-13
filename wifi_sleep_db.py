#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MySQL data access helpers for the WiFi sleep monitor demo."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator


DB_NAME = os.getenv("WIFI_SLEEP_DB_NAME", "wifi_sleep_monitor")


class DatabaseNotConfigured(RuntimeError):
    """Raised when MySQL dependencies or connection settings are unavailable."""


def _load_pymysql():
    try:
        import pymysql
        from pymysql.cursors import DictCursor
    except ModuleNotFoundError as exc:
        raise DatabaseNotConfigured(
            "缺少 pymysql，请先运行：pip install pymysql"
        ) from exc
    return pymysql, DictCursor


def _connection_kwargs(database: str | None = DB_NAME) -> dict[str, Any]:
    return {
        "host": os.getenv("WIFI_SLEEP_DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("WIFI_SLEEP_DB_PORT", "3306")),
        "user": os.getenv("WIFI_SLEEP_DB_USER", "root"),
        "password": os.getenv("WIFI_SLEEP_DB_PASSWORD", ""),
        "database": database,
        "charset": "utf8mb4",
        "autocommit": False,
    }


@contextmanager
def mysql_conn(database: str | None = DB_NAME) -> Iterator[Any]:
    pymysql, dict_cursor = _load_pymysql()
    conn = pymysql.connect(cursorclass=dict_cursor, **_connection_kwargs(database))
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _split_sql_script(sql: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(current).rstrip(";"))
            current = []
    if current:
        statements.append("\n".join(current))
    return statements


def init_database() -> None:
    schema = Path("mysql_schema.sql").read_text(encoding="utf-8")
    with mysql_conn(database=None) as conn:
        with conn.cursor() as cur:
            for statement in _split_sql_script(schema):
                cur.execute(statement)


def db_status() -> dict[str, Any]:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE() AS database_name, NOW() AS server_time")
            row = cur.fetchone()
    return {"ok": True, **serialize_row(row)}


def hash_password(password: str) -> str:
    salt = os.getenv("WIFI_SLEEP_PASSWORD_SALT", "wifi-sleep-monitor")
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def serialize_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ")
    return value


def serialize_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    return {key: serialize_value(value) for key, value in row.items()}


def public_user(row: dict[str, Any] | None) -> dict[str, Any] | None:
    data = serialize_row(row)
    if not data:
        return None
    data.pop("password_hash", None)
    return data


def register_user(payload: dict[str, Any]) -> dict[str, Any]:
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", "")).strip()
    nickname = str(payload.get("nickname") or username).strip()
    if not username or not password:
        raise ValueError("账号和密码不能为空")
    avatar_text = str(payload.get("avatar_text") or nickname[:1] or username[:1])
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM users WHERE username=%s", (username,))
            if cur.fetchone():
                raise ValueError("账号已存在")
            cur.execute(
                """
                INSERT INTO users
                  (username, password_hash, nickname, avatar_text, avatar_url, birthday, bio)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    username,
                    hash_password(password),
                    nickname,
                    avatar_text,
                    str(payload.get("avatar_url") or ""),
                    payload.get("birthday") or None,
                    str(payload.get("bio") or "用 WiFi CSI 记录睡眠与微动状态。"),
                ),
            )
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            return public_user(cur.fetchone()) or {}


def login_user(username: str, password: str) -> dict[str, Any] | None:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            row = cur.fetchone()
    if not row or row["password_hash"] != hash_password(password):
        return None
    return public_user(row)


def get_user(username: str) -> dict[str, Any] | None:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            return public_user(cur.fetchone())


def update_user(username: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    allowed = ["nickname", "avatar_text", "avatar_url", "birthday", "bio"]
    fields = [field for field in allowed if field in payload]
    if not fields:
        return get_user(username)
    values = [payload.get(field) or None for field in fields]
    assignments = ", ".join(f"{field}=%s" for field in fields)
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE users SET {assignments} WHERE username=%s",
                [*values, username],
            )
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
            return public_user(cur.fetchone())


def create_post(payload: dict[str, Any]) -> dict[str, Any]:
    post_id = str(payload.get("id") or f"post_{uuid.uuid4().hex}")
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO posts
                  (id, username, title, content, media_url, media_type, media_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    post_id,
                    payload["username"],
                    payload["title"],
                    payload.get("content") or "",
                    payload.get("media_url") or "",
                    payload.get("media_type") or "",
                    payload.get("media_name") or "",
                ),
            )
            cur.execute("SELECT * FROM posts WHERE id=%s", (post_id,))
            return serialize_row(cur.fetchone())


def list_posts(viewer: str | None = None, include_own: bool = True) -> list[dict[str, Any]]:
    where = ""
    args: list[Any] = []
    if viewer and not include_own:
        where = "WHERE p.username<>%s"
        args.append(viewer)
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT p.*, u.nickname, u.avatar_text, u.avatar_url,
                  CASE WHEN l.username IS NULL THEN 0 ELSE 1 END AS liked_by_viewer,
                  CASE WHEN f.username IS NULL THEN 0 ELSE 1 END AS favorited_by_viewer
                FROM posts p
                JOIN users u ON u.username=p.username
                LEFT JOIN post_likes l ON l.post_id=p.id AND l.username=%s
                LEFT JOIN favorites f ON f.post_id=p.id AND f.username=%s
                {where}
                ORDER BY p.created_at DESC
                """,
                [viewer or "", viewer or "", *args],
            )
            return [serialize_row(row) for row in cur.fetchall()]


def list_liked_posts(username: str) -> list[dict[str, Any]]:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*, u.nickname, u.avatar_text, u.avatar_url,
                  1 AS liked_by_viewer,
                  CASE WHEN f.username IS NULL THEN 0 ELSE 1 END AS favorited_by_viewer
                FROM post_likes l
                JOIN posts p ON p.id=l.post_id
                JOIN users u ON u.username=p.username
                LEFT JOIN favorites f ON f.post_id=p.id AND f.username=%s
                WHERE l.username=%s
                ORDER BY l.created_at DESC
                """,
                (username, username),
            )
            return [serialize_row(row) for row in cur.fetchall()]


def list_favorite_posts(username: str) -> list[dict[str, Any]]:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.*, u.nickname, u.avatar_text, u.avatar_url,
                  CASE WHEN l.username IS NULL THEN 0 ELSE 1 END AS liked_by_viewer,
                  1 AS favorited_by_viewer
                FROM favorites f
                JOIN posts p ON p.id=f.post_id
                JOIN users u ON u.username=p.username
                LEFT JOIN post_likes l ON l.post_id=p.id AND l.username=%s
                WHERE f.username=%s
                ORDER BY f.created_at DESC
                """,
                (username, username),
            )
            return [serialize_row(row) for row in cur.fetchall()]


def create_detect_session(username: str) -> int:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO detect_sessions(username) VALUES(%s)",
                (username,),
            )
            return int(cur.lastrowid)


def finish_detect_session(
    session_id: int | None,
    packet_count: int,
    stable_prediction: str,
    summary: dict[str, Any],
) -> None:
    if not session_id:
        return
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE detect_sessions
                SET ended_at=NOW(),
                    packet_count=%s,
                    stable_prediction=%s,
                    summary_json=%s
                WHERE id=%s AND ended_at IS NULL
                """,
                (
                    int(packet_count or 0),
                    stable_prediction or "",
                    json.dumps(summary, ensure_ascii=False),
                    int(session_id),
                ),
            )


def list_recent_detect_sessions(username: str, days: int = 7) -> list[dict[str, Any]]:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM detect_sessions
                WHERE username=%s
                  AND started_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                ORDER BY started_at DESC
                LIMIT 80
                """,
                (username, int(days)),
            )
            rows = [serialize_row(row) for row in cur.fetchall()]
    for row in rows:
        raw_summary = row.get("summary_json")
        if isinstance(raw_summary, str):
            try:
                row["summary_json"] = json.loads(raw_summary)
            except json.JSONDecodeError:
                row["summary_json"] = {}
    return rows


def list_post_comments(post_id: str) -> list[dict[str, Any]]:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.*, u.nickname, u.avatar_text, u.avatar_url
                FROM post_comments c
                JOIN users u ON u.username=c.username
                WHERE c.post_id=%s
                ORDER BY c.created_at ASC
                LIMIT 200
                """,
                (post_id,),
            )
            return [serialize_row(row) for row in cur.fetchall()]


def create_post_comment(payload: dict[str, Any]) -> dict[str, Any]:
    post_id = str(payload.get("post_id") or "").strip()
    username = str(payload.get("username") or "").strip()
    content = str(payload.get("content") or "").strip()
    if not post_id or not username or not content:
        raise ValueError("作品、用户和评论内容不能为空")
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO post_comments(post_id, username, content)
                VALUES(%s, %s, %s)
                """,
                (post_id, username, content),
            )
            comment_id = cur.lastrowid
            cur.execute(
                """
                SELECT c.*, u.nickname, u.avatar_text, u.avatar_url
                FROM post_comments c
                JOIN users u ON u.username=c.username
                WHERE c.id=%s
                """,
                (comment_id,),
            )
            return serialize_row(cur.fetchone())


def toggle_like(post_id: str, username: str) -> dict[str, Any]:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM post_likes WHERE post_id=%s AND username=%s",
                (post_id, username),
            )
            exists = bool(cur.fetchone())
            if exists:
                cur.execute(
                    "DELETE FROM post_likes WHERE post_id=%s AND username=%s",
                    (post_id, username),
                )
                cur.execute(
                    "UPDATE posts SET likes_count=GREATEST(likes_count-1, 0) WHERE id=%s",
                    (post_id,),
                )
            else:
                cur.execute(
                    "INSERT INTO post_likes (post_id, username) VALUES (%s, %s)",
                    (post_id, username),
                )
                cur.execute(
                    "UPDATE posts SET likes_count=likes_count+1 WHERE id=%s",
                    (post_id,),
                )
            cur.execute("SELECT likes_count FROM posts WHERE id=%s", (post_id,))
            post = cur.fetchone()
    return {"liked": not exists, "likes_count": int((post or {}).get("likes_count", 0))}


def toggle_favorite(post_id: str, username: str) -> dict[str, Any]:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM favorites WHERE post_id=%s AND username=%s",
                (post_id, username),
            )
            exists = bool(cur.fetchone())
            if exists:
                cur.execute(
                    "DELETE FROM favorites WHERE post_id=%s AND username=%s",
                    (post_id, username),
                )
            else:
                cur.execute(
                    "INSERT INTO favorites (post_id, username) VALUES (%s, %s)",
                    (post_id, username),
                )
    return {"favorited": not exists}


def send_message(payload: dict[str, Any]) -> dict[str, Any]:
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (sender, receiver, content) VALUES (%s, %s, %s)",
                (payload["sender"], payload["receiver"], payload["content"]),
            )
            message_id = cur.lastrowid
            cur.execute("SELECT * FROM messages WHERE id=%s", (message_id,))
            return serialize_row(cur.fetchone())


def list_messages(username: str, peer: str | None = None) -> list[dict[str, Any]]:
    args: list[Any] = [username, username]
    where = "(sender=%s OR receiver=%s)"
    if peer:
        where += " AND (sender=%s OR receiver=%s)"
        args.extend([peer, peer])
    with mysql_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM messages WHERE {where} ORDER BY created_at ASC",
                args,
            )
            return [serialize_row(row) for row in cur.fetchall()]
