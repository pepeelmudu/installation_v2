# tests/test_ws_server.py
import pytest
import asyncio
from fastapi.testclient import TestClient
import ws_server
from ws_server import app, broadcast, connected_clients, has_audience

def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

def test_app_served_at_root():
    # App is mounted at "/" (commit 75fb072 dropped the /face/ prefix).
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_broadcast_sends_to_connected_clients():
    from unittest.mock import AsyncMock
    mock_ws = AsyncMock()
    connected_clients.add(mock_ws)
    await broadcast({"type": "mood_change", "mood": "hostile"})
    mock_ws.send_json.assert_called_once_with({"type": "mood_change", "mood": "hostile"})
    connected_clients.discard(mock_ws)

@pytest.mark.asyncio
async def test_broadcast_removes_disconnected_client():
    from unittest.mock import AsyncMock
    from websockets.exceptions import ConnectionClosedOK
    mock_ws = AsyncMock()
    mock_ws.send_json.side_effect = Exception("disconnected")
    connected_clients.add(mock_ws)
    await broadcast({"type": "test"})
    assert mock_ws not in connected_clients


def test_has_audience_false_when_no_audio_client():
    # No browser on /audio → nobody can hear proactive speech, so the proactive
    # loop must NOT synthesize (otherwise an idle deployment burns TTS credits).
    saved = ws_server._audio_client
    try:
        ws_server._audio_client = None
        assert has_audience() is False
    finally:
        ws_server._audio_client = saved


def test_has_audience_true_when_audio_client_connected():
    from unittest.mock import AsyncMock
    saved = ws_server._audio_client
    try:
        ws_server._audio_client = AsyncMock()
        assert has_audience() is True
    finally:
        ws_server._audio_client = saved
