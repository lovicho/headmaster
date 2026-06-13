"""Environment Context schema.

Represents the capabilities, skills, and tools available in the CLI environment
(e.g., Claude Code, Codex, Antigravity) that Headmaster is currently running within.
"""

from pydantic import BaseModel, Field

class EnvironmentContext(BaseModel):
    """Context probed from the active model CLI or environment."""
    
    provider_name: str
    cli_version: str = "unknown"
    native_capabilities: list[str] = Field(default_factory=list)
    system_prompt_extension: str = ""
