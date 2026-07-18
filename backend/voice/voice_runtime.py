from datetime import datetime
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

import edge_tts

from backend.events.event_bus import publish_event
from backend.tools.tool_registry import tool_registry

# ==========================================
# VOICE RUNTIME
# ==========================================

class VoiceRuntime:

    def __init__(self):

        # ==========================================
        # VOICE PROFILES
        # ==========================================

        self.voice_profiles = {

            # ======================================
            # MALE VOICES
            # ======================================

            "jarvis_male":

                "en-US-GuyNeural",

            "eric_male":

                "en-US-EricNeural",

            "roger_male":

                "en-US-RogerNeural",

            # ======================================
            # FEMALE VOICES
            # ======================================

            "nova_female":

                "en-US-AriaNeural",

            "jenny_female":

                "en-US-JennyNeural",

            "natasha_female":

                "en-AU-NatashaNeural"
        }

        # ==========================================
        # DEFAULT PROFILE
        # ==========================================

        self.current_profile = (
            "jarvis_male"
        )

        # ==========================================
        # OUTPUT DIRECTORY
        # ==========================================

        self.output_dir = Path(
            "generated_voice"
        )

        self.output_dir.mkdir(
            exist_ok=True
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

        payload: Dict[str, Any] = None
    ):

        await publish_event("voice_runtime", execution_id, event_type, status, phase, message, payload)


    # ==========================================
    # SET VOICE PROFILE
    # ==========================================

    async def set_voice_profile(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        profile = payload.get(
            "profile"
        )

        if profile not in (

            self.voice_profiles
        ):

            return {

                "success": False,

                "error":
                    "Invalid voice profile"
            }

        self.current_profile = (
            profile
        )

        return {

            "success": True,

            "current_profile":
                self.current_profile,

            "voice":
                self.voice_profiles[
                    profile
                ]
        }


    # ==========================================
    # TEXT TO SPEECH
    # ==========================================

    async def synthesize_speech(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        text = payload.get(
            "text"
        )

        if not text:

            return {

                "success": False,

                "error":
                    "Missing text"
            }

        voice_profile = payload.get(

            "voice_profile",

            self.current_profile
        )

        voice_name = (

            self.voice_profiles.get(

                voice_profile,

                "en-US-GuyNeural"
            )
        )

        await self.publish_event(

            execution_id,

            "voice_synthesis_started",

            "running",

            "voice_generation",

            "Generating speech audio",

            {

                "voice_profile":
                    voice_profile
            }
        )

        try:

            # ======================================
            # OUTPUT FILE
            # ======================================

            output_file = (

                self.output_dir /

                f"{execution_id}.mp3"
            )

            # ======================================
            # EDGE TTS
            # ======================================

            communicator = (

                edge_tts.Communicate(

                    text=text,

                    voice=voice_name
                )
            )

            await communicator.save(

                str(output_file)
            )

            await self.publish_event(

                execution_id,

                "voice_synthesis_completed",

                "completed",

                "voice_generation",

                "Speech synthesis completed",

                {

                    "voice_profile":
                        voice_profile,

                    "output_file":
                        str(output_file)
                }
            )

            return {

                "success": True,

                "voice_profile":
                    voice_profile,

                "voice_name":
                    voice_name,

                "audio_file":
                    str(output_file),

                "timestamp":
                    datetime.utcnow()
                    .isoformat()
            }

        except Exception as error:

            await self.publish_event(

                execution_id,

                "voice_synthesis_failed",

                "failed",

                "voice_generation",

                "Voice synthesis failed",

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
    # LIST VOICES
    # ==========================================

    async def list_voice_profiles(

        self

    ) -> Dict[str, Any]:

        return {

            "success": True,

            "current_profile":
                self.current_profile,

            "profiles":
                self.voice_profiles
        }


    # ==========================================
    # SIMPLE TEST SPEECH
    # ==========================================

    async def test_voice(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        profile = payload.get(

            "voice_profile",

            self.current_profile
        )

        return await self.synthesize_speech({

            "text":
                (
                    "Hello. "
                    "I am CortexPrime. "
                    "Voice runtime is now active."
                ),

            "voice_profile":
                profile
        })


# ==========================================
# SINGLETON
# ==========================================

voice_runtime = VoiceRuntime()


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="voice_set_profile",

    description=
        "Switch voice profiles",

    handler=
        voice_runtime.set_voice_profile,

    tool_type=
        "voice"
)

tool_registry.register_tool(

    name="voice_synthesize",

    description=
        "Generate speech audio",

    handler=
        voice_runtime.synthesize_speech,

    tool_type=
        "voice"
)

tool_registry.register_tool(

    name="voice_test",

    description=
        "Generate test speech",

    handler=
        voice_runtime.test_voice,

    tool_type=
        "voice"
)

tool_registry.register_tool(

    name="voice_list_profiles",

    description=
        "List available voices",

    handler=
        voice_runtime.list_voice_profiles,

    tool_type=
        "voice"
)
