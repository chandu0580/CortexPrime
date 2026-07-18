import asyncio
from typing import Any, Dict
from uuid import uuid4

import pygetwindow as gw

from backend.events.event_bus import event_bus, publish_event
from backend.events.event_models import CognitionEvent
from backend.tools.tool_registry import tool_registry

# ==========================================
# WINDOW MANAGER
# ==========================================

class WindowManager:

    def __init__(self):

        pass


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

        await publish_event("window_manager", execution_id, event_type, status, phase, message, payload)


    # ==========================================
    # GET ALL WINDOWS
    # ==========================================

    async def get_all_windows(

        self

    ) -> Dict[str, Any]:

        windows = []

        for window in gw.getAllWindows():

            try:

                if window.title.strip():

                    windows.append({

                        "title":
                            window.title,

                        "left":
                            window.left,

                        "top":
                            window.top,

                        "width":
                            window.width,

                        "height":
                            window.height,

                        "is_active":
                            window.isActive
                    })

            except Exception:

                continue

        return {

            "success": True,

            "count":
                len(windows),

            "windows":
                windows
        }


    # ==========================================
    # GET ACTIVE WINDOW
    # ==========================================

    async def get_active_window(

        self

    ) -> Dict[str, Any]:

        active = (
            gw.getActiveWindow()
        )

        if not active:

            return {

                "success": False,

                "error":
                    "No active window found"
            }

        return {

            "success": True,

            "window": {

                "title":
                    active.title,

                "left":
                    active.left,

                "top":
                    active.top,

                "width":
                    active.width,

                "height":
                    active.height
            }
        }


    # ==========================================
    # FIND WINDOW
    # ==========================================

    def find_window(

        self,

        title_keyword: str
    ):

        windows = gw.getAllWindows()

        for window in windows:

            try:

                if (

                    title_keyword.lower()

                    in

                    window.title.lower()
                ):

                    return window

            except Exception:

                continue

        return None


    # ==========================================
    # FOCUS WINDOW
    # ==========================================

    async def focus_window(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        title = payload.get(
            "title"
        )

        if not title:

            return {

                "success": False,

                "error":
                    "Missing window title"
            }

        window = self.find_window(
            title
        )

        if not window:

            return {

                "success": False,

                "error":
                    f"Window not found: {title}"
            }

        await self.publish_event(

            execution_id,

            "window_focus_started",

            "running",

            "window_control",

            f"Focusing window: {window.title}"
        )

        window.activate()

        await asyncio.sleep(1)

        await self.publish_event(

            execution_id,

            "window_focus_completed",

            "completed",

            "window_control",

            f"Focused window: {window.title}"
        )

        return {

            "success": True,

            "window":
                window.title
        }


    # ==========================================
    # MAXIMIZE WINDOW
    # ==========================================

    async def maximize_window(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        title = payload.get(
            "title"
        )

        window = self.find_window(
            title
        )

        if not window:

            return {

                "success": False,

                "error":
                    "Window not found"
            }

        await self.publish_event(

            execution_id,

            "window_maximize_started",

            "running",

            "window_control",

            f"Maximizing window: {window.title}"
        )

        window.maximize()

        await asyncio.sleep(1)

        await self.publish_event(

            execution_id,

            "window_maximize_completed",

            "completed",

            "window_control",

            f"Maximized window: {window.title}"
        )

        return {

            "success": True
        }


    # ==========================================
    # MINIMIZE WINDOW
    # ==========================================

    async def minimize_window(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        title = payload.get(
            "title"
        )

        window = self.find_window(
            title
        )

        if not window:

            return {

                "success": False,

                "error":
                    "Window not found"
            }

        await self.publish_event(

            execution_id,

            "window_minimize_started",

            "running",

            "window_control",

            f"Minimizing window: {window.title}"
        )

        window.minimize()

        await asyncio.sleep(1)

        await self.publish_event(

            execution_id,

            "window_minimize_completed",

            "completed",

            "window_control",

            f"Minimized window: {window.title}"
        )

        return {

            "success": True
        }


    # ==========================================
    # MOVE WINDOW
    # ==========================================

    async def move_window(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        title = payload.get(
            "title"
        )

        x = payload.get("x")
        y = payload.get("y")

        window = self.find_window(
            title
        )

        if not window:

            return {

                "success": False,

                "error":
                    "Window not found"
            }

        await self.publish_event(

            execution_id,

            "window_move_started",

            "running",

            "window_control",

            f"Moving window: {window.title}"
        )

        window.moveTo(
            x,
            y
        )

        await asyncio.sleep(1)

        await self.publish_event(

            execution_id,

            "window_move_completed",

            "completed",

            "window_control",

            f"Moved window: {window.title}"
        )

        return {

            "success": True,

            "x": x,

            "y": y
        }


    # ==========================================
    # RESIZE WINDOW
    # ==========================================

    async def resize_window(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        title = payload.get(
            "title"
        )

        width = payload.get(
            "width"
        )

        height = payload.get(
            "height"
        )

        window = self.find_window(
            title
        )

        if not window:

            return {

                "success": False,

                "error":
                    "Window not found"
            }

        await self.publish_event(

            execution_id,

            "window_resize_started",

            "running",

            "window_control",

            f"Resizing window: {window.title}"
        )

        window.resizeTo(
            width,
            height
        )

        await asyncio.sleep(1)

        await self.publish_event(

            execution_id,

            "window_resize_completed",

            "completed",

            "window_control",

            f"Resized window: {window.title}"
        )

        return {

            "success": True,

            "width": width,

            "height": height
        }


# ==========================================
# SINGLETON
# ==========================================

window_manager = (
    WindowManager()
)


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="window_get_all",

    description=
        "Get all desktop windows",

    handler=
        window_manager.get_all_windows,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="window_get_active",

    description=
        "Get active desktop window",

    handler=
        window_manager.get_active_window,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="window_focus",

    description=
        "Focus desktop window",

    handler=
        window_manager.focus_window,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="window_maximize",

    description=
        "Maximize desktop window",

    handler=
        window_manager.maximize_window,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="window_minimize",

    description=
        "Minimize desktop window",

    handler=
        window_manager.minimize_window,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="window_move",

    description=
        "Move desktop window",

    handler=
        window_manager.move_window,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="window_resize",

    description=
        "Resize desktop window",

    handler=
        window_manager.resize_window,

    tool_type=
        "computer"
)
