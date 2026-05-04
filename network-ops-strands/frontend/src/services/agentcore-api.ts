/**
 * AgentCore Direct API Service
 * 
 * This service connects directly to AgentCore's local HTTP endpoint
 * when running `agentcore dev`. This bypasses the FastAPI wrapper
 * and connects directly to the AgentCore runtime.
 * 
 * Usage:
 * 1. Start AgentCore: `agentcore dev --port 8080`
 * 2. Set VITE_USE_AGENTCORE_DIRECT=true in .env
 * 3. Frontend will connect to http://localhost:8080/invocations
 */

import type { IWhitelabelConfig, IDashboardMetrics } from '../types';

const AGENTCORE_URL = import.meta.env.VITE_AGENTCORE_ENDPOINT || 'http://localhost:8080';
const USE_DIRECT = import.meta.env.VITE_USE_AGENTCORE_DIRECT === 'true';

export const agentcoreApi = {
  /**
   * Stream chat responses directly from AgentCore
   */
  async* streamChat(message: string, sessionId: string = 'default') {
    const startTime = Date.now();
    console.log(`[${new Date().toISOString()}] 🚀 AgentCore direct: Starting stream for message:`, message.substring(0, 50));
    
    const response = await fetch(`${AGENTCORE_URL}/invocations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        input: message,
        session_id: sessionId,
        stream: true
      }),
    });

    if (!response.ok) {
      throw new Error(`AgentCore request failed: ${response.status} ${response.statusText}`);
    }
    
    if (!response.body) {
      throw new Error('No response body from AgentCore');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullResponse = '';
    let firstTokenTime: number | null = null;
    let tokenCount = 0;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        
        // AgentCore streams JSON lines
        const lines = chunk.split('\n').filter(line => line.trim());
        
        for (const line of lines) {
          try {
            const data = JSON.parse(line);
            
            // Handle different AgentCore event types
            if (data.type === 'content_block_delta' && data.delta?.text) {
              if (!firstTokenTime) {
                firstTokenTime = Date.now();
                console.log(`[${new Date().toISOString()}] ⚡ First token after ${firstTokenTime - startTime}ms`);
              }
              
              const text = data.delta.text;
              fullResponse += text;
              tokenCount++;
              
              yield {
                type: 'token',
                content: text
              };
            } else if (data.type === 'message_stop' || data.type === 'done') {
              yield {
                type: 'done'
              };
            }
          } catch (e) {
            // Skip invalid JSON lines
            console.warn('Failed to parse AgentCore response line:', line);
          }
        }
      }
      
      const endTime = Date.now();
      console.log(`[${new Date().toISOString()}] ✅ AgentCore stream complete after ${endTime - startTime}ms`);
      console.log(`[${new Date().toISOString()}] 📊 Total tokens: ${tokenCount}, Response length: ${fullResponse.length} chars`);
      console.log(`[${new Date().toISOString()}] 📝 Full response:\n${fullResponse}`);
      
    } finally {
      reader.releaseLock();
    }
  },

  /**
   * Get configuration (fallback to default)
   */
  async getConfig(): Promise<IWhitelabelConfig> {
    // When using AgentCore direct, return default config
    return {
      companyName: 'Network Operations Platform',
      logoUrl: '/logo.svg',
      primaryColor: '#10b981',
      secondaryColor: '#14b8a6',
      features: {
        darkMode: true,
        dashboard: true
      }
    };
  },

  /**
   * Get dashboard metrics (fallback to mock data)
   */
  async getDashboardMetrics(): Promise<IDashboardMetrics> {
    // When using AgentCore direct, return mock metrics
    // In production, you'd query the agents directly
    return {
      activeAlarms: {
        critical: 3,
        major: 13,
        minor: 10,
        warning: 0
      },
      ongoingMaintenance: 2,
      sitesMonitored: 20,
      averageLatency: 18.5
    };
  },
};

/**
 * Check if AgentCore is available
 */
export async function checkAgentCoreHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${AGENTCORE_URL}/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(2000)
    });
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Get the appropriate API based on configuration
 */
export function getApi() {
  if (USE_DIRECT) {
    console.log('🔧 Using AgentCore direct API');
    return agentcoreApi;
  }
  
  // Import the regular API
  console.log('🔧 Using FastAPI wrapper');
  return import('./api').then(m => m.api);
}
