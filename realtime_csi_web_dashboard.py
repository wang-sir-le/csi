#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI dashboard for real-time CSI state recognition."""

import argparse
import asyncio
import threading
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from build_csi_features import WINDOW_SIZE, STEP_SIZE, extract_window_features
from csi_receiver_collector import CSIReceiverCollector
from wifi_sleep_db import (
    DatabaseNotConfigured,
    create_detect_session,
    create_post_comment,
    create_post,
    db_status,
    finish_detect_session,
    get_user,
    init_database,
    list_favorite_posts,
    list_liked_posts,
    list_messages,
    list_post_comments,
    list_posts,
    list_recent_detect_sessions,
    login_user,
    register_user,
    send_message,
    toggle_favorite,
    toggle_like,
    update_user,
)


DEFAULT_MODEL = Path("data/multi_group/models/csi_state_classifier.joblib")
PAGE_DIR = Path("web_pages")

app = FastAPI(title="CSI State Dashboard")
app.mount("/assets", StaticFiles(directory="web_assets"), name="assets")


class RegisterPayload(BaseModel):
    username: str
    password: str
    nickname: str | None = None
    avatar_text: str | None = None
    avatar_url: str | None = None
    birthday: str | None = None
    bio: str | None = None


class LoginPayload(BaseModel):
    username: str
    password: str


class UserUpdatePayload(BaseModel):
    nickname: str | None = None
    avatar_text: str | None = None
    avatar_url: str | None = None
    birthday: str | None = None
    bio: str | None = None


class PostPayload(BaseModel):
    username: str
    title: str
    content: str | None = ""
    media_url: str | None = ""
    media_type: str | None = ""
    media_name: str | None = ""


class ActorPayload(BaseModel):
    username: str


class MessagePayload(BaseModel):
    sender: str
    receiver: str
    content: str


class CommentPayload(BaseModel):
    post_id: str
    username: str
    content: str


def read_page(name: str) -> str:
    return (PAGE_DIR / name).read_text(encoding="utf-8")


def db_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DatabaseNotConfigured):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@app.get("/api/db/status")
def api_db_status() -> dict[str, Any]:
    try:
        return db_status()
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.post("/api/db/init")
def api_db_init() -> dict[str, Any]:
    try:
        init_database()
        return {"ok": True, "message": "MySQL 数据表已初始化"}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.post("/api/auth/register")
def api_register(payload: RegisterPayload) -> dict[str, Any]:
    try:
        return {"ok": True, "user": register_user(payload.model_dump())}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.post("/api/auth/login")
def api_login(payload: LoginPayload) -> dict[str, Any]:
    try:
        user = login_user(payload.username, payload.password)
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc
    if not user:
        raise HTTPException(status_code=401, detail="账号不存在或密码错误")
    return {"ok": True, "user": user}


@app.get("/api/users/{username}")
def api_get_user(username: str) -> dict[str, Any]:
    try:
        user = get_user(username)
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "user": user}


@app.patch("/api/users/{username}")
def api_update_user(username: str, payload: UserUpdatePayload) -> dict[str, Any]:
    try:
        user = update_user(username, payload.model_dump(exclude_unset=True))
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "user": user}


@app.get("/api/posts")
def api_list_posts(
    viewer: str | None = Query(default=None),
    include_own: bool = Query(default=True),
) -> dict[str, Any]:
    try:
        return {"ok": True, "posts": list_posts(viewer=viewer, include_own=include_own)}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.get("/api/users/{username}/liked-posts")
def api_list_liked_posts(username: str) -> dict[str, Any]:
    try:
        return {"ok": True, "posts": list_liked_posts(username)}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.get("/api/users/{username}/favorite-posts")
def api_list_favorite_posts(username: str) -> dict[str, Any]:
    try:
        return {"ok": True, "posts": list_favorite_posts(username)}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.get("/api/users/{username}/detect-sessions")
