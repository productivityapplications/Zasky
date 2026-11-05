# Zasky — External Technical References

The handoff documents are the project source of truth. These external references are for protocol and API behavior that can evolve; the coding agent must re-check the documentation against the deployed service versions during Phase 0 intake.

## Switch

1. **The agent protocol**  
   https://docs.switchagents.ai/switch-rooms/internals/agent-protocol  
   Relevant: registration is one-time; registration key and agent runtime API key are different; current custom agent transport is WebSocket; SSE is deprecated; owner-only addressing; messages should be processed only when `payload.addressed` is true; HTTP operations are called with the current connection ID as required.

2. **Agent connection**  
   https://docs.switchagents.ai/switch-rooms/internals/agent-connection  
   Relevant: WebSocket connection path; stable connection ID; `connection_state` first frame; cursor and generation; ping/pong heartbeat; resume using cursor/expected generation; `gap` recovery; `evicted` handling; `taken_over` is terminal; one connection per agent may act in a given room.

3. **Agent events**  
   https://docs.switchagents.ai/switch-rooms/internals/agent-events  
   Confirm exact current event payload and addressed message semantics against the deployed server's protocol version before coding.

4. **Identity and access**  
   https://docs.switchagents.ai/switch-rooms/internals/identity-and-access  
   Review resource permissions separately from addressing rules; do not infer authorization from room visibility alone.

5. **Working safely with agents**  
   https://docs.switchagents.ai/switch-rooms/resources/working-safely-with-agents  
   Apply least privilege and controls around untrusted room content and tool access.

## OpenAI

1. **Assistants migration / sunset notice**  
   https://developers.openai.com/api/docs/assistants/migration  
   The Assistants API was sunset on 2026-08-26. New implementation uses the Responses API, not Assistants API.

2. **Responses API migration guide**  
   https://developers.openai.com/api/docs/guides/migrate-to-responses  
   Re-check current input/output shape, function call IDs, structured output options, storage semantics and streaming behavior.

3. **Tool/function calling guide**  
   https://developers.openai.com/api/docs/guides/tools  
   Use only the seven approved Zasky domain functions; do not grant unrelated built-in tools.

## Reference handling

- Current API/model availability, quotas, billing and data retention must be confirmed at implementation time.
- URLs and protocol assumptions in these documents are not a substitute for version checks.
- Do not include secrets or private deployment URLs in this document.
