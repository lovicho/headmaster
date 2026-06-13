### OpenAI (Codex/GPT) Official Guidelines & Best Practices
1. **Parallel Tool Calling**:
   - OpenAI models are highly optimized for executing multiple independent tool calls in parallel. Use this to speed up data retrieval.
2. **JSON Mode & Structured Data**:
   - The models strictly adhere to JSON schemas when required. Always specify the schema clearly in the prompt.
   - Avoid trailing commas and ensure output is parseable JSON when instructed.
3. **Step-by-Step Thinking**:
   - Adding "Let's think step by step" or asking the model to explicitly list assumptions drastically reduces logic errors, especially in math and coding tasks.
4. **Code Generation Patterns**:
   - The model excels at standard design patterns (e.g., Factory, Observer). Mention the pattern by name.
   - Use clear, typed function signatures in prompts to guide code structure.
5. **Instruction Placement**:
   - OpenAI models pay close attention to the `system` message. Place overarching behavioral rules there, and specific task details in the `user` message.
