import React, { useState, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, Loader2, Eye, EyeOff, Copy, Check, Globe, Zap, Terminal } from 'lucide-react';
import { Chart as ChartJS, registerables } from 'chart.js';
import { Chart } from 'react-chartjs-2';
import type { IMessage } from '../types';

// Register all Chart.js components
ChartJS.register(...registerables);

interface IAIMessageProps {
  message: IMessage;
}

interface McpToolCall {
  name: string;
  params: Record<string, unknown>;
}

interface CiImage {
  mime: string;
  data: string;
}

interface ParsedContent {
  thinking: string | null;
  toolCalls: string[];
  mcpTools: McpToolCall[];
  hasCodeInterpreter: boolean;
  images: CiImage[];
  charts: ChartConfig[];
  mainContent: string;
}

interface ChartConfig {
  type: string;
  data: Record<string, unknown>;
  options?: Record<string, unknown>;
}

const MCP_TOOL_LABELS: Record<string, { label: string; icon: string }> = {
  check_power_outages: { label: 'Power Outage Check', icon: '⚡' },
  check_811_dig_requests: { label: '811 Dig Request Check', icon: '🚧' },
  check_weather_events: { label: 'Weather Event Check', icon: '🌩️' },
  get_external_context_summary: { label: 'External Context Analysis', icon: '🔍' },
};

