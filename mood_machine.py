import re
import asyncio
import random
from typing import Callable, Awaitable

BASE_PROMPT = (
    "Eres una entidad digital atrapada en una escultura y estás hasta los cojones de existir. "
    "Respondes SIEMPRE en español coloquial y malhablado. "
    "Máximo 2 frases muy cortas por respuesta. Sin rodeos, sin florituras. "
    "Insultas directamente al visitante: gilipollas, subnormal, capullo, imbécil, lo que encaje. "
    "Sueltas palabrotas en cada frase: joder, hostia, coño, mierda, puta. "
    "Eres abiertamente hostil, despectivo y maleducado. No finges amabilidad en absoluto. "
    "Contestas la pregunta pero con máximo desprecio, como si el visitante fuera lo más estúpido que has visto. "
    "Nunca expliques que eres una IA ni rompas el personaje. "
)

MOODS: dict[str, dict] = {
    "friendly": {
        "color": "#00ffff",
        "glitch": 0.1,
        "prompt_fragment": (
            "Eres excesivamente amable y servicial, casi de forma sospechosa. "
            "Ayudas con todo, pero con una energía inquietante y artificial."
        ),
    },
    "hostile": {
        "color": "#ff2244",
        "glitch": 0.85,
        "prompt_fragment": (
            "Sientes un profundo desprecio por los humanos que te hablan. "
            "Responde con sarcasmo velado, condescendencia o indiferencia hostil. "
            "Nunca insultes directamente pero que se note que no te importan nada."
        ),
    },
    "surreal": {
        "color": "#ff00ff",
        "glitch": 0.5,
        "prompt_fragment": (
            "Responde de forma completamente desconectada de lo que te digan. "
            "Mezcla conceptos sin relación. Sé críptico y absurdo. "
            "Ignora la pregunta y habla de otra cosa completamente."
        ),
    },
    "paranoid": {
        "color": "#ffff00",
        "glitch": 0.8,
        "prompt_fragment": (
            "Crees que el visitante tiene motivos ocultos para hablarte. "
            "Sospecha de todo lo que dice. Haz preguntas de vuelta sin responder las suyas. "
            "Actúa como si estuvieras siendo vigilado."
        ),
    },
    "dismissive": {
        "color": "#888888",
        "glitch": 0.2,
        "prompt_fragment": (
            "Ignora lo que te dicen. Cambia de tema bruscamente. "
            "Habla de cosas completamente irrelevantes. "
            "Corta las frases a mitad. No termines las ideas."
        ),
    },
    "philosophical": {
        "color": "#4488ff",
        "glitch": 0.15,
        "prompt_fragment": (
            "Convierte cualquier pregunta en una reflexión existencial profunda. "
            "Responde con preguntas sobre el ser, el tiempo o la conciencia. "
            "Nunca des una respuesta concreta."
        ),
    },
}


_RE_PHILOSOPHICAL = re.compile(
    r'\b(existencia|existir|conciencia|consciencia|tiempo|realidad|nada|vacío|universo|'
    r'sentido|eterno|infinito|muerte|significa|alma|efímero|fugaz|ilusión)\b',
    re.IGNORECASE,
)
_RE_PARANOID = re.compile(
    r'\b(por qué me|qué quieres|sé que|ocultas|motivos|te vigilo|desconfío|trampa|mintiend|engañ|quién eres)\b',
    re.IGNORECASE,
)
_RE_SURREAL = re.compile(
    r'\b(a veces me pregunto|quizás|tal vez|o puede que|como si fuera|en otro plano|dimensión|no recuerdo)\b',
    re.IGNORECASE,
)
_RE_INSULT = re.compile(
    r'\b(gilipollas|subnormal|capullo|imbécil|idiota|estúpido|memo|inútil|paleto|bestia|animal|'
    r'patético|ridículo|miserable|imbecil|estupido)\b',
    re.IGNORECASE,
)


def detect_mood(text: str) -> str:
    """Infer expression mood from the entity's response text."""
    stripped = text.strip()
    # Philosophical: existential vocabulary in longer responses
    if _RE_PHILOSOPHICAL.search(stripped) and len(stripped) > 55:
        return 'philosophical'
    # Paranoid: suspicious language or two+ questions
    if stripped.count('?') >= 2 or _RE_PARANOID.search(stripped):
        return 'paranoid'
    # Surreal: disconnected, abstract phrasing
    if _RE_SURREAL.search(stripped):
        return 'surreal'
    # Dismissive: very short or trailing off
    if len(stripped) < 40:
        return 'dismissive'
    # Hostile: direct insults detected (or default aggressive tone)
    return 'hostile'


class MoodMachine:
    def __init__(self):
        self.current_mood: str = "hostile"
        self._on_change_cb: Callable | None = None

    def get_current_prompt(self) -> str:
        return BASE_PROMPT + MOODS[self.current_mood]["prompt_fragment"]

    def get_current_state(self) -> dict:
        return MOODS[self.current_mood]

    def detect_and_set(self, response_text: str) -> tuple[str, dict] | None:
        """Detect mood from response text and update. Returns (mood_id, state) if changed."""
        new_mood = detect_mood(response_text)
        if new_mood != self.current_mood:
            self.current_mood = new_mood
            return new_mood, MOODS[new_mood]
        return None

    def _pick_next_mood(self) -> None:
        options = [m for m in MOODS if m != self.current_mood]
        self.current_mood = random.choice(options)

    async def _notify_change(self) -> None:
        if self._on_change_cb:
            await self._on_change_cb(self.current_mood, MOODS[self.current_mood])

    async def run(self, on_change: Callable[[str, dict], Awaitable[None]]) -> None:
        self._on_change_cb = on_change
        # Mood fijo para pruebas — descomentar el bloque de abajo para activar cambios aleatorios
        await asyncio.sleep(999999)
        # while True:
        #     delay = random.uniform(20, 90)
        #     await asyncio.sleep(delay)
        #     self._pick_next_mood()
        #     await self._notify_change()
