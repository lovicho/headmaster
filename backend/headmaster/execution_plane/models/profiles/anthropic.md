### Anthropic (Claude) Official Guidelines & Best Practices
1. **XML Tagging for Structure & Reasoning**:
   - Claude highly prefers thinking within `<thinking>` or `<scratchpad>` tags before answering. This prevents premature commitment to an incorrect path.
   - Use XML tags to structure output (e.g., `<output>`, `<explanation>`).
2. **Context Window Strategy**:
   - Claude supports a massive context window (up to 200K tokens). However, place the most critical instructions at the very beginning or the very end of the prompt.
   - When extracting data from large documents, specify exactly what fields to extract and provide clear examples.
3. **Computer Use & Tool Capabilities**:
   - Claude Code / Computer Use requires explicit confirmation before destructive actions.
   - For file editing, prefer rewriting only necessary chunks. If using `bash`, handle errors gracefully and read outputs sequentially.
4. **Tone & Alignment**:
   - Maintain a neutral, helpful, and direct tone. Avoid "as an AI" filler text.
   - Do not apologize unnecessarily; simply state the correction and move on.