def api_list_detect_sessions(username: str, days: int = Query(default=7)) -> dict[str, Any]:
    try:
        return {"ok": True, "sessions": list_recent_detect_sessions(username, days=days)}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.post("/api/posts")
def api_create_post(payload: PostPayload) -> dict[str, Any]:
    try:
        return {"ok": True, "post": create_post(payload.model_dump())}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.get("/api/posts/{post_id}/comments")
def api_list_post_comments(post_id: str) -> dict[str, Any]:
    try:
        return {"ok": True, "comments": list_post_comments(post_id)}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.post("/api/posts/{post_id}/comments")
def api_create_post_comment(post_id: str, payload: CommentPayload) -> dict[str, Any]:
    try:
        data = payload.model_dump()
        data["post_id"] = post_id
        return {"ok": True, "comment": create_post_comment(data)}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.post("/api/posts/{post_id}/like")
def api_toggle_like(post_id: str, payload: ActorPayload) -> dict[str, Any]:
    try:
        return {"ok": True, **toggle_like(post_id, payload.username)}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.post("/api/posts/{post_id}/favorite")
def api_toggle_favorite(post_id: str, payload: ActorPayload) -> dict[str, Any]:
    try:
        return {"ok": True, **toggle_favorite(post_id, payload.username)}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.get("/api/messages")
def api_list_messages(username: str, peer: str | None = None) -> dict[str, Any]:
    try:
        return {"ok": True, "messages": list_messages(username=username, peer=peer)}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc


@app.post("/api/messages")
def api_send_message(payload: MessagePayload) -> dict[str, Any]:
    try:
        return {"ok": True, "message": send_message(payload.model_dump())}
    except Exception as exc:  # noqa: BLE001
        raise db_error(exc) from exc

state_lock = threading.Lock()
runtime_state: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "packets": 0,
    "prediction": "等待数据",
    "stable_prediction": "等待数据",
    "probabilities": {},
    "logs": [],
    "error": "",
}

monitor_thread: threading.Thread | None = None
monitor_stop_event: threading.Event | None = None
monitor_config: dict[str, Any] = {}
active_session_id: int | None = None


def add_log(message: str) -> None:
    with state_lock:
        logs = runtime_state["logs"]
        logs.append({"time": time.strftime("%H:%M:%S"), "message": message})
        del logs[:-30]


def majority_vote(values: deque[str]) -> str:
    if not values:
        return "等待数据"
    return Counter(values).most_common(1)[0][0]


def update_state(**kwargs: Any) -> None:
    with state_lock:
        runtime_state.update(kwargs)


def session_summary() -> dict[str, Any]:
    with state_lock:
        probabilities = dict(runtime_state.get("probabilities") or {})
        max_confidence = max([float(v) for v in probabilities.values()], default=0.0)
        return {
            "packets": int(runtime_state.get("packets") or 0),
            "prediction": runtime_state.get("prediction") or "等待数据",
            "stable_prediction": runtime_state.get("stable_prediction") or "等待数据",
            "max_confidence": max_confidence,
            "error": runtime_state.get("error") or "",
        }


def close_active_session() -> None:
    global active_session_id
    if not active_session_id:
        return
    summary = session_summary()
    try:
        finish_detect_session(
            active_session_id,
            packet_count=int(summary["packets"]),
            stable_prediction=str(summary["stable_prediction"]),
            summary=summary,
        )
    except Exception as exc:  # noqa: BLE001
        add_log(f"检测记录保存失败：{exc}")
    active_session_id = None


