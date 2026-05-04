export interface IMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface IWhitelabelConfig {
  companyName: string;
  logoUrl: string;
  primaryColor: string;
  secondaryColor: string;
  accentColor?: string;
  faviconUrl?: string;
  description?: string;
  features?: {
    darkMode?: boolean;
    dashboard?: boolean;
    traceViewer?: boolean;
  };
}

export interface IDashboardMetrics {
  activeAlarms: {
    critical: number;
    major: number;
    minor: number;
    warning: number;
  };
  ongoingMaintenance: number;
  sitesMonitored: number;
  averageLatency: number;
}

export interface IChatStreamEvent {
  type: 'token' | 'done' | 'error' | 'thinking' | 'mcp_tool' | 'code_interpreter' | 'image' | 'image_inline';
  content?: string;
  error?: string;
  tool?: string;
  params?: Record<string, unknown>;
  data?: string;
  mimeType?: string;
}
