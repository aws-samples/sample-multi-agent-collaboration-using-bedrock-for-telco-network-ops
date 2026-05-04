import type { IWhitelabelConfig, IDashboardMetrics } from '../types';
import { isAgentCoreMode, invokeAgentCore } from './agentcoreService';

const API_BASE_URL = import.meta.env.VITE_API_ENDPOINT || 'http://localhost:8000';
// API Gateway endpoint for non-LLM calls (metrics, topology, history, config)
const API_GW_URL = import.meta.env.VITE_API_GW_ENDPOINT || API_BASE_URL;

export const api = {
  async getConfig(): Promise<IWhitelabelConfig> {
    try {
      const base = isAgentCoreMode() ? API_GW_URL : API_BASE_URL;
      const response = await fetch(`${base}/api/config`);
      if (response.ok) {
        const data = await response.json();
        return data.branding || data;
      }
    } catch (e) {
      console.warn('Config fetch failed, using defaults:', e);
    }
    return {
      companyName: 'Network Operations',
      logoUrl: '',
      primaryColor: '#3B82F6',
      secondaryColor: '#8B5CF6',
    };
  },

  async getDashboardMetrics(): Promise<IDashboardMetrics> {
    const base = isAgentCoreMode() ? API_GW_URL : API_BASE_URL;
    const url = isAgentCoreMode() ? `${base}/api/metrics` : `${base}/api/dashboard/metrics`;
    try {
      const response = await fetch(url);
      if (response.ok) return response.json();
    } catch (e) {
      console.warn('Metrics fetch failed:', e);
    }
    return {
      activeAlarms: { critical: 0, major: 0, minor: 0, warning: 0 },
      ongoingMaintenance: 0,
      sitesMonitored: 20,
      averageLatency: 18.5,
    };
  },

  async getTopology(profile: string = 'datacenter') {
    const base = isAgentCoreMode() ? API_GW_URL : API_BASE_URL;
    try {
      const response = await fetch(`${base}/api/topology?profile=${profile}`);
      if (response.ok) return response.json();
    } catch (e) {
      console.warn('Topology fetch failed:', e);
    }
    return { nodes: [], edges: [] };
  },

  async getChatSessions(
    actorId: string,
  ): Promise<Array<{sessionId: string; createdAt: string}>> {
    const base = isAgentCoreMode() ? API_GW_URL : API_BASE_URL;
    try {
      const response = await fetch(
        `${base}/api/chat/sessions?actor_id=${encodeURIComponent(actorId)}`
      );
      if (response.ok) {
        const data = await response.json();
        return data.sessions || [];
      }
    } catch (e) {
      console.warn('Chat sessions fetch failed:', e);
    }
    return [];
  },

  async deleteChatSession(
    sessionId: string,
    actorId: string,
  ): Promise<boolean> {
    const base = isAgentCoreMode() ? API_GW_URL : API_BASE_URL;
    try {
      const response = await fetch(
        `${base}/api/chat/sessions?session_id=${encodeURIComponent(sessionId)}&actor_id=${encodeURIComponent(actorId)}&action=delete`
      );
      if (response.ok) {
        const data = await response.json();
        return data.deleted === true;
      }
    } catch (e) {
      console.warn('Delete session failed:', e);
    }
    return false;
  },

  async getChatHistory(
    sessionId: string = 'default',
    actorId: string = 'default',
  ): Promise<Array<{role: string; content: string}>> {
    const base = isAgentCoreMode() ? API_GW_URL : API_BASE_URL;
    try {
      const response = await fetch(
        `${base}/api/chat/history?session_id=${encodeURIComponent(sessionId)}&actor_id=${encodeURIComponent(actorId)}`
      );
      if (response.ok) {
        const data = await response.json();
        return data.messages || [];
      }
    } catch (e) {
      console.warn('Chat history fetch failed:', e);
    }
    return [];
  },

  async* streamChat(message: string, sessionId: string = 'default', userId: string = 'anonymous') {
    // Use AgentCore direct invocation in production
    if (isAgentCoreMode()) {
      console.log(`[${new Date().toISOString()}] 🚀 AgentCore mode: invoking agent directly`);
      yield* invokeAgentCore(message, sessionId, userId);
      return;
    }

    // Local mode: use FastAPI backend
    const startTime = Date.now();
    console.log(`[${new Date().toISOString()}] 🚀 Local mode: streaming via FastAPI`);
    
    const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message, session_id: sessionId, user_id: userId }),
    });

    if (!response.ok) throw new Error('Failed to send message');
    if (!response.body) throw new Error('No response body');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullResponse = '';
    let fullThinking = '';
    let firstTokenTime: number | null = null;
    let tokenCount = 0;
    let thinkingCount = 0;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'thinking' && data.content) {
              if (!firstTokenTime) {
                firstTokenTime = Date.now();
                console.log(`[${new Date().toISOString()}] 💭 First thinking received after ${firstTokenTime - startTime}ms`);
              }
              fullThinking += data.content;
              thinkingCount++;
            } else if (data.type === 'mcp_tool' && data.tool) {
              console.log(`[${new Date().toISOString()}] 🌐 MCP tool invoked: ${data.tool}`, data.params || {});
            } else if (data.type === 'code_interpreter') {
              console.log(`[${new Date().toISOString()}] 💻 Code Interpreter invoked`);
            } else if (data.type === 'token' && data.content) {
              if (!firstTokenTime) {
                firstTokenTime = Date.now();
                console.log(`[${new Date().toISOString()}] ⚡ First token received after ${firstTokenTime - startTime}ms`);
              }
              fullResponse += data.content;
              tokenCount++;
            }
            
            yield data;
          }
        }
      }
      
      const endTime = Date.now();
      console.log(`[${new Date().toISOString()}] ✅ Stream complete after ${endTime - startTime}ms`);
      console.log(`[${new Date().toISOString()}] 📊 Tokens: ${tokenCount}, Thinking: ${thinkingCount}`);
      if (fullThinking) {
        console.log(`[${new Date().toISOString()}] 💭 Thinking length: ${fullThinking.length} chars`);
      }
      console.log(`[${new Date().toISOString()}] 📝 Response length: ${fullResponse.length} chars`);
      
    } finally {
      reader.releaseLock();
    }
  },
};