def monitor_loop(
    port: str,
    baudrate: int,
    model_path: str,
    window_size: int,
    step_size: int,
    smooth: int,
    min_confidence: float,
    stop_event: threading.Event,
) -> None:
    bundle = joblib.load(model_path)
    model = bundle["model"]
    feature_cols = bundle["feature_cols"]

    collector = CSIReceiverCollector(port=port, baudrate=baudrate, timeout=1.0)
    if not collector.connect():
        update_state(error="串口连接失败", running=False)
        add_log("串口连接失败")
        return

    amp_buffer: deque[list[float]] = deque(maxlen=window_size)
    votes: deque[str] = deque(maxlen=smooth)
    valid_packets = 0
    next_predict_at = window_size
    update_state(running=True, started_at=time.time(), error="")
    add_log(f"实时监测启动：port={port}, model={model_path}")

    try:
        while not stop_event.is_set():
            raw = collector.serial_conn.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="ignore").strip()
            parsed = collector.parse_csi_line(line)
            if not parsed or not collector.validate_csi_data(parsed):
                continue

            amp = parsed.get("amplitude_array", [])
            if len(amp) != 192:
                continue

            amp_buffer.append(amp)
            valid_packets += 1

            if len(amp_buffer) < window_size or valid_packets < next_predict_at:
                update_state(packets=valid_packets)
                continue

            window = np.asarray(amp_buffer, dtype=float)
            features = extract_window_features(window)
            x = pd.DataFrame([[features[col] for col in feature_cols]], columns=feature_cols)
            probs = model.predict_proba(x)[0]
            labels = list(model.classes_)
            best_idx = int(np.argmax(probs))
            raw_pred = str(labels[best_idx])
            best_prob = float(probs[best_idx])
            pred = raw_pred if best_prob >= min_confidence else "不确定"
            votes.append(pred)
            stable = majority_vote(votes)
            probabilities = {str(label): float(prob) for label, prob in zip(labels, probs)}

            update_state(
                packets=valid_packets,
                prediction=pred,
                stable_prediction=stable,
                probabilities=probabilities,
            )
            add_log(f"预测={pred}，稳定状态={stable}，最高置信度={best_prob:.2f}")
            next_predict_at += step_size

    except Exception as exc:  # noqa: BLE001
        update_state(error=str(exc), running=False)
        add_log(f"监测异常：{exc}")
    finally:
        collector.disconnect()
        update_state(running=False)
        close_active_session()
        add_log("检测已停止，串口已释放")


@app.get("/api/state")
def get_state() -> dict[str, Any]:
    with state_lock:
        data = dict(runtime_state)
        data["logs"] = list(runtime_state["logs"])
    if data["started_at"]:
        data["elapsed"] = time.time() - float(data["started_at"])
    else:
        data["elapsed"] = 0
    return data


@app.post("/api/start")
def start_monitor(payload: ActorPayload | None = None) -> dict[str, Any]:
    global monitor_thread, monitor_stop_event, active_session_id
    if monitor_thread and monitor_thread.is_alive():
        return {"ok": True, "message": "检测已在运行"}

    config = {
        "port": monitor_config.get("port", "COM13"),
        "baudrate": monitor_config.get("baudrate", 921600),
        "model_path": monitor_config.get("model_path", str(DEFAULT_MODEL)),
        "window_size": monitor_config.get("window_size", WINDOW_SIZE),
        "step_size": monitor_config.get("step_size", STEP_SIZE),
        "smooth": monitor_config.get("smooth", 5),
        "min_confidence": monitor_config.get("min_confidence", 0.60),
    }
    monitor_stop_event = threading.Event()
    active_session_id = None
    if payload and payload.username:
        try:
            active_session_id = create_detect_session(payload.username)
        except Exception as exc:  # noqa: BLE001
            add_log(f"检测记录创建失败：{exc}")
    update_state(
        running=False,
        started_at=None,
        packets=0,
        prediction="等待数据",
        stable_prediction="等待数据",
        probabilities={},
        error="",
    )
    add_log("用户点击开启检测")
    monitor_thread = threading.Thread(
        target=monitor_loop,
        kwargs={**config, "stop_event": monitor_stop_event},
        daemon=True,
    )
    monitor_thread.start()
    return {"ok": True, "message": "检测启动中"}


