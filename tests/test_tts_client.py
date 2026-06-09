import asyncio
import struct
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from tts_client import (
    TTSClient, _rms, _is_sentence_end, _SynthJob,
    format_tts_error, low_credit_message,
)
from config import ELEVENLABS_MODEL, ELEVENLABS_MODEL_V3


class _FakeApiError(Exception):
    """Mimics elevenlabs.core.ApiError: empty repr, info hidden in attrs."""
    def __init__(self, status_code, body):
        super().__init__()
        self.status_code = status_code
        self.body = body

    def __repr__(self):
        return "ApiError()"


def test_format_tts_error_surfaces_quota_message():
    e = _FakeApiError(401, {"detail": {
        "code": "quota_exceeded",
        "message": "You have 0 credits remaining",
        "status": "quota_exceeded",
    }})
    out = format_tts_error(e)
    assert "401" in out
    assert "quota_exceeded" in out
    assert "0 credits remaining" in out
    assert out != "ApiError()"


def test_format_tts_error_handles_missing_permissions():
    e = _FakeApiError(401, {"detail": {
        "status": "missing_permissions",
        "message": "missing the permission user_read",
    }})
    out = format_tts_error(e)
    assert "missing_permissions" in out
    assert "user_read" in out


def test_format_tts_error_falls_back_to_repr_for_plain_exception():
    assert format_tts_error(ValueError("boom")) == repr(ValueError("boom"))


def test_low_credit_message_none_when_healthy():
    assert low_credit_message(remaining=90000, limit=100000) is None


def test_low_credit_message_warns_below_threshold():
    msg = low_credit_message(remaining=5000, limit=100000)  # 5% < 10%
    assert msg is not None
    assert "LOW" in msg


def test_low_credit_message_exhausted_at_zero():
    msg = low_credit_message(remaining=0, limit=100000)
    assert msg is not None
    assert "EXHAUSTED" in msg


def test_low_credit_message_none_when_limit_unknown():
    assert low_credit_message(remaining=0, limit=0) is None


def _make_client():
    import asyncio
    from unittest.mock import AsyncMock
    loop = asyncio.new_event_loop()
    return TTSClient(api_key="fake", voice_id="v", on_amplitude=AsyncMock(),
                     on_speaking=AsyncMock(), on_viseme_schedule=AsyncMock(),
                     on_audio_chunk=AsyncMock(), loop=loop)


def test_feed_flush_enqueues_flash_job_with_timestamps():
    c = _make_client()
    try:
        c.feed("This is a full sentence that ends here.")
        job = c._synth_queue.get_nowait()
        assert isinstance(job, _SynthJob)
        assert job.model_id == ELEVENLABS_MODEL
        assert job.use_timestamps is True
    finally:
        c.close()
        c._loop.close()


def test_say_special_uses_flash_with_timestamps_and_strips_tags():
    # Shouts are synthesized on Flash WITH timestamps (so the mouth lip-syncs like
    # normal speech), and any v3 audio tags are stripped (Flash would read them).
    c = _make_client()
    try:
        c.say_special("[shouts] BITCOIN PUMPED", mood="shout")
        job = c._synth_queue.get_nowait()
        assert isinstance(job, _SynthJob)
        assert job.model_id == ELEVENLABS_MODEL
        assert job.use_timestamps is True
        assert "[shouts]" not in job.text
        assert "BITCOIN PUMPED" in job.text
    finally:
        c.close()
        c._loop.close()


def test_say_special_normal_mood_uses_flash():
    c = _make_client()
    try:
        c.say_special("whatever human", mood="normal")
        job = c._synth_queue.get_nowait()
        assert job.model_id == ELEVENLABS_MODEL
    finally:
        c.close()
        c._loop.close()

def test_rms_silence():
    silence = bytes(100)
    assert _rms(silence) == 0.0

def test_rms_max_amplitude():
    samples = struct.pack("<" + "h" * 100, *([32767] * 100))
    result = _rms(samples)
    assert 0.99 < result <= 1.0

def test_rms_half_amplitude():
    samples = struct.pack("<" + "h" * 100, *([16384] * 100))
    result = _rms(samples)
    assert 0.4 < result < 0.6

def test_rms_empty_bytes():
    assert _rms(b"") == 0.0

def test_is_sentence_end_period():
    assert _is_sentence_end("Hola mundo.", 5) is True

def test_is_sentence_end_exclamation():
    assert _is_sentence_end("¡Qué interesante!", 5) is True

def test_is_sentence_end_question():
    assert _is_sentence_end("¿Qué quieres?", 5) is True

def test_is_sentence_end_too_short():
    assert _is_sentence_end("No.", 5) is False

def test_is_sentence_end_no_punctuation():
    assert _is_sentence_end("esto no termina", 20) is False

def test_feed_flushes_on_sentence_end():
    flushed = []
    client = TTSClient.__new__(TTSClient)
    client._buffer = ""
    client._flush_cb = lambda text: flushed.append(text)
    from tts_client import _is_sentence_end, SENTENCE_MIN_CHARS
    client._buffer = "Eres muy molesto conmigo."
    if _is_sentence_end(client._buffer, SENTENCE_MIN_CHARS):
        client._flush_cb(client._buffer.strip())
        client._buffer = ""
    assert flushed == ["Eres muy molesto conmigo."]


