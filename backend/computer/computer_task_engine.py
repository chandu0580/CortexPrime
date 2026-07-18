import asyncio
import subprocess
import webbrowser
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from backend.computer.desktop_controller import desktop_controller
from backend.computer.screen_intelligence import screen_intelligence
from backend.events.event_bus import event_bus, publish_event
from backend.events.event_models import CognitionEvent
from backend.tools.tool_registry import tool_registry

# ==========================================
# COMPUTER TASK ENGINE
# ==========================================

class ComputerTaskEngine:

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

        await publish_event("computer_task_engine", execution_id, event_type, status, phase, message, payload)


    # ==========================================
    # OPEN WEBSITE
    # ==========================================

    async def open_website(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        url = payload.get(
            "url"
        )

        if not url:

            return {

                "success": False,

                "error":
                    "Missing URL"
            }

        await self.publish_event(

            execution_id,

            "website_open_started",

            "running",

            "computer_task",

            f"Opening website: {url}"
        )

        webbrowser.open(url)

        await asyncio.sleep(3)

        await self.publish_event(

            execution_id,

            "website_open_completed",

            "completed",

            "computer_task",

            f"Website opened: {url}"
        )

        return {

            "success": True,

            "url": url
        }


    # ==========================================
    # OPEN APPLICATION
    # ==========================================

    async def open_application(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        app = payload.get(
            "application"
        )

        if not app:

            return {

                "success": False,

                "error":
                    "Missing application"
            }

        await self.publish_event(

            execution_id,

            "application_launch_started",

            "running",

            "computer_task",

            f"Launching application: {app}"
        )

        try:

            subprocess.Popen(app)

            await asyncio.sleep(3)

            await self.publish_event(

                execution_id,

                "application_launch_completed",

                "completed",

                "computer_task",

                f"Application launched: {app}"
            )

            return {

                "success": True,

                "application":
                    app
            }

        except Exception as error:

            return {

                "success": False,

                "error":
                    str(error)
            }


    # ==========================================
    # GOOGLE SEARCH
    # ==========================================

    async def google_search(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        query = payload.get(
            "query"
        )

        if not query:

            return {

                "success": False,

                "error":
                    "Missing query"
            }

        search_url = (

            "https://www.google.com/search?q="

            +

            query.replace(
                " ",
                "+"
            )
        )

        await self.publish_event(

            execution_id,

            "google_search_started",

            "running",

            "computer_task",

            f"Searching Google: {query}"
        )

        webbrowser.open(
            search_url
        )

        await asyncio.sleep(4)

        await self.publish_event(

            execution_id,

            "google_search_completed",

            "completed",

            "computer_task",

            f"Google search completed: {query}"
        )

        return {

            "success": True,

            "query": query
        }


    # ==========================================
    # TYPE INTO ACTIVE WINDOW
    # ==========================================

    async def type_into_window(

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

        await self.publish_event(

            execution_id,

            "window_typing_started",

            "running",

            "computer_task",

            "Typing into active window"
        )

        await desktop_controller.type_text({

            "text": text
        })

        await self.publish_event(

            execution_id,

            "window_typing_completed",

            "completed",

            "computer_task",

            "Typing completed"
        )

        return {

            "success": True
        }


    # ==========================================
    # TAKE SCREENSHOT
    # ==========================================

    async def capture_desktop(

        self

    ) -> Dict[str, Any]:

        return await (

            screen_intelligence
            .capture_screen({})
        )


    # ==========================================
    # AUTOMATED WORKFLOW
    # ==========================================

    async def execute_workflow(

        self,

        payload: Dict[str, Any]

    ) -> Dict[str, Any]:

        execution_id = str(
            uuid4()
        )

        workflow_name = payload.get(

            "workflow_name",

            "Unnamed Workflow"
        )

        actions = payload.get(
            "actions",
            []
        )

        completed_actions = []

        await self.publish_event(

            execution_id,

            "workflow_started",

            "running",

            "workflow_execution",

            f"Executing workflow: {workflow_name}"
        )

        # ==========================================
        # EXECUTE ACTIONS
        # ==========================================

        for action in actions:

            action_type = action.get(
                "type"
            )

            try:

                # ==============================
                # OPEN WEBSITE
                # ==============================

                if action_type == "website":

                    result = await (

                        self.open_website(
                            action
                        )
                    )

                # ==============================
                # GOOGLE SEARCH
                # ==============================

                elif action_type == "search":

                    result = await (

                        self.google_search(
                            action
                        )
                    )

                # ==============================
                # TYPE TEXT
                # ==============================

                elif action_type == "type":

                    result = await (

                        self.type_into_window(
                            action
                        )
                    )

                # ==============================
                # HOTKEY
                # ==============================

                elif action_type == "hotkey":

                    result = await (

                        desktop_controller
                        .hotkey(action)
                    )

                # ==============================
                # SCREENSHOT
                # ==============================

                elif action_type == "screenshot":

                    result = await (

                        self.capture_desktop()
                    )

                else:

                    result = {

                        "success": False,

                        "error":
                            f"Unknown action: {action_type}"
                    }

                completed_actions.append({

                    "action":
                        action_type,

                    "result":
                        result
                })

                await asyncio.sleep(1)

            except Exception as error:

                completed_actions.append({

                    "action":
                        action_type,

                    "error":
                        str(error)
                })

        await self.publish_event(

            execution_id,

            "workflow_completed",

            "completed",

            "workflow_execution",

            f"Workflow completed: {workflow_name}",

            {

                "completed_actions":
                    len(completed_actions)
            }
        )

        return {

            "success": True,

            "workflow_name":
                workflow_name,

            "completed_actions":
                completed_actions,

            "timestamp":
                datetime.utcnow()
                .isoformat()
        }


# ==========================================
# SINGLETON
# ==========================================

computer_task_engine = (
    ComputerTaskEngine()
)


# ==========================================
# REGISTER TOOLS
# ==========================================

tool_registry.register_tool(

    name="computer_open_website",

    description=
        "Open website in browser",

    handler=
        computer_task_engine.open_website,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="computer_open_application",

    description=
        "Launch desktop application",

    handler=
        computer_task_engine.open_application,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="computer_google_search",

    description=
        "Perform Google search",

    handler=
        computer_task_engine.google_search,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="computer_type_text",

    description=
        "Type text into active window",

    handler=
        computer_task_engine.type_into_window,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="computer_capture_screen",

    description=
        "Capture desktop screenshot",

    handler=
        computer_task_engine.capture_desktop,

    tool_type=
        "computer"
)

tool_registry.register_tool(

    name="computer_execute_workflow",

    description=
        "Execute autonomous desktop workflow",

    handler=
        computer_task_engine.execute_workflow,

    tool_type=
        "computer"
)
