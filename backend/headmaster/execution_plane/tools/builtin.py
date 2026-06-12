"""Built-in tools — local capabilities exposed through the policed gateway."""

from headmaster.control_plane.policy_engine import PolicyEngine
from headmaster.execution_plane.memory.fabric import MemoryFabric
from headmaster.execution_plane.tools.tool_gateway import ToolGateway


def build_default_tool_gateway(fabric: MemoryFabric) -> ToolGateway:
    """Gateway with the rag_search tool backed by the memory fabric."""
    gateway = ToolGateway(PolicyEngine())

    def rag_search(args: dict[str, object]) -> object:
        query = str(args.get("query", "")).strip()
        records = fabric.search(keyword=query or None, limit=5)
        if not records:
            return "no matching internal assets"
        return "\n".join(f"{record.memory_id}: {record.summary}" for record in records)

    gateway.register(
        "rag_search",
        rag_search,
        description=(
            "Search the internal knowledge base (RAG) for reusable assets;"
            " returns asset ids usable in ibf_proof.imitated_assets."
        ),
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "search keyword"}},
            "required": ["query"],
        },
    )
    return gateway