@pytest.mark.asyncio
async def test_audio_chunk_callback_called():
    """TTSClient calls on_audio_chunk with each PCM chunk instead of sounddevice."""
    received_chunks = []

    async def capture_chunk(data: bytes):
        received_chunks.append(data)

    with patch("tts_client.ElevenLabs") as MockEL:
        mock_client = MagicMock()
        MockEL.return_value = mock_client

        fake_chunk = MagicMock()
        fake_chunk.audio_bytes = b"\x10\x20" * 100
        fake_chunk.alignment = None
        mock_client.text_to_speech.stream_with_timestamps.return_value = iter([fake_chunk])

        loop = asyncio.get_running_loop()
        from tts_client import TTSClient
        tts = TTSClient(
            api_key="test",
            voice_id="test_voice",
            on_amplitude=AsyncMock(),
            on_speaking=AsyncMock(),
            on_viseme_schedule=AsyncMock(),
            on_audio_chunk=capture_chunk,
            loop=loop,
        )
        tts.feed("Hola mundo.")
        tts.flush()
        await asyncio.sleep(0.3)
        assert len(received_chunks) > 0
        tts.close()


def test_flush_buffer_enqueues_without_ending_turn():
    c = _make_client()
    try:
        c.feed("Hi.")                      # too short to auto-enqueue (<20 chars)
        assert c._synth_queue.empty()      # still buffered
        c.flush_buffer()
        job = c._synth_queue.get_nowait()  # now enqueued
        assert isinstance(job, _SynthJob)
        assert c._flushed is False         # turn NOT ended
    finally:
        c.close()
        c._loop.close()


def test_rms_pure_python():
    """_rms returns 0 for silence and >0 for signal."""
    from tts_client import _rms
    assert _rms(b"") == 0.0
    assert _rms(bytes(100)) == 0.0  # silence
    # Max amplitude int16 = 32767 → rms should be ~1.0
    import struct
    loud = struct.pack("<" + "h" * 50, *([32767] * 50))
    assert _rms(loud) > 0.9


def test_say_special_shout_is_faster():
    # Shouts use the intense 'shout' preset, which speaks faster (speed > 1).
    c = _make_client()
    try:
        c.say_special("BITCOIN PUMPED", mood="shout")
        job = c._synth_queue.get_nowait()
        assert getattr(job.voice_settings, "speed", 1.0) > 1.0
    finally:
        c.close()
        c._loop.close()


import time


def _make_client_with_audience(has_audience):
    loop = asyncio.new_event_loop()
    return TTSClient(api_key="fake", voice_id="v", on_amplitude=AsyncMock(),
                     on_speaking=AsyncMock(), on_viseme_schedule=AsyncMock(),
                     on_audio_chunk=AsyncMock(), loop=loop, has_audience=has_audience)


def test_no_audience_means_zero_elevenlabs_calls():
    # The credit-burn guarantee: with no browser connected, NOTHING reaches the
    # ElevenLabs API — not one credit can be spent talking to an empty room.
    c = _make_client_with_audience(lambda: False)
    try:
        c._client.text_to_speech.stream = MagicMock(return_value=iter([]))
        c._client.text_to_speech.stream_with_timestamps = MagicMock(return_value=iter([]))
        c.feed("This is a full sentence that should never be synthesized.")
        c.flush()
        time.sleep(0.3)
        assert c._client.text_to_speech.stream.called is False
        assert c._client.text_to_speech.stream_with_timestamps.called is False
    finally:
        c.close()
        c._loop.close()


def test_with_audience_synthesis_proceeds():
    c = _make_client_with_audience(lambda: True)
    try:
        c._client.text_to_speech.stream = MagicMock(return_value=iter([]))
        c._client.text_to_speech.stream_with_timestamps = MagicMock(return_value=iter([]))
        c.feed("This is a full sentence that should be synthesized now.")
        c.flush()
        time.sleep(0.3)
        # at least one API path was hit (timestamps, with plain as fallback)
        assert (c._client.text_to_speech.stream_with_timestamps.called
                or c._client.text_to_speech.stream.called)
    finally:
        c.close()
        c._loop.close()


def test_stream_plain_falls_back_to_flash_when_v3_fails():
    c = _make_client()
    try:
        calls = []

        def fake_stream(voice_id, text=None, model_id=None, **kwargs):
            calls.append((model_id, text))
            if model_id == ELEVENLABS_MODEL_V3:
                raise RuntimeError("v3 not available on streaming")
            return iter([b"\x00\x01"])

        c._client.text_to_speech.stream = fake_stream
        job = _SynthJob("[shouts] hello", model_id=ELEVENLABS_MODEL_V3,
                        use_timestamps=False)
        c._stream_plain(job, c._mood_voice_settings("shout"))
        # first call v3 (failed), second call Flash with the tag stripped
        assert calls[0][0] == ELEVENLABS_MODEL_V3
        assert calls[1][0] == ELEVENLABS_MODEL
        assert "[shouts]" not in calls[1][1]
        assert "hello" in calls[1][1]
    finally:
        c.close()
        c._loop.close()
