"""Lets the web playground call the MCP tools over plain HTTP. It calls the same
functions the MCP servers register, so the results are identical."""

import inspect
from collections.abc import Callable

from fastapi import APIRouter, HTTPException

from backend.api.schemas import McpCallRequest, McpToolOut, McpToolParam
from backend.mcp_servers.finki_hub_mcp.server import (
    search_consultations,
    search_courses,
    search_exam_sessions,
    search_materials,
    search_staff,
    search_thesis_archive,
)
from backend.mcp_servers.official_live_mcp.server import search_official_site_live
from backend.mcp_servers.official_mcp.server import (
    get_course_info,
    get_exam_schedule,
    get_professor_info,
    search_announcements,
    search_faculty_info,
    search_official_documents,
)

router = APIRouter(prefix="/mcp", tags=["mcp"])

SERVERS: dict[str, dict[str, Callable]] = {
    "official": {
        "search_announcements": search_announcements,
        "get_exam_schedule": get_exam_schedule,
        "get_course_info": get_course_info,
        "get_professor_info": get_professor_info,
        "search_faculty_info": search_faculty_info,
        "search_official_documents": search_official_documents,
    },
    "finki_hub": {
        "search_courses": search_courses,
        "search_staff": search_staff,
        "search_consultations": search_consultations,
        "search_materials": search_materials,
        "search_thesis_archive": search_thesis_archive,
        "search_exam_sessions": search_exam_sessions,
    },
    "official_live": {
        "search_official_site_live": search_official_site_live,
    },
}


def _tool_params(fn: Callable) -> list[McpToolParam]:
    params = []
    for name, p in inspect.signature(fn).parameters.items():
        has_default = p.default is not inspect.Parameter.empty
        params.append(
            McpToolParam(
                name=name,
                type=p.annotation.__name__ if hasattr(p.annotation, "__name__") else str(p.annotation),
                required=not has_default,
                default=p.default if has_default else None,
            )
        )
    return params


@router.get("/tools", response_model=list[McpToolOut])
def list_tools() -> list[McpToolOut]:
    return [
        McpToolOut(
            server=server,
            name=name,
            description=inspect.getdoc(fn) or "",
            params=_tool_params(fn),
        )
        for server, tools in SERVERS.items()
        for name, fn in tools.items()
    ]


@router.post("/call")
def call_tool(payload: McpCallRequest) -> list[dict]:
    tools = SERVERS.get(payload.server)
    if tools is None:
        raise HTTPException(status_code=404, detail=f"Unknown MCP server: {payload.server}")
    fn = tools.get(payload.tool)
    if fn is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {payload.tool}")

    accepted = set(inspect.signature(fn).parameters)
    kwargs = {k: v for k, v in {"query": payload.query, "limit": payload.limit}.items() if k in accepted}
    return fn(**kwargs)
