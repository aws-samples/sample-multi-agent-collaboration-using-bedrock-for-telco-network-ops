import React, { useState, useRef, useEffect } from 'react';
import { Bot, Wrench, AlertTriangle, BarChart3, Send, Loader2, Plus, MessageSquare, Clock, Trash2 } from 'lucide-react';
import { api } from '../services/api';
import { UserMessage } from './UserMessage';
import { AIMessage } from './AIMessage';
import type { IMessage } from '../types';

interface IChatSession {
  sessionId: string;
  createdAt: string;
}

interface IChatInterfaceProps {
  initialQuery?: string;
  onQuerySent?: () => void;
  userId?: string;
}

export const ChatInterface: React.FC<IChatInterfaceProps> = ({ initialQuery, onQuerySent, userId = 'anonymous' }) => {
  const [messages, setMessages] = useState<IMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [sessions, setSessions] = useState<IChatSession[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const skipHistoryLoadRef = useRef(false);

  // Session ID: persisted in localStorage so it survives refresh.
  const getOrCreateSessionId = (): string => {
    const key = `netops_session_${userId}`;
    const saved = localStorage.getItem(key);
    if (saved) return saved;
    const newId = `sess-${crypto.randomUUID().slice(0, 12)}`;
    localStorage.setItem(key, newId);
    return newId;
  };
  const [activeSessionId, setActiveSessionId] = useState(getOrCreateSessionId());
  const sessionIdRef = useRef(activeSessionId);

  // Keep ref in sync with state
  useEffect(() => { sessionIdRef.current = activeSessionId; }, [activeSessionId]);

  // Load sessions list on mount — include current session
  useEffect(() => {
    const loadSessions = async () => {
      try {
        const list = await api.getChatSessions(userId);
        // Filter out sessions the user previously deleted
        const deletedKey = `netops_deleted_sessions_${userId}`;
        const deletedSet: string[] = JSON.parse(localStorage.getItem(deletedKey) || '[]');
        const filtered = deletedSet.length > 0
          ? list.filter(s => !deletedSet.includes(s.sessionId))
          : list;
        // Sort newest first by createdAt
        filtered.sort((a, b) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
        // Ensure current session is in the list
        // Compare with padding since AgentCore pads session IDs to 33 chars
        const currentId = sessionIdRef.current;
        const paddedCurrentId = currentId.padEnd(33, '0');
        const hasCurrentSession = filtered.some(
          s => s.sessionId === currentId || s.sessionId === paddedCurrentId
        );
        if (!hasCurrentSession) {
          filtered.unshift({ sessionId: currentId, createdAt: new Date().toISOString() });
        }
        setSessions(filtered);
      } catch (e) {
        console.warn('Failed to load sessions:', e);
        // Still show current session
        setSessions([{ sessionId: sessionIdRef.current, createdAt: new Date().toISOString() }]);
      }
    };
    loadSessions();
  }, [userId]);

  // Load conversation history when session changes
  useEffect(() => {
    // Skip if we just created a fresh session for a quick action
    if (skipHistoryLoadRef.current) {
      skipHistoryLoadRef.current = false;
      return;
    }
    const loadHistory = async () => {
      try {
        const history = await api.getChatHistory(activeSessionId, userId);
        if (history.length > 0) {
          const restored: IMessage[] = history.map((msg, idx) => ({
            id: `history-${idx}`,
            role: msg.role as 'user' | 'assistant',
            content: msg.content,
            timestamp: new Date(),
          }));
          setMessages(restored);
        } else {
          setMessages([]);
        }
      } catch (e) {
        console.warn('Failed to load chat history:', e);
      }
    };
    loadHistory();
  }, [activeSessionId, userId]);

  const handleNewSession = () => {
    const newId = `sess-${crypto.randomUUID().slice(0, 12)}`;
    localStorage.setItem(`netops_session_${userId}`, newId);
    setActiveSessionId(newId);
    setMessages([]);
    // Add to local sessions list
    setSessions(prev => [{ sessionId: newId, createdAt: new Date().toISOString() }, ...prev]);
  };

  const handleSwitchSession = (sessionId: string) => {
    localStorage.setItem(`netops_session_${userId}`, sessionId);
    setActiveSessionId(sessionId);
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const deleted = await api.deleteChatSession(sessionId, userId);
    if (deleted) {
      // Track deleted sessions in localStorage so they stay hidden
      const key = `netops_deleted_sessions_${userId}`;
      const deletedSet: string[] = JSON.parse(localStorage.getItem(key) || '[]');
      deletedSet.push(sessionId);
      localStorage.setItem(key, JSON.stringify(deletedSet));

      const remaining = sessions.filter(s => s.sessionId !== sessionId);
      setSessions(remaining);

      // Only act if we deleted the currently active session
      const isActive = sessionId === activeSessionId
        || sessionId.startsWith(activeSessionId)
        || activeSessionId.startsWith(sessionId);
      if (isActive) {
        if (remaining.length > 0) {
          // Switch to the most recent remaining session
          handleSwitchSession(remaining[0].sessionId);
        } else {
          // No sessions left — create a fresh one
          handleNewSession();
        }
      }
    }
  };

  const [showPrefillBanner, setShowPrefillBanner] = useState(false);
  const sendButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!initialQuery) return;
    try {
      const action = JSON.parse(initialQuery) as { query: string; autoSend?: boolean; ts: number };
      const query = action.query;

      // Create a new session
      const newId = `sess-${crypto.randomUUID().slice(0, 12)}`;
      localStorage.setItem(`netops_session_${userId}`, newId);
      sessionIdRef.current = newId;
      skipHistoryLoadRef.current = true;
      setActiveSessionId(newId);
      setMessages([]);
      setSessions(prev => [{ sessionId: newId, createdAt: new Date().toISOString() }, ...prev]);

      // Both types: prefill the input
      setInput(query);

      if (action.autoSend) {
        // Instant query: click Send after React renders the prefilled input
        setShowPrefillBanner(false);
        if (onQuerySent) onQuerySent();
        setTimeout(() => {
          sendButtonRef.current?.click();
        }, 300);
      } else {
        // Site-specific: show banner, let user edit and send manually
        setShowPrefillBanner(true);
      }
    } catch {
      setInput(initialQuery);
    }
  }, [initialQuery]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendWithQuery = async (query: string) => {
    if (!query.trim() || isStreaming) return;

    if (onQuerySent) onQuerySent();

    const userMessage: IMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsStreaming(true);

    const assistantMessage: IMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };

    setMessages((prev) => [...prev, assistantMessage]);

    try {
      for await (const event of api.streamChat(query, sessionIdRef.current, userId)) {
        if (event.type === 'thinking' && event.content) {
          // Accumulate thinking content with <thinking> tags
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              // Prepend thinking to content (will be parsed by AIMessage)
              const thinkingBlock = `<thinking>${event.content}</thinking>\n`;
              updated[updated.length - 1] = {
                ...lastMsg,
                content: thinkingBlock + lastMsg.content
              };
            }
            return updated;
          });
        } else if (event.type === 'mcp_tool' && event.tool) {
          // MCP tool invocation — inject as <mcp_tool> tag for distinct UI
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              const paramsStr = event.params ? JSON.stringify(event.params) : '{}';
              const mcpBlock = `<mcp_tool name="${event.tool}" params='${paramsStr}'></mcp_tool>\n`;
              updated[updated.length - 1] = {
                ...lastMsg,
                content: mcpBlock + lastMsg.content
              };
            }
            return updated;
          });
        } else if (event.type === 'code_interpreter' && event.tool) {
          // Code Interpreter invocation
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              const ciBlock = `<code_interpreter></code_interpreter>\n`;
              updated[updated.length - 1] = {
                ...lastMsg,
                content: ciBlock + lastMsg.content
              };
            }
            return updated;
          });
        } else if (event.type === 'image' && event.data) {
          // Image from Code Interpreter — inject as <ci_image> tag
          const mimeType = event.mimeType || 'image/png';
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              const imgTag = `\n\n<ci_image mime="${mimeType}" data="${event.data}"></ci_image>\n\n`;
              updated[updated.length - 1] = {
                ...lastMsg,
                content: lastMsg.content + imgTag
              };
            }
            return updated;
          });
        } else if (event.type === 'token' && event.content) {
          // Update the last message with new content
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              // Create a new object to ensure React detects the change
              const newContent = lastMsg.content + event.content;
              updated[updated.length - 1] = {
                ...lastMsg,
                content: newContent
              };
            }
            return updated;
          });
        } else if (event.type === 'done') {
          setMessages((prev) => {
            const updated = [...prev];
            const lastMsg = updated[updated.length - 1];
            if (lastMsg && lastMsg.role === 'assistant') {
              updated[updated.length - 1] = {
                ...lastMsg,
                isStreaming: false
              };
            }
            return updated;
          });
        }
      }
    } catch (error) {
      console.error('Error streaming chat:', error);
      setMessages((prev) => {
        const updated = [...prev];
        const lastMsg = updated[updated.length - 1];
        if (lastMsg.role === 'assistant') {
          lastMsg.content = 'Error: Failed to get response from server.';
          lastMsg.isStreaming = false;
        }
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  const handleSend = () => handleSendWithQuery(input);

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex h-full bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      {/* Session Sidebar */}
      <div className="w-56 flex-shrink-0 bg-white dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700 flex flex-col">
        <div className="p-3 border-b border-slate-200 dark:border-slate-700">
          <button
            onClick={handleNewSession}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium
                       bg-emerald-500 hover:bg-emerald-600 text-white transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {sessions.map((s) => (
            <div
              key={s.sessionId}
              className={`group w-full text-left px-3 py-2 rounded-lg text-xs transition-colors flex items-start gap-2 cursor-pointer ${
                s.sessionId === activeSessionId
                  ? 'bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800'
                  : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700'
              }`}
              onClick={() => handleSwitchSession(s.sessionId)}
            >
              <MessageSquare className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{s.sessionId.slice(0, 16)}</div>
                {s.createdAt && (
                  <div className="flex items-center gap-1 text-[10px] text-slate-400 mt-0.5">
                    <Clock className="w-2.5 h-2.5" />
                    {new Date(s.createdAt).toLocaleDateString()}
                  </div>
                )}
              </div>
              <button
                onClick={(e) => handleDeleteSession(s.sessionId, e)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-slate-400 hover:text-red-500 transition-all flex-shrink-0"
                title="Delete session"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))}
          {sessions.length === 0 && (
            <p className="text-xs text-slate-400 text-center py-4">No previous sessions</p>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 && (
          <div className="text-center text-slate-600 dark:text-slate-400 mt-12 animate-fadeIn">
            <div className="mb-6">
              <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-2xl shadow-lg mb-4">
                <Bot className="w-10 h-10 text-white" />
              </div>
            </div>
            <h2 className="text-3xl font-bold mb-4 text-slate-900 dark:text-slate-100">
              Welcome to Network Operations
            </h2>
            <p className="mb-8 text-lg">Ask me about maintenance, alarms, or performance metrics!</p>
            <div className="text-left max-w-2xl mx-auto bg-white dark:bg-slate-800 rounded-2xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
              <p className="font-semibold text-slate-900 dark:text-slate-100 mb-3 flex items-center gap-2">
                <span className="text-emerald-500">💡</span>
                Try asking:
              </p>
              <ul className="space-y-3 text-sm">
                <li className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors cursor-pointer">
                  <Wrench className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                  <span>"Check maintenance for site_atlanta_001"</span>
                </li>
                <li className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors cursor-pointer">
                  <AlertTriangle className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                  <span>"Show all active alarms"</span>
                </li>
                <li className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors cursor-pointer">
                  <BarChart3 className="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                  <span>"Analyze KPIs for site_dallas_003"</span>
                </li>
              </ul>
            </div>
          </div>
        )}
        
        {messages.map((message) => (
          message.role === 'user' ? (
            <UserMessage key={message.id} message={message} />
          ) : (
            <AIMessage key={message.id} message={message} />
          )
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 shadow-lg">
        {showPrefillBanner && input && (
          <div className="max-w-4xl mx-auto mb-3 px-4 py-2.5 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400">
            <span>✏️</span>
            <span>Query prefilled — edit the site name if needed, then click Send</span>
            <button onClick={() => setShowPrefillBanner(false)} className="ml-auto text-amber-400 hover:text-amber-600">✕</button>
          </div>
        )}
        <div className="flex gap-3 max-w-4xl mx-auto">
          <input
            type="text"
            value={input}
            onChange={(e) => { setInput(e.target.value); setShowPrefillBanner(false); }}
            onKeyPress={handleKeyPress}
            placeholder="Ask about maintenance, alarms, or performance..."
            disabled={isStreaming}
            className="flex-1 px-5 py-3 border-2 border-slate-300 dark:border-slate-600 rounded-xl 
                     bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100
                     placeholder-slate-400 dark:placeholder-slate-500
                     focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-all shadow-sm"
          />
          <button
            ref={sendButtonRef}
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            className="px-8 py-3 bg-gradient-to-r from-emerald-500 to-teal-600 text-white font-semibold rounded-xl 
                     hover:from-emerald-600 hover:to-teal-700
                     disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:from-emerald-500 disabled:hover:to-teal-600
                     transition-all shadow-md hover:shadow-lg transform hover:-translate-y-0.5
                     flex items-center gap-2"
          >
            {isStreaming ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Sending...</span>
              </>
            ) : (
              <>
                <span>Send</span>
                <Send className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      </div>
      </div>{/* end Main Chat Area */}
    </div>
  );
};
