from typing import Dict, Any
from uuid import uuid4
from datetime import datetime
import asyncio

import pyautogui

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
# SAFETY CONFIG
# ==========================================

pyautogui.FAILSAFE = True


# ==========================================
# DESKTOP CONTROLLER
# ==========================================

class DesktopController:

    def __init__(self):

        # ==========================================
        # DEFAULT ACTION DELAY
        # ==========================================

        self.default_delay = 0.5


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
                    "desktop_controller",

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
    # GET SCREEN SIZE
    # ==========================================

    async def get_screen_size(

        self

    ) -> Dict[str, Any]:

        width, height = (
            pyautogui.size()
        )

        return {

            "success": True,

            "width": width,

            "height": height
        }


    # ==========================================
    # GET MOUSE POSITION
    # ==========================================

    async def get_mouse_position(

        self

    ) -> Dict[str, Any]:

        x, y = (
            pyautogui.position()
        )

        return {

            "success": True,

            "x": x,

            "y": y
        }


    # ==========================================
    # MOVE MOUSE
    # ==========================================

    async def move_mouse(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        x = payload.get("x")
        y = payload.get("y")

        duration = payload.get(
            "duration",
            0.5
        )

        if x is None or y is None:

            return {

                "success": False,

                "error":
                    "Missing x or y coordinates"
            }

        await self.publish_event(

            execution_id,

            "mouse_move_started",

            "running",

            "desktop_control",

            f"Moving mouse to ({x}, {y})"
        )

        pyautogui.moveTo(

            x,
            y,

            duration=duration
        )

        await asyncio.sleep(
            self.default_delay
        )

        await self.publish_event(

            execution_id,

            "mouse_move_completed",

            "completed",

            "desktop_control",

            "Mouse movement completed",

            {

                "x": x,

                "y": y
            }
        )

        return {

            "success": True,

            "x": x,

            "y": y
        }


    # ==========================================
    # CLICK
    # ==========================================

    async def click(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        button = payload.get(
            "button",
            "left"
        )

        clicks = payload.get(
            "clicks",
            1
        )

        interval = payload.get(
            "interval",
            0.25
        )

        await self.publish_event(

            execution_id,

            "mouse_click_started",

            "running",

            "desktop_control",

            f"Performing {button} click"
        )

        pyautogui.click(

            button=button,

            clicks=clicks,

            interval=interval
        )

        await asyncio.sleep(
            self.default_delay
        )

        await self.publish_event(

            execution_id,

            "mouse_click_completed",

            "completed",

            "desktop_control",

            "Mouse click completed"
        )

        return {

            "success": True,

            "button": button,

            "clicks": clicks
        }


    # ==========================================
    # DOUBLE CLICK
    # ==========================================

    async def double_click(

        self

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        await self.publish_event(

            execution_id,

            "double_click_started",

            "running",

            "desktop_control",

            "Performing double click"
        )

        pyautogui.doubleClick()

        await asyncio.sleep(
            self.default_delay
        )

        await self.publish_event(

            execution_id,

            "double_click_completed",

            "completed",

            "desktop_control",

            "Double click completed"
        )

        return {

            "success": True
        }


    # ==========================================
    # TYPE TEXT
    # ==========================================

    async def type_text(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        text = payload.get(
            "text"
        )

        interval = payload.get(
            "interval",
            0.03
        )

        if not text:

            return {

                "success": False,

                "error":
                    "Missing text"
            }

        await self.publish_event(

            execution_id,

            "keyboard_typing_started",

            "running",

            "desktop_control",

            "Typing text input"
        )

        pyautogui.write(

            text,

            interval=interval
        )

        await asyncio.sleep(
            self.default_delay
        )

        await self.publish_event(

            execution_id,

            "keyboard_typing_completed",

            "completed",

            "desktop_control",

            "Typing completed",

            {

                "characters":
                    len(text)
            }
        )

        return {

            "success": True,

            "characters":
                len(text)
        }


    # ==========================================
    # PRESS KEY
    # ==========================================

    async def press_key(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        key = payload.get(
            "key"
        )

        if not key:

            return {

                "success": False,

                "error":
                    "Missing key"
            }

        await self.publish_event(

            execution_id,

            "key_press_started",

            "running",

            "desktop_control",

            f"Pressing key: {key}"
        )

        pyautogui.press(key)

        await asyncio.sleep(
            self.default_delay
        )

        await self.publish_event(

            execution_id,

            "key_press_completed",

            "completed",

            "desktop_control",

            f"Key press completed: {key}"
        )

        return {

            "success": True,

            "key": key
        }


    # ==========================================
    # HOTKEY
    # ==========================================

    async def hotkey(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        keys = payload.get(
            "keys",
            []
        )

        if not keys:

            return {

                "success": False,

                "error":
                    "Missing hotkey keys"
            }

        await self.publish_event(

            execution_id,

            "hotkey_started",

            "running",

            "desktop_control",

            f"Executing hotkey: {' + '.join(keys)}"
        )

        pyautogui.hotkey(*keys)

        await asyncio.sleep(
            self.default_delay
        )

        await self.publish_event(

            execution_id,

            "hotkey_completed",

            "completed",

            "desktop_control",

            "Hotkey execution completed"
        )

        return {

            "success": True,

            "keys": keys
        }


    # ==========================================
    # SCROLL
    # ==========================================

    async def scroll(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        clicks = payload.get(
            "clicks",
            -500
        )

        await self.publish_event(

            execution_id,

            "scroll_started",

            "running",

            "desktop_control",

            "Scrolling screen"
        )

        pyautogui.scroll(
            clicks
        )

        await asyncio.sleep(
            self.default_delay
        )

        await self.publish_event(

            execution_id,

            "scroll_completed",

            "completed",

            "desktop_control",

            "Scroll completed"
        )

        return {

            "success": True,

            "clicks": clicks
        }


# ==========================================
# SINGLETON
# ==========================================

desktop_controller = (
    DesktopController()
)


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="desktop_get_screen_size",

    description=
        "Get desktop screen size",

    handler=
        desktop_controller.get_screen_size,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="desktop_get_mouse_position",

    description=
        "Get mouse coordinates",

    handler=
        desktop_controller.get_mouse_position,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="desktop_move_mouse",

    description=
        "Move mouse on screen",

    handler=
        desktop_controller.move_mouse,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="desktop_click",

    description=
        "Mouse click actions",

    handler=
        desktop_controller.click,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="desktop_double_click",

    description=
        "Double click action",

    handler=
        desktop_controller.double_click,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="desktop_type_text",

    description=
        "Keyboard typing",

    handler=
        desktop_controller.type_text,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="desktop_press_key",

    description=
        "Press keyboard key",

    handler=
        desktop_controller.press_key,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="desktop_hotkey",

    description=
        "Execute hotkeys",

    handler=
        desktop_controller.hotkey,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="desktop_scroll",

    description=
        "Scroll screen",

    handler=
        desktop_controller.scroll,

    tool_type=
        "computer"
)