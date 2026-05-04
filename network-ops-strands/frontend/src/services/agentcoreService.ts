/**
 * AgentCore direct invocation service with SSE streaming support.
 *
 * The AgentCore entrypoint is an async generator that yields SSE events.
 * The runtime wraps them in text/event-stream format.
 */

import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from '@aws-sdk/client-bedrock-agentcore';
import { fromCognitoIdentityPool } from '@aws-sdk/credential-providers';

const AGENTCORE_ARN = import.meta.env.VITE_AGENTCORE_ARN || '';
const REGION = import.meta.env.VITE_REGION || 'us-east-1';
const IDENTITY_POOL_ID = import.meta.env.VITE_IDENTITY_POOL_ID || '';
const USER_POOL_ID = import.meta.env.VITE_USER_POOL_ID || '';

export const isAgentCoreMode = (): boolean => !!AGENTCORE_ARN;

const cognitoLoginKey = `cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}`;

function createClient(idToken?: string): BedrockAgentCoreClient {
  if (IDENTITY_POOL_ID && idToken) {
    return new BedrockAgentCoreClient({
      region: REGION,
      credentials: fromCognitoIdentityPool({
        identityPoolId: IDENTITY_POOL_ID,
        clientConfig: { region: REGION },
        logins: { [cognitoLoginKey]: idToken },
      }),
    });
  }
  return new BedrockAgentCoreClient({ region: REGION });
}

async function getIdToken(): Promise<string | undefined> {
  try {
    const { fetchAuthSession } = await import('aws-amplify/auth');
    const session = await fetchAuthSession();
    return session.tokens?.idToken?.toString();
  } catch {
    return undefined;
  }
}

/**
 * Parse SSE text into individual events.
 * AgentCore streams: "data: {json}\n\ndata: {json}\n\n..."
 */
function parseSSEEvents(text: string): Array<Record<string, unknown>> {
  const events: Array<Record<string, unknown>> = [];
  const lines = text.split('\n');

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('data: ')) {
      try {
        events.push(JSON.parse(trimmed.slice(6)));
      } catch {
        // Not valid JSON — might be partial
      }
    } else if (trimmed.startsWith('{')) {
      // Direct JSON (non-SSE format, e.g., metrics response)
      try {
        events.push(JSON.parse(trimmed));
      } catch {
        // Ignore
      }
    }
  }
  return events;
}

/**
 * Invoke the supervisor agent on AgentCore with SSE streaming.
 * Yields events compatible with the ChatInterface consumer.
 */
export async function* invokeAgentCore(
  message: string,
  sessionId: string,
  _userId: string,
) {
  const idToken = await getIdToken();
  const client = createClient(idToken);

  const payload = JSON.stringify({ prompt: message, actor_id: _userId });
  const paddedSessionId = sessionId.padEnd(33, '0');

  const command = new InvokeAgentRuntimeCommand({
    agentRuntimeArn: AGENTCORE_ARN,
    runtimeSessionId: paddedSessionId,
    payload: new TextEncoder().encode(payload),
  });

  try {
    const response = await client.send(command);
    const body = response.response;
    if (!body) {
      yield { type: 'token' as const, content: 'No response from agent.' };
      yield { type: 'done' as const };
      return;
    }

    // Try to get the underlying web ReadableStream for true streaming
    const webStream = (body as unknown as { transformToWebStream?: () => ReadableStream })
      .transformToWebStream?.();

    if (webStream) {
      // True streaming: read chunks as they arrive
      const reader = webStream.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value as Uint8Array, { stream: true });

        // Process complete SSE lines from the buffer
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          let jsonStr = trimmed;
          if (trimmed.startsWith('data: ')) {
            jsonStr = trimmed.slice(6);
          }

          try {
            const evt = JSON.parse(jsonStr) as Record<string, unknown>;
            const evtType = evt.type as string;

            if (evtType === 'token' && evt.content) {
              yield { type: 'token' as const, content: evt.content as string };
            } else if (evtType === 'thinking' && evt.content) {
              yield { type: 'thinking' as const, content: evt.content as string };
            } else if (evtType === 'mcp_tool' && evt.tool) {
              yield {
                type: 'mcp_tool' as const,
                tool: evt.tool as string,
                params: (evt.params || {}) as Record<string, unknown>,
              };
            } else if (evtType === 'done') {
              yield { type: 'done' as const };
              reader.cancel();
              return;
            }
          } catch {
            // Not valid JSON yet
          }
        }
      }
    } else {
      // Fallback: transformToString (buffers entire response)
      const text = await body.transformToString();
      const events = parseSSEEvents(text);
      for (const evt of events) {
        const evtType = evt.type as string;
        if (evtType === 'token' && evt.content) {
          yield { type: 'token' as const, content: evt.content as string };
        } else if (evtType === 'thinking' && evt.content) {
          yield { type: 'thinking' as const, content: evt.content as string };
        } else if (evtType === 'mcp_tool' && evt.tool) {
          yield {
            type: 'mcp_tool' as const,
            tool: evt.tool as string,
            params: (evt.params || {}) as Record<string, unknown>,
          };
        } else if (evtType === 'done') {
          yield { type: 'done' as const };
          return;
        } else if (evt.result) {
          const result = evt.result as Record<string, unknown>;
          if (result.content && Array.isArray(result.content)) {
            const textContent = (result.content as Array<Record<string, string>>)
              .filter((b) => b.text)
              .map((b) => b.text)
              .join('\n');
            yield { type: 'token' as const, content: textContent };
          } else if (typeof evt.result === 'string') {
            yield { type: 'token' as const, content: evt.result as string };
          }
        }
      }
    }

    yield { type: 'done' as const };
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Unknown error';
    console.error('AgentCore invocation failed:', msg);
    yield { type: 'token' as const, content: `Error: ${msg}` };
    yield { type: 'done' as const };
  }
}

/**
 * Invoke AgentCore directly with a structured payload (non-streaming).
 * Used for actions like "metrics" that bypass the LLM.
 */
export async function invokeAgentCoreDirect(
  payload: Record<string, unknown>,
): Promise<Record<string, unknown> | null> {
  const idToken = await getIdToken();
  const client = createClient(idToken);

  const sessionId = `direct-${Date.now()}-${'0'.repeat(20)}`;

  const command = new InvokeAgentRuntimeCommand({
    agentRuntimeArn: AGENTCORE_ARN,
    runtimeSessionId: sessionId,
    payload: new TextEncoder().encode(JSON.stringify(payload)),
  });

  try {
    const response = await client.send(command);
    const body = response.response;
    if (!body) return null;

    const text = await body.transformToString();

    // Parse SSE — metrics yields a single event
    const events = parseSSEEvents(text);
    for (const evt of events) {
      if (evt.action === 'metrics' && evt.data) {
        return evt as Record<string, unknown>;
      }
    }

    // Fallback: try direct JSON parse
    return JSON.parse(text);
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : 'Unknown error';
    console.error('AgentCore direct invocation failed:', msg);
    return null;
  }
}