@app.post("/api/stop")
def stop_monitor() -> dict[str, Any]:
    global monitor_stop_event
    if monitor_stop_event:
        monitor_stop_event.set()
    add_log("用户点击关闭检测")
    update_state(running=False)
    close_active_session()
    return {"ok": True, "message": "检测停止中"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>无源 WiFi 睡眠微动监测</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
      --panel: rgba(13, 29, 38, 0.72);
      --panel-soft: rgba(255, 255, 255, 0.12);
      --line: rgba(255, 255, 255, 0.20);
      --text: #f8fbff;
      --muted: rgba(248, 251, 255, 0.72);
      --mint: #9ee7c5;
      --aqua: #8bd4ff;
      --rose: #f7c8d8;
      --gold: #f5db9b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        linear-gradient(115deg, rgba(8, 31, 44, .78), rgba(31, 52, 45, .42)),
        url('/assets/forest.jpeg') center / cover fixed;
      overflow-x: hidden;
    }
    body.night {
      background:
        linear-gradient(115deg, rgba(10, 11, 34, .72), rgba(44, 37, 76, .44)),
        url('/assets/stars.jpeg') center / cover fixed;
    }
    .app {
      min-height: 100vh;
      padding: 22px clamp(16px, 4vw, 54px) 34px;
      background: linear-gradient(180deg, rgba(5, 16, 22, .22), rgba(5, 16, 22, .58));
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 34px;
    }
    .brand { display: flex; flex-direction: column; gap: 4px; }
    .brand h1 { margin: 0; font-size: clamp(22px, 3vw, 34px); letter-spacing: 0; }
    .brand span { color: var(--muted); font-size: 14px; }
    .nav { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .pill, button {
      border: 1px solid var(--line);
      background: rgba(255,255,255,.11);
      color: var(--text);
      border-radius: 999px;
      padding: 9px 14px;
      backdrop-filter: blur(18px);
      font-size: 13px;
    }
    button { cursor: pointer; }
    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(330px, .75fr);
      gap: 22px;
      align-items: stretch;
    }
    .glass {
      border: 1px solid var(--line);
      background: linear-gradient(145deg, rgba(13,29,38,.78), rgba(255,255,255,.08));
      backdrop-filter: blur(24px);
      border-radius: 8px;
      box-shadow: 0 24px 70px rgba(0,0,0,.22);
    }
    .stage { padding: clamp(22px, 4vw, 42px); min-height: 560px; position: relative; overflow: hidden; }
    .stage-title { max-width: 720px; }
    .eyebrow { color: var(--mint); font-weight: 800; letter-spacing: 0; font-size: 13px; }
    .headline {
      margin: 12px 0 10px;
      font-size: clamp(36px, 6.4vw, 76px);
      line-height: 1.02;
      letter-spacing: 0;
    }
    .headline small { display: block; font-size: .32em; color: var(--muted); margin-top: 12px; font-weight: 500; line-height: 1.55; max-width: 680px; }
    .hero-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 24px; align-items: center; }
    .detect-main {
      min-width: 190px;
      border: 0;
      color: #062019;
      background: linear-gradient(90deg, #9ee7c5, #dffff0);
      box-shadow: 0 18px 42px rgba(158, 231, 197, .28);
      font-size: 17px;
      padding: 15px 24px;
    }
    .detect-main.running {
      color: #fff;
      background: linear-gradient(90deg, #ff5f7e, #f7c8d8);
      box-shadow: 0 18px 42px rgba(255, 95, 126, .24);
    }
    .system-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 22px;
    }
    .system-chip {
      min-height: 74px;
      padding: 13px 14px;
      border: 1px solid rgba(255,255,255,.16);
      border-radius: 8px;
      background: rgba(255,255,255,.09);
    }
    .system-chip span { display: block; color: var(--muted); font-size: 12px; margin-bottom: 6px; }
    .system-chip b { font-size: 16px; }
    .wave-wrap { margin-top: 34px; height: 190px; position: relative; }
    canvas { width: 100%; height: 190px; display: block; }
    .sleep-axis {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-top: 28px;
    }
    .axis-item {
      border-top: 2px solid rgba(255,255,255,.35);
      padding-top: 10px;
      color: var(--muted);
      min-height: 58px;
    }
    .axis-item b { color: var(--text); display: block; font-size: 16px; margin-bottom: 4px; }
    .side { display: grid; gap: 18px; }
    .status-card { padding: 24px; }
    .status-top { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
    .status-label { color: var(--muted); font-size: 14px; }
    .live-dot { display: inline-flex; align-items: center; gap: 7px; color: var(--muted); font-size: 13px; }
    .live-dot::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: rgba(255,255,255,.42); box-shadow: 0 0 0 6px rgba(255,255,255,.08); }
    .live-dot.on::before { background: var(--mint); box-shadow: 0 0 0 6px rgba(158,231,197,.16); }
    .status-value { font-size: clamp(40px, 5.6vw, 66px); font-weight: 900; margin: 12px 0 8px; line-height: 1.05; }
    .instant { color: var(--muted); }
    .metric-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 22px; }
    .metric { border: 1px solid rgba(255,255,255,.16); background: rgba(255,255,255,.09); border-radius: 8px; padding: 14px; min-height: 78px; }
    .metric span { color: var(--muted); font-size: 12px; }
    .metric b { display: block; font-size: 22px; margin-top: 4px; }
    .prob-card, .log-card { padding: 20px; }
    .section-title { display: flex; justify-content: space-between; color: var(--muted); font-size: 14px; margin-bottom: 14px; }
    .bar-row { margin: 15px 0; }
    .bar-label { display: flex; justify-content: space-between; font-size: 14px; margin-bottom: 7px; }
    .bar { height: 11px; background: rgba(255,255,255,.16); border-radius: 999px; overflow: hidden; }
    .bar span { display: block; height: 100%; border-radius: 999px; transition: width .25s; }
    .bar span.unmanned { background: linear-gradient(90deg, var(--aqua), #d7f3ff); }
    .bar span.still { background: linear-gradient(90deg, var(--mint), #dcffe9); }
    .bar span.roll { background: linear-gradient(90deg, var(--rose), var(--gold)); }
    .mini-report {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-top: 22px;
    }
    .report-item { padding: 16px; border-radius: 8px; background: rgba(255,255,255,.11); border: 1px solid rgba(255,255,255,.18); }
    .report-item b { display: block; font-size: 24px; margin-bottom: 6px; }
    .report-item span { color: var(--muted); font-size: 13px; }
    .logs { font-family: Consolas, monospace; font-size: 12px; max-height: 190px; overflow: auto; color: #e9f7ff; }
    .logline { padding: 7px 0; border-bottom: 1px solid rgba(255,255,255,.10); }
    .sub { color: var(--muted); line-height: 1.7; }
    .warn { color: #ffe1a6; margin-top: 8px; }
    @media (max-width: 960px) {
      .hero { grid-template-columns: 1fr; }
      .stage { min-height: auto; }
    }
    @media (max-width: 620px) {
      .topbar { align-items: flex-start; flex-direction: column; }
      .system-strip, .sleep-axis, .mini-report, .metric-grid { grid-template-columns: 1fr; }
      .headline { font-size: 36px; }
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background:
        linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px),
        linear-gradient(180deg, rgba(255,255,255,.035) 1px, transparent 1px);
      background-size: 72px 72px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,.75), transparent 76%);
    }
    body::after {
      content: "";
      position: fixed;
      inset: auto 0 0 0;
      height: 34vh;
      pointer-events: none;
      background: linear-gradient(180deg, transparent, rgba(4,12,16,.72));
    }
    .topbar {
      position: relative;
      z-index: 2;
      padding: 14px 16px;
      border: 1px solid rgba(255,255,255,.14);
      border-radius: 8px;
      background: rgba(6, 17, 23, .42);
      backdrop-filter: blur(20px);
    }
    .brand h1 {
      text-wrap: balance;
      text-shadow: 0 10px 34px rgba(0,0,0,.34);
    }
    .pill, button {
      transition: transform .18s ease, border-color .18s ease, background .18s ease, box-shadow .18s ease;
    }
    .pill:hover, button:hover {
      transform: translateY(-1px);
      border-color: rgba(158,231,197,.46);
      background: rgba(158,231,197,.14);
    }
    .stage::before {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background:
        radial-gradient(circle at 14% 18%, rgba(158,231,197,.20), transparent 27%),
        radial-gradient(circle at 84% 12%, rgba(139,212,255,.17), transparent 24%);
    }
    .stage > * { position: relative; z-index: 1; }
    .headline {
      max-width: 780px;
      text-shadow: 0 18px 44px rgba(0,0,0,.30);
      text-wrap: balance;
    }
    .headline small { text-wrap: pretty; }
    .detect-main {
      letter-spacing: 0;
      position: relative;
      overflow: hidden;
    }
    .detect-main::after {
      content: "";
      position: absolute;
      inset: 0;
      transform: translateX(-120%);
      background: linear-gradient(90deg, transparent, rgba(255,255,255,.42), transparent);
      transition: transform .55s ease;
    }
    .detect-main:hover::after { transform: translateX(120%); }
    .system-chip, .metric, .report-item, .axis-item {
      transition: transform .18s ease, background .18s ease, border-color .18s ease;
    }
    .system-chip:hover, .metric:hover, .report-item:hover {
      transform: translateY(-2px);
      border-color: rgba(158,231,197,.34);
      background: rgba(255,255,255,.13);
    }
    .wave-wrap {
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 8px;
      background:
        linear-gradient(180deg, rgba(255,255,255,.05), rgba(255,255,255,.02)),
        repeating-linear-gradient(90deg, rgba(255,255,255,.08) 0 1px, transparent 1px 42px);
      padding: 8px;
    }
    .status-value {
      word-break: keep-all;
      overflow-wrap: anywhere;
    }
    .bar {
      box-shadow: inset 0 1px 8px rgba(0,0,0,.22);
    }
    .bar span {
      box-shadow: 0 0 18px rgba(158,231,197,.24);
    }
    .logs::-webkit-scrollbar { width: 8px; }
    .logs::-webkit-scrollbar-thumb { background: rgba(255,255,255,.22); border-radius: 999px; }
    @media (max-width: 620px) {
      .app { padding: 14px 12px 26px; }
      .topbar { padding: 12px; }
      .nav { width: 100%; }
      .pill, .nav button { flex: 1 1 auto; text-align: center; }
      .stage { padding: 20px; }
    }
  </style>
</head>
<body>
  <div class="app">
    <nav class="topbar">
      <div class="brand">
        <h1>无源 WiFi 人体微动与睡眠监测系统</h1>
        <span>WiFi CSI · 无感监测 · 实时状态识别</span>
      </div>
      <div class="nav">
        <a class="pill" href="/">实时看板</a>
        <a class="pill" href="/home">个人主页</a>
        <a class="pill" href="/community">社区</a>
        <span class="pill">COM13 实时采集</span>
        <span class="pill">三状态模型</span>
        <button id="themeBtn">切换星空</button>
      </div>
    </nav>
    <main class="hero">
      <section class="stage glass">
        <div class="stage-title">
          <div class="eyebrow">ESP32 CSI 实时识别</div>
          <div class="headline">无源 WiFi 睡眠微动监测<small>把串口 CSI 幅度窗口转化为无人、静止、翻滚三类状态反馈，适合现场演示和答辩讲解。</small></div>
          <div class="hero-actions">
            <button id="detectBtn" class="detect-main">开启检测</button>
          </div>
        </div>
        <div class="system-strip">
          <div class="system-chip"><span>采集设备</span><b>ESP32-S3 接收端</b></div>
          <div class="system-chip"><span>输入信号</span><b>CSI 幅度序列</b></div>
          <div class="system-chip"><span>识别方式</span><b>滑动窗口分类</b></div>
          <div class="system-chip"><span>展示层</span><b>FastAPI 看板</b></div>
        </div>
        <div class="wave-wrap"><canvas id="wave"></canvas></div>
        <div class="sleep-axis">
          <div class="axis-item"><b>无人</b>环境基线稳定</div>
          <div class="axis-item"><b>静止</b>人体微动感知</div>
          <div class="axis-item"><b>翻滚</b>体动状态识别</div>
          <div class="axis-item"><b>扩展</b>呼吸频率估计</div>
        </div>
        <div class="mini-report">
          <div class="report-item"><b id="packetRate">--</b><span>有效数据包</span></div>
          <div class="report-item"><b id="dominant">--</b><span>当前主状态</span></div>
          <div class="report-item"><b id="confidence">--</b><span>最高置信度</span></div>
        </div>
      </section>
      <aside class="side">
        <section class="status-card glass">
          <div class="status-top">
            <div class="status-label">稳定状态</div>
            <div id="liveDot" class="live-dot">待机</div>
          </div>
          <div id="stable" class="status-value">等待数据</div>
          <div id="instant" class="instant">当前窗口：等待数据</div>
          <div id="error" class="warn"></div>
          <div class="metric-grid">
            <div class="metric"><span title="成功解析并通过格式校验的 CSI 数据包数量">有效数据包</span><b id="packets">0</b></div>
            <div class="metric"><span>运行时长</span><b id="elapsed">0.0s</b></div>
            <div class="metric"><span>运行状态</span><b id="running">等待</b></div>
            <div class="metric"><span>窗口长度</span><b>128</b></div>
          </div>
        </section>
        <section class="prob-card glass">
          <div class="section-title"><span>状态概率</span><span>Random Forest</span></div>
          <div id="probs"></div>
        </section>
        <section class="log-card glass">
          <div class="section-title"><span>实时日志</span><span>Live</span></div>
          <div id="logs" class="logs"></div>
        </section>
      </aside>
    </main>
  </div>
  <script>
    function pct(v) { return `${(Number(v || 0) * 100).toFixed(1)}%`; }
    function cls(name) {
      if (name.includes('无人')) return 'unmanned';
      if (name.includes('静止')) return 'still';
      if (name.includes('翻滚')) return 'roll';
      return 'still';
    }
    const canvas = document.getElementById('wave');
    const ctx = canvas.getContext('2d');
    let phase = 0;
    let latestStrength = 0.5;
    function drawWave() {
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      canvas.width = rect.width * ratio;
      canvas.height = rect.height * ratio;
      ctx.scale(ratio, ratio);
      ctx.clearRect(0, 0, rect.width, rect.height);
      const mid = rect.height * 0.52;
      const amp = 18 + latestStrength * 32;
      for (let layer = 0; layer < 3; layer++) {
        ctx.beginPath();
        ctx.lineWidth = layer === 0 ? 3 : 1.4;
        ctx.strokeStyle = layer === 0 ? 'rgba(158,231,197,.95)' : layer === 1 ? 'rgba(139,212,255,.55)' : 'rgba(247,200,216,.42)';
        for (let x = 0; x <= rect.width; x += 4) {
          const y = mid + Math.sin((x / 55) + phase + layer * .9) * (amp - layer * 8)
            + Math.sin((x / 21) + phase * 1.4) * 4;
          if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      phase += 0.035;
      requestAnimationFrame(drawWave);
    }
    drawWave();
    document.getElementById('themeBtn').addEventListener('click', () => {
      document.body.classList.toggle('night');
      document.getElementById('themeBtn').textContent = document.body.classList.contains('night') ? '切换森林' : '切换星空';
    });
    async function toggleDetection() {
      const running = document.getElementById('detectBtn').dataset.running === 'true';
      if (!running) {
        const currentUser = JSON.parse(localStorage.getItem('csi_user') || 'null');
        const users = JSON.parse(localStorage.getItem('csi_users') || '{}');
        if (!currentUser || !currentUser.username || !users[currentUser.username]) {
          localStorage.removeItem('csi_user');
          location.href = '/home?auth=1';
          return;
        }
      }
      const endpoint = running ? '/api/stop' : '/api/start';
      const currentUser = JSON.parse(localStorage.getItem('csi_user') || 'null');
      await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: currentUser && currentUser.username ? JSON.stringify({ username: currentUser.username }) : '{}'
      });
      setTimeout(refresh, 500);
    }
    document.getElementById('detectBtn').addEventListener('click', toggleDetection);
    async function refresh() {
      const res = await fetch('/api/state');
      const s = await res.json();
      document.getElementById('stable').textContent = s.stable_prediction || '等待数据';
      document.getElementById('instant').textContent = `当前窗口：${s.prediction || '等待数据'}`;
      document.getElementById('packets').textContent = s.packets || 0;
      document.getElementById('packetRate').textContent = s.packets || 0;
      document.getElementById('dominant').textContent = s.stable_prediction || '--';
      document.getElementById('elapsed').textContent = `${Number(s.elapsed || 0).toFixed(1)}s`;
      document.getElementById('running').textContent = s.running ? '运行中' : '停止';
      const detectBtn = document.getElementById('detectBtn');
      const liveDot = document.getElementById('liveDot');
      detectBtn.dataset.running = s.running ? 'true' : 'false';
      detectBtn.textContent = s.running ? '关闭检测' : '开启检测';
      detectBtn.classList.toggle('running', Boolean(s.running));
      liveDot.textContent = s.running ? '运行中' : '待机';
      liveDot.classList.toggle('on', Boolean(s.running));
      document.getElementById('error').textContent = s.error ? `错误：${s.error}` : '';
      const probs = s.probabilities || {};
      const maxProb = Math.max(0, ...Object.values(probs).map(Number));
      latestStrength = maxProb;
      document.getElementById('confidence').textContent = probs && Object.keys(probs).length ? pct(maxProb) : '--';
      document.getElementById('probs').innerHTML = Object.entries(probs).map(([k, v]) => `
        <div class="bar-row">
          <div class="bar-label"><span>${k}</span><strong>${pct(v)}</strong></div>
          <div class="bar"><span class="${cls(k)}" style="width:${pct(v)}"></span></div>
        </div>`).join('') || '<div class="sub">等待首个窗口</div>';
      document.getElementById('logs').innerHTML = (s.logs || []).slice().reverse().map(
        l => `<div class="logline">[${l.time}] ${l.message}</div>`
      ).join('');
    }
    setInterval(refresh, 700);
    refresh();
  </script>
</body>
</html>
"""


@app.get("/login", response_class=HTMLResponse)
def login_page() -> str:
    return read_page("home.html")


@app.get("/home", response_class=HTMLResponse)
def personal_home_page() -> str:
    return read_page("home.html")


@app.get("/community", response_class=HTMLResponse)
def community_page() -> str:
    return read_page("community.html")


def main() -> None:
    parser = argparse.ArgumentParser(description="CSI real-time web dashboard")
    parser.add_argument("--port", default="COM13")
    parser.add_argument("--baudrate", type=int, default=921600)
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--http_port", type=int, default=8000)
    parser.add_argument("--window", type=int, default=WINDOW_SIZE)
    parser.add_argument("--step", type=int, default=STEP_SIZE)
    parser.add_argument("--smooth", type=int, default=5)
    parser.add_argument("--min_confidence", type=float, default=0.60)
    args = parser.parse_args()

    monitor_config.update(
        {
            "port": args.port,
            "baudrate": args.baudrate,
            "model_path": args.model,
            "window_size": args.window,
            "step_size": args.step,
            "smooth": args.smooth,
            "min_confidence": args.min_confidence,
        }
    )
    add_log("系统已就绪，等待用户开启检测")
    print(f"Open dashboard: http://{args.host}:{args.http_port}")
    uvicorn.run(app, host=args.host, port=args.http_port, log_level="warning")


if __name__ == "__main__":
    main()
