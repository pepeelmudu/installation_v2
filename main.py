import asyncio
from concurrent.futures import ThreadPoolExecutor
from config import (
    DEEPGRAM_API_KEY, GROQ_API_KEY,
    ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID,
    GROQ_MODEL, SERVER_PORT,
)
from mood_machine import MoodMachine
from llm_client import LLMClient
from tts_client import TTSClient
from stt_client import STTClient
from ws_server import app, broadcast
import uvicorn

mood_machine = MoodMachine()
llm_client = LLMClient(api_key=GROQ_API_KEY, model=GROQ_MODEL)
tts_client: TTSClient | None = None
stt_client: STTClient | None = None
_speaking = False
_executor = ThreadPoolExecutor(max_workers=2)


async def on_amplitude(value: float) -> None:
    await broadcast({"type": "amplitude", "value": round(value, 3)})


async def on_speaking(value: bool) -> None:
    global _speaking
    _speaking = value
    await broadcast({"type": "speaking", "value": value})


async def on_transcript(text: str) -> None:
    if _speaking:
        return  # Ignore input while speaking
    await broadcast({"type": "text", "value": text})
    system_prompt = mood_machine.get_current_prompt()

    # llm_client.stream() is a sync generator — run in executor to avoid
    # blocking the asyncio event loop during LLM generation.
    loop = asyncio.get_running_loop()
    def _stream_and_feed():
        for token in llm_client.stream(text, system_prompt):
            tts_client.feed(token)
        tts_client.flush()

    await loop.run_in_executor(_executor, _stream_and_feed)


async def on_mood_change(mood_id: str, state: dict) -> None:
    tts_client.set_mood(mood_id)
    await broadcast({
        "type": "mood_change",
        "mood": mood_id,
        "color": state["color"],
        "glitch": state["glitch"],
    })


async def run_pipeline() -> None:
    global tts_client, stt_client
    loop = asyncio.get_running_loop()

    tts_client = TTSClient(
        api_key=ELEVENLABS_API_KEY,
        voice_id=ELEVENLABS_VOICE_ID,
        on_amplitude=on_amplitude,
        on_speaking=on_speaking,
        loop=loop,
    )
    tts_client.set_mood(mood_machine.current_mood)

    stt_client = STTClient(
        api_key=DEEPGRAM_API_KEY,
        on_transcript=on_transcript,
    )

    await stt_client.start()
    print(f"[ENTITY] Listening on port {SERVER_PORT}. Open http://<this-ip>:{SERVER_PORT}/face on iPad.")
    await mood_machine.run(on_change=on_mood_change)


async def main() -> None:
    server = uvicorn.Server(
        uvicorn.Config(app, host="0.0.0.0", port=SERVER_PORT, log_level="warning")
    )
    await asyncio.gather(
        server.serve(),
        run_pipeline(),
    )


if __name__ == "__main__":
    asyncio.run(main())
