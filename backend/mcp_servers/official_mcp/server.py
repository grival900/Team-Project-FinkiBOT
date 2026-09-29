"""MCP server exposing the official finki.ukim.mk data: announcements (exam schedules,
enrollment notices, etc.), official course syllabus pages, professor/staff profiles,
and static faculty info pages (About Us, Studies, Admissions, International Students,
Contact).

Run standalone: `python -m backend.mcp_servers.official_mcp.server`
"""

from mcp.server.fastmcp import FastMCP

from backend.mcp_servers.common import run_search

mcp = FastMCP("finki-official")


@mcp.tool()
def search_announcements(query: str, limit: int = 5) -> list[dict]:
    """Search the official student announcement board (огласна табла): enrollment
    notices, FSS elections, guest lectures, and exam-session schedule postings."""
    return run_search(query, k=limit, source="official", type="announcement")


@mcp.tool()
def get_exam_schedule(query: str = "испитна сесија распоред", limit: int = 5) -> list[dict]:
    """Find exam-session schedule references. Exact dates live in linked SharePoint
    spreadsheets, not in any page text — this returns the reference link (title + url)
    pointing to the right schedule file, not the dates themselves."""
    return run_search(query, k=limit, source="official", type="schedule")


@mcp.tool()
def get_course_info(query: str, limit: int = 5) -> list[dict]:
    """Search official course syllabus pages (finki.ukim.mk/mk/subject/<code>) by name
    or topic: full syllabus text — prerequisites, teacher, ECTS credits, learning
    objectives, content outline, and literature. For course metadata like accreditation
    years and Discord channel instead, prefer finki-hub's `search_courses` tool."""
    return run_search(query, k=limit, source="official", type="course")


@mcp.tool()
def get_professor_info(query: str, limit: int = 5) -> list[dict]:
    """Search professor/staff directory pages by name: bio/resume, publications, and
    contact email when filled in. Profiles with no bio entered are not indexed."""
    return run_search(query, k=limit, source="official", type="professor")


@mcp.tool()
def search_faculty_info(query: str, limit: int = 5) -> list[dict]:
    """Search static faculty info pages: organization/leadership/institutes/labs
    (About Us), study programs and student services (Studies), enrollment quotas/
    requirements/documents per study cycle (Admissions), international-student
    admissions, and Contact details (address, phone, email). Does not cover
    announcements, course syllabi, or professor bios — use the other tools for those."""
    return run_search(query, k=limit, source="official", type="page")


@mcp.tool()
def search_official_documents(query: str, limit: int = 5) -> list[dict]:
    """Search PDFs linked from finki.ukim.mk pages: rulebooks, statutes, study guides,
    forms and study program elaborates."""
    return run_search(query, k=limit, source="official", type="document")


if __name__ == "__main__":
    mcp.run()
