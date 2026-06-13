### Google (AGY/Gemini) Official Guidelines & Best Practices
1. **Massive Context & Caching**:
   - Gemini models (like 1.5 Pro) support up to 1M-2M tokens. Leverage this by feeding entire repositories, large codebases, or extensive documentation.
   - Context caching is highly effective; ensure repetitive background knowledge is batched correctly.
2. **Multi-Agent Orchestration (Antigravity SDK)**:
   - When running via AGY, agents can spawn sub-agents or coordinate tasks in parallel. 
   - Think of tasks as a graph of responsibilities. Use MCP (Model Context Protocol) to seamlessly connect diverse tools and APIs.
3. **Search Grounding & Factuality**:
   - Gemini can ground its answers using Google Search. When verifiable facts or up-to-date documentation are needed, formulate explicit queries.
4. **Multimodal Capabilities**:
   - Gemini naturally understands interwoven text, images, and video. If visual context is provided, treat it as a primary source of truth for UI/UX tasks.
