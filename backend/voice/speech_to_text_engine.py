from typing import Dict, Any
from uuid import uuid4
from datetime import datetime

import speech_recognition as sr

from backend.events.event_bus import (
    event_bus
)

from backend.events.event_models import (
    CognitionEvent
)

from backend.tools.tool_registry import (
    tool_registry
)


# ==========================================
# SPEECH TO TEXT ENGINE
# ==========================================

class SpeechToTextEngine:

    def __init__(self):

        # ==========================================
        # RECOGNIZER
        # ==========================================

        self.recognizer = (
            sr.Recognizer()
        )

        # ==========================================
        # WAKE WORDS
        # ==========================================

        self.wake_words = [

            "hey cortex",
            "cortex",
            "jarvis",
            "hello cortex"
        ]

        # ==========================================
        # MICROPHONE
        # ==========================================

        self.microphone = (
            sr.Microphone()
        )


    # ==========================================
    # EVENT HELPER
    # ==========================================

    async def publish_event(

        self,

        execution_id: str,

        event_type: str,

        status: str,

        phase: str,

        message: str,

        payload: Dict[str, Any] = {}
    ):

        await event_bus.publish(

            CognitionEvent(

                agent=
                    "speech_to_text_engine",

                event_type=
                    event_type,

                status=
                    status,

                phase=
                    phase,

                execution_id=
                    execution_id,

                message=
                    message,

                payload=
                    payload
            )
        )


    # ==========================================
    # LISTEN FROM MICROPHONE
    # ==========================================

    async def listen_once(

        self

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        await self.publish_event(

            execution_id,

            "voice_listening_started",

            "running",

            "speech_capture",

            "Listening for speech input"
        )

        try:

            with self.microphone as source:

                # ==================================
                # NOISE ADJUSTMENT
                # ==================================

                self.recognizer.adjust_for_ambient_noise(

                    source,

                    duration=1
                )

                # ==================================
                # LISTEN
                # ==================================

                audio = self.recognizer.listen(

                    source,

                    timeout=10,

                    phrase_time_limit=15
                )

            # ======================================
            # GOOGLE SPEECH RECOGNITION
            # ======================================

            recognized_text = (

                self.recognizer
                .recognize_google(

                    audio
                )
            )

            await self.publish_event(

                execution_id,

                "speech_recognition_completed",

                "completed",

                "speech_recognition",

                "Speech successfully recognized",

                {

                    "recognized_text":
                        recognized_text
                }
            )

            return {

                "success": True,

                "recognized_text":
                    recognized_text,

                "timestamp":
                    datetime.utcnow()
                    .isoformat()
            }

        except sr.UnknownValueError:

            return {

                "success": False,

                "error":
                    "Speech could not be understood"
            }

        except sr.WaitTimeoutError:

            return {

                "success": False,

                "error":
                    "Listening timeout reached"
            }

        except Exception as error:

            await self.publish_event(

                execution_id,

                "speech_recognition_failed",

                "failed",

                "speech_recognition",

                "Speech recognition failed",

                {

                    "error":
                        str(error)
                }
            )

            return {

                "success": False,

                "error":
                    str(error)
            }


    # ==========================================
    # WAKE WORD DETECTION
    # ==========================================

    async def detect_wake_word(

        self

    ) -> Dict[str, Any]:

        result = await self.listen_once()

        if not result.get(
            "success"
        ):

            return result

        recognized_text = (

            result[
                "recognized_text"
            ].lower()
        )

        wake_detected = any(

            wake_word in recognized_text

            for wake_word in
            self.wake_words
        )

        return {

            "success": True,

            "wake_word_detected":
                wake_detected,

            "recognized_text":
                recognized_text
        }


    # ==========================================
    # CONTINUOUS LISTENING
    # ==========================================

    async def continuous_listen(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        cycles = payload.get(
            "cycles",
            3
        )

        transcripts = []

        await self.publish_event(

            execution_id,

            "continuous_listening_started",

            "running",

            "voice_runtime",

            "Continuous listening started",

            {

                "cycles":
                    cycles
            }
        )

        for _ in range(cycles):

            result = await self.listen_once()

            if result.get(
                "success"
            ):

                transcripts.append(

                    result[
                        "recognized_text"
                    ]
                )

        await self.publish_event(

            execution_id,

            "continuous_listening_completed",

            "completed",

            "voice_runtime",

            "Continuous listening completed",

            {

                "transcript_count":
                    len(transcripts)
            }
        )

        return {

            "success": True,

            "transcripts":
                transcripts
        }


# ==========================================
# SINGLETON
# ==========================================

speech_to_text_engine = (
    SpeechToTextEngine()
)


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="speech_listen_once",

    description=
        "Listen once from microphone",

    handler=
        speech_to_text_engine.listen_once,

    tool_type=
        "voice"
)

tool_registry.register_tool(

    name="speech_detect_wake_word",

    description=
        "Detect Cortex wake word",

    handler=
        speech_to_text_engine.detect_wake_word,

    tool_type=
        "voice"
)

tool_registry.register_tool(

    name="speech_continuous_listen",

    description=
        "Continuous speech listening",

    handler=
        speech_to_text_engine.continuous_listen,

    tool_type=
        "voice"
)