from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.video.pipeline import get_video_pipeline

router = APIRouter(tags=["websockets"])


@router.websocket("/ws/recording-status")
async def ws_recording_status(websocket: WebSocket) -> None:
    await websocket.accept()
    pipeline = get_video_pipeline()
    try:
        while True:
            metrics = pipeline.recording_metrics()
            capture = pipeline.capture_status()
            payload = {
                "type": "recording_status",
                "data": {
                    **{k: v for k, v in metrics.items() if k != "last_snapshots"},
                    "capture": capture.model_dump(),
                },
            }
            await websocket.send_text(json.dumps(payload, default=str))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return


@router.websocket("/ws/session-status")
async def ws_session_status(websocket: WebSocket) -> None:
    await websocket.accept()
    pipeline = get_video_pipeline()
    try:
        while True:
            metrics = pipeline.recording_metrics()
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "session_status",
                        "data": {
                            "session_public_id": metrics.get("session_public_id"),
                            "state": metrics.get("state"),
                            "remote_connected": metrics.get("remote_connected"),
                            "snapshot_count": metrics.get("snapshot_count"),
                        },
                    },
                    default=str,
                )
            )
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
