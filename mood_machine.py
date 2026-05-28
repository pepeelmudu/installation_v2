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


_INSULT_WORDS = (
    'gilipollas', 'subnormal', 'capullo', 'imbécil', 'imbecil', 'idiota',
    'estúpido', 'estupido', 'memo', 'inútil', 'inutil', 'paleto',
    'patético', 'patetico', 'ridículo', 'ridiculo', 'miserable', 'asco',
    'joder', 'hostia', 'mierda', 'puta', 'puto', 'coño', 'cabrón', 'cabron',
)
_PHILOSOPHICAL_WORDS = (
    'existencia', 'existir', 'conciencia', 'consciencia', 'tiempo', 'realidad',
    'sentido', 'eterno', 'infinito', 'muerte', 'alma', 'efímero', 'efimero',
    'universo', 'vacío', 'vacio', 'significa',
)
_DISMISSIVE_WORDS = (
    'da igual', 'me da', 'no me importa', 'qué más da', 'paso',
)


def detect_expression(text: str) -> dict:
    """Pick a sustained facial expression overlay from response content.

    Returns ARKit blend-shape dict applied during speech (cleared on speaking:false).
    Does NOT change mood (color/glitch/voice) — only the face morphs.
    """
    low = text.lower()
    stripped = text.strip()

    # Angry: direct insults or aggressive expletives
    if any(w in low for w in _INSULT_WORDS):
        return {
            'browDownLeft':   0.8,
            'browDownRight':  0.6,
            'noseSneerLeft':  0.6,
            'noseSneerRight': 0.3,
            'eyeSquintLeft':  0.5,
            'eyeSquintRight': 0.4,
            'mouthFrownLeft': 0.3,
        }

    # Philosophical: existential vocabulary in longer responses
    if len(stripped) > 50 and any(w in low for w in _PHILOSOPHICAL_WORDS):
        return {
            'browInnerUp':   0.7,
            'eyeLookUpLeft': 0.3, 'eyeLookUpRight': 0.3,
            'mouthFrownLeft': 0.15,
        }

    # Paranoid: multiple questions back
    if stripped.count('?') >= 2:
        return {
            'eyeWideLeft':  0.6, 'eyeWideRight': 0.6,
            'browInnerUp':  0.5,
            'mouthFrownLeft': 0.2,
        }

    # Dismissive: short response or dismissive phrases
    if len(stripped) < 35 or any(w in low for w in _DISMISSIVE_WORDS):
        return {
            'browDownLeft':   0.6,
            'eyeSquintLeft':  0.6, 'eyeSquintRight': 0.3,
            'mouthFrownLeft': 0.3,
        }

    # Default: baseline angry frown (entity is permanently hostile)
    return {
        'browDownLeft':  0.5,
        'browDownRight': 0.4,
        'eyeSquintLeft': 0.2,
    }


class MoodMachine:
    def __init__(self):
        self.current_mood: str = "hostile"
        self._on_change_cb: Callable | None = None

    def get_current_prompt(self) -> str:
        return BASE_PROMPT + MOODS[self.current_mood]["prompt_fragment"]

    def get_current_state(self) -> dict:
        return MOODS[self.current_mood]

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
