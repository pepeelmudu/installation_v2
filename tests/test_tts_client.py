import numpy as np
import pytest
from tts_client import TTSClient, _rms, _is_sentence_end

def test_rms_silence():
    silence = bytes(100)
    assert _rms(silence) == 0.0

def test_rms_max_amplitude():
    samples = np.full(100, 32767, dtype=np.int16)
    result = _rms(samples.tobytes())
    assert 0.99 < result <= 1.0

def test_rms_half_amplitude():
    samples = np.full(100, 16384, dtype=np.int16)
    result = _rms(samples.tobytes())
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