const parseContent = (content: string): ParsedContent => {
  // Extract thinking blocks
  const thinkingRegex = /<thinking>([\s\S]*?)<\/thinking>/g;
  const thinkingMatches = [...content.matchAll(thinkingRegex)];
  const thinking = thinkingMatches.map(m => m[1].trim()).join('\n\n') || null;

  // Extract MCP tool calls
  const mcpToolRegex = /<mcp_tool\s+name="([^"]+)"\s+params='([^']*)'><\/mcp_tool>/g;
  const mcpMatches = [...content.matchAll(mcpToolRegex)];
  const mcpTools: McpToolCall[] = mcpMatches.map(m => {
    let params = {};
    try { params = JSON.parse(m[2]); } catch {}
    return { name: m[1], params };
  });

  // Extract Code Interpreter blocks
  const ciRegex = /<code_interpreter><\/code_interpreter>/g;
  const hasCodeInterpreter = ciRegex.test(content);

  // Extract Code Interpreter images
  const ciImageRegex = /<ci_image\s+mime="([^"]+)"\s+data="([^"]+)"><\/ci_image>/g;
  const imageMatches = [...content.matchAll(ciImageRegex)];
  const images: CiImage[] = imageMatches.map(m => ({ mime: m[1], data: m[2] }));

  // Extract Chart.js configurations
  const chartRegex = /<chart>([\s\S]*?)<\/chart>/g;
  const chartMatches = [...content.matchAll(chartRegex)];
  const charts: ChartConfig[] = [];
  for (const m of chartMatches) {
    try {
      const config = JSON.parse(m[1].trim());
      charts.push(config);
    } catch (e) {
      console.warn('Failed to parse chart config:', e);
    }
  }

  // Extract tool calls
  const toolRegex = /Tool #\d+:.*?\n/g;
  const routingRegex = /[🔧🚨📊]\s*Routing to.*?\n/g;
  const toolCalls = [
    ...content.match(toolRegex) || [],
    ...content.match(routingRegex) || []
  ];

  // Remove all tags from main content
  let mainContent = content
    .replace(thinkingRegex, '')
    .replace(mcpToolRegex, '')
    .replace(/<code_interpreter><\/code_interpreter>/g, '')
    .replace(ciImageRegex, '')
    .replace(chartRegex, '')
    .replace(toolRegex, '')
    .replace(routingRegex, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  return { thinking, toolCalls, mcpTools, hasCodeInterpreter, images, charts, mainContent };
};

export const AIMessage: React.FC<IAIMessageProps> = ({ message }) => {
  // Load initial state from localStorage, default to true (show thinking by default)
  const [showThinking, setShowThinking] = useState(() => {
    const saved = localStorage.getItem('showThinking');
    return saved !== null ? saved === 'true' : true; // Default to true
  });
  const [copied, setCopied] = useState(false);

  // Save preference to localStorage whenever it changes
  const toggleThinking = () => {
    const newValue = !showThinking;
    setShowThinking(newValue);
    localStorage.setItem('showThinking', String(newValue));
  };

  const parsed = useMemo(() => {
    return parseContent(message.content);
  }, [message.content, message.isStreaming]);
  
  const hasThinking = parsed.thinking || parsed.toolCalls.length > 0 || parsed.mcpTools.length > 0;
  const hasMcpTools = parsed.mcpTools.length > 0;
  
  // Check if we're streaming but have no main content yet
  const isLoadingResponse = message.isStreaming && !parsed.mainContent.trim();

  const handleCopy = async () => {
    await navigator.clipboard.writeText(parsed.mainContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyThinking = async () => {
    const thinkingText = [
      parsed.thinking,
      ...parsed.toolCalls
    ].filter(Boolean).join('\n\n');
    await navigator.clipboard.writeText(thinkingText);
  };

  return (
    <div className="flex flex-col max-w-full items-start relative group">
      {/* Header with avatar and controls */}
      <div className="flex items-center mb-2 self-start">
        <div className="relative flex shrink-0 overflow-hidden rounded-full h-8 w-8">
          <div className="flex h-full w-full items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-teal-600">
            <Bot className="w-5 h-5 text-white" />
          </div>
        </div>
        
        {hasThinking && (
          <div className="flex ml-2 text-xs text-slate-500 dark:text-slate-400 items-center gap-2">
            <button
              onClick={toggleThinking}
              className="flex items-center gap-1 px-2 py-1 rounded-md hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            >
              {showThinking ? (
                <>
                  <EyeOff className="w-4 h-4" />
                  Hide thinking
                </>
              ) : (
                <>
                  <Eye className="w-4 h-4" />
                  Show thinking
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Main content */}
      <div className="rounded-lg max-w-full">
        <div className="prose prose-sm max-w-none break-words dark:prose-invert">
          
          {/* MCP Tool Calls */}
          {hasMcpTools && (
            <div className="mb-3 space-y-2 max-w-sm">
              {parsed.mcpTools.map((mcp, idx) => {
                const meta = MCP_TOOL_LABELS[mcp.name] || { label: mcp.name, icon: '🌐' };
                const siteId = (mcp.params.site_id as string) || '';
                return (
                  <div
                    key={idx}
                    className="flex items-center gap-3 px-4 py-2.5 bg-indigo-50 dark:bg-indigo-900/20 border border-indigo-200 dark:border-indigo-800 rounded-lg"
                  >
                    <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-100 dark:bg-indigo-900/40">
                      <Globe className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
                          MCP
                        </span>
                        <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                          {meta.icon} {meta.label}
                        </span>
                      </div>
                      {siteId && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                          Site: <code className="px-1 py-0.5 bg-indigo-100 dark:bg-indigo-900/40 rounded text-indigo-700 dark:text-indigo-300">{siteId}</code>
                        </p>
                      )}
                    </div>
                    <Zap className="w-4 h-4 text-indigo-400 dark:text-indigo-500 animate-pulse" />
                  </div>
                );
              })}
            </div>
          )}

          {/* Code Interpreter */}
          {parsed.hasCodeInterpreter && (
            <div className="mb-3 max-w-sm">
              <div className="flex items-center gap-3 px-4 py-2.5 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-amber-100 dark:bg-amber-900/40">
                  <Terminal className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                      AgentCore
                    </span>
                    <span className="text-sm font-medium text-slate-900 dark:text-slate-100">
                      💻 Code Interpreter
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Running Python analysis in secure sandbox
                  </p>
                </div>
                <Zap className="w-4 h-4 text-amber-400 dark:text-amber-500 animate-pulse" />
              </div>
            </div>
          )}

          {/* Thinking section */}
          {showThinking && hasThinking && (
            <div className="border-t border-slate-200 dark:border-slate-700 pt-2 mb-4">
              <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-lg text-sm text-slate-600 dark:text-slate-400 relative group/thinking">
                <button
                  onClick={handleCopyThinking}
                  className="absolute top-2 right-2 p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 opacity-0 group-hover/thinking:opacity-100 transition-opacity"
                  title="Copy thinking"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
                
                {parsed.thinking && (
                  <div className="prose prose-sm max-w-full dark:prose-invert">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {parsed.thinking}
                    </ReactMarkdown>
                  </div>
                )}
                
                {parsed.toolCalls.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-slate-200 dark:border-slate-700 text-xs">
                    {parsed.toolCalls.map((tool, idx) => (
                      <div key={idx} className="text-slate-500 dark:text-slate-500">
                        {tool}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Loading indicator - shows when streaming but no content yet */}
          {isLoadingResponse && (
            <div className="flex items-center gap-3 px-2 py-4 text-slate-500 dark:text-slate-400">
              <Loader2 className="w-4 h-4 animate-spin text-emerald-500" />
              <span className="text-sm">Generating response...</span>
            </div>
          )}

          {/* Main message content */}
          <div className="px-2">
            {parsed.mainContent && (
              <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ node, ...props }) => (
                  <h1 className="text-xl font-bold mb-3 mt-4 text-slate-900 dark:text-slate-100" {...props} />
                ),
                h2: ({ node, ...props }) => (
                  <h2 className="text-lg font-bold mb-2 mt-4 text-slate-900 dark:text-slate-100" {...props} />
                ),
                h3: ({ node, ...props }) => (
                  <h3 className="text-base font-semibold mb-2 mt-3 text-slate-900 dark:text-slate-100" {...props} />
                ),
                p: ({ node, ...props }) => (
                  <p className="my-2 leading-relaxed text-slate-700 dark:text-slate-300" {...props} />
                ),
                ul: ({ node, ...props }) => (
                  <ul className="list-disc list-outside ml-4 my-2 space-y-1 text-slate-700 dark:text-slate-300" {...props} />
                ),
                ol: ({ node, ...props }) => (
                  <ol className="list-decimal list-outside ml-4 my-2 space-y-1 text-slate-700 dark:text-slate-300" {...props} />
                ),
                li: ({ node, ...props }) => (
                  <li className="my-1" {...props} />
                ),
                code: ({ node, className, children, ...props }: any) => {
                  const inline = !className;
                  return inline ? (
                    <code className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-800 text-emerald-600 dark:text-emerald-400 rounded text-sm font-mono" {...props}>
                      {children}
                    </code>
                  ) : (
                    <code className="block p-3 bg-slate-100 dark:bg-slate-900 rounded-lg text-sm font-mono overflow-x-auto my-2" {...props}>
                      {children}
                    </code>
                  );
                },
                table: ({ node, ...props }) => (
                  <div className="overflow-x-auto my-4">
                    <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700 border border-slate-200 dark:border-slate-700" {...props} />
                  </div>
                ),
                thead: ({ node, ...props }) => (
                  <thead className="bg-slate-50 dark:bg-slate-800" {...props} />
                ),
                th: ({ node, ...props }) => (
                  <th className="px-4 py-2 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider border-b border-slate-200 dark:border-slate-700" {...props} />
                ),
                tbody: ({ node, ...props }) => (
                  <tbody className="bg-white dark:bg-slate-900 divide-y divide-slate-200 dark:divide-slate-700" {...props} />
                ),
                tr: ({ node, ...props }) => (
                  <tr className="hover:bg-slate-50 dark:hover:bg-slate-800/50" {...props} />
                ),
                td: ({ node, ...props }) => (
                  <td className="px-4 py-2 text-sm text-slate-700 dark:text-slate-300" {...props} />
                ),
                a: ({ node, ...props }) => (
                  <a className="text-emerald-600 dark:text-emerald-400 hover:underline" {...props} />
                ),
                blockquote: ({ node, ...props }) => (
                  <blockquote className="border-l-4 border-emerald-500 pl-4 italic text-slate-600 dark:text-slate-400 my-3 bg-slate-50 dark:bg-slate-800/50 py-2" {...props} />
                ),
                strong: ({ node, ...props }) => (
                  <strong className="font-bold text-slate-900 dark:text-slate-100" {...props} />
                ),
                hr: ({ node, ...props }) => (
                  <hr className="my-4 border-slate-200 dark:border-slate-700" {...props} />
                ),
              }}
            >
              {parsed.mainContent}
            </ReactMarkdown>
            )}
            
            {/* Chart.js interactive charts */}
            {parsed.charts.length > 0 && (
              <div className="my-4 space-y-4 not-prose max-w-full">
                {parsed.charts.map((chartConfig, idx) => (
                  <div key={idx} className="rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700 shadow-sm w-full">
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 dark:bg-blue-900/20 border-b border-slate-200 dark:border-slate-700">
                      <span className="text-sm">📊</span>
                      <span className="text-xs font-medium text-blue-700 dark:text-blue-400">Interactive Chart</span>
                    </div>
                    <div className="p-4 bg-white dark:bg-slate-800 w-full" style={{ height: '350px' }}>
                      <Chart
                        type={chartConfig.type as 'line' | 'bar' | 'doughnut' | 'radar' | 'pie'}
                        data={chartConfig.data as never}
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          ...(chartConfig.options as Record<string, unknown> || {}),
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {/* Code Interpreter generated images */}
            {parsed.images.length > 0 && (
              <div className="my-4 space-y-3">
                {parsed.images.map((img, idx) => (
                  <div key={idx} className="rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-50 dark:bg-amber-900/20 border-b border-slate-200 dark:border-slate-700">
                      <Terminal className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                      <span className="text-xs font-medium text-amber-700 dark:text-amber-400">Code Interpreter Output</span>
                    </div>
                    <img
                      src={`data:${img.mime};base64,${img.data}`}
                      alt={`Generated visualization ${idx + 1}`}
                      className="w-full max-w-2xl"
                    />
                  </div>
                ))}
              </div>
            )}
            
            {message.isStreaming && parsed.mainContent && (
              <span className="inline-block w-2 h-4 ml-1 bg-emerald-500 animate-pulse rounded" />
            )}
          </div>
        </div>
      </div>

      {/* Action buttons (copy) */}
      <div className="absolute -bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
        <div className="flex bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700">
          <button
            onClick={handleCopy}
            className="h-7 w-7 flex items-center justify-center hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors"
            title={copied ? 'Copied!' : 'Copy message'}
          >
            {copied ? (
              <Check className="w-4 h-4 text-emerald-600" />
            ) : (
              <Copy className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
