"""Harness compiler — turns an AgentHarness manifest into a model-agnostic
system prompt with a strict JSON output contract (3rd report skeleton)."""

from headmaster.schemas.harness_manifest import AgentHarness, IBFRequirements

_OUTPUT_CONTRACT = """\
## Output Contract (STRICT)
Respond with a SINGLE JSON object and nothing else:
{{
  "ibf_proof": {{
    "imitated_assets": ["<internal asset id>", ...],
    "benchmarked_references": ["<external reference uri>", ...],
    "fusion_method": "<how client-specific facts were fused into the skeleton>"
  }},
  "content": "<the deliverable, format: {format}, written in {external_lang}>"
}}
- {imitation_rule}
- {benchmark_rule}
- Never invent sources. If you cannot cite a source, leave the list empty
  and state the gap inside fusion_method."""


def compile_system_prompt(harness: AgentHarness, requirements: IBFRequirements) -> str:
    sections = [
        f"You are {harness.persona.role}.",
        f"Objective: {harness.persona.objective}",
        "## Inherited Master Directives",
        *[f"- {directive}" for directive in harness.inherited_directives],
        "## I-B-F Protocol",
    ]
    protocol = harness.ibf_protocol
    for step, description in (
        ("Imitate", protocol.imitate),
        ("Benchmark", protocol.benchmark),
        ("Fusion", protocol.fusion),
        ("Maintain", protocol.maintain),
    ):
        if description:
            sections.append(f"- [{step}] {description}")
    sections.append(
        _OUTPUT_CONTRACT.format(
            format=harness.output_contract.format,
            external_lang=harness.language_policy.external.value.upper(),
            imitation_rule=(
                "imitated_assets MUST be non-empty (declare your imitation base)."
                if requirements.must_reference_internal_assets
                else "imitated_assets may be empty for this role."
            ),
            benchmark_rule=(
                "benchmarked_references MUST be non-empty (declare your benchmark targets)."
                if requirements.must_reference_external_benchmarks
                else "benchmarked_references may be empty for this role."
            ),
        )
    )
    return "\n".join(sections)
