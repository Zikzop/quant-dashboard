type MessageHandler = (data: Record<string, unknown>) => void;

interface WSConfig {
  url: string;
  onMessage: MessageHandler;
  onStatusChange?: (status: "CONNECTED" | "RECONNECTING" | "DISCONNECTED") => void;
  reconnectMs?: number;
  maxReconnectMs?: number;
}

export class TerminalWebSocket {
  private ws: WebSocket | null = null;
  private config: WSConfig;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private currentDelay: number;
  private destroyed = false;
  private _latency = 0;

  constructor(config: WSConfig) {
    this.config = config;
    this.currentDelay = config.reconnectMs ?? 1000;
  }

  get latency(): number {
    return this._latency;
  }

  connect(): void {
    if (this.destroyed) return;
    this.cleanup();

    try {
      this.ws = new WebSocket(this.config.url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.currentDelay = this.config.reconnectMs ?? 1000;
      this.config.onStatusChange?.("CONNECTED");
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data._ts) {
          this._latency = Date.now() - data._ts;
        }
        this.config.onMessage(data);
      } catch {
        // malformed message, ignore
      }
    };

    this.ws.onclose = () => {
      if (!this.destroyed) {
        this.config.onStatusChange?.("RECONNECTING");
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  private scheduleReconnect(): void {
    if (this.destroyed) return;
    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, this.currentDelay);
    const maxDelay = this.config.maxReconnectMs ?? 30000;
    this.currentDelay = Math.min(this.currentDelay * 1.5, maxDelay);
  }

  private cleanup(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      if (this.ws.readyState <= WebSocket.OPEN) {
        this.ws.close();
      }
      this.ws = null;
    }
  }

  send(data: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  destroy(): void {
    this.destroyed = true;
    this.config.onStatusChange?.("DISCONNECTED");
    this.cleanup();
  }
}
