// Trading API client for enhanced backend

interface TraderSummary {
  trader_id: string;
  balance: number;
  roe: number;
  target_roe: number;
  drawdown: number;
  total_trades: number;
  active_trades: number;
  win_rate: number;
  signals_generated: number;
  long_signals: number;
  short_signals: number;
  signal_balance: string;
  is_running: boolean;
  current_price: number;
  last_error?: string;
}

interface Trade {
  id: string;
  signal: string;
  entry_price: number;
  quantity: number;
  leverage: number;
  stop_loss: number;
  take_profit: number;
  timestamp: string;
  status: string;
  exit_price?: number;
  pnl: number;
}

interface Signal {
  id: string;
  direction: string;
  price: number;
  confidence: number;
  timestamp: string;
  long_ratio: number;
  short_ratio: number;
}

interface CreateTraderResponse {
  trader_id: string;
  status: string;
}

interface TradesResponse {
  trades: Trade[];
  total_trades: number;
  active_trades: number;
}

interface SignalsResponse {
  signals: Signal[];
  total_signals: number;
  balance_ratio: string;
}

interface TradersListResponse {
  traders: string[];
  total: number;
}

export class TradingAPI {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:5000/api') {
    this.baseUrl = baseUrl;
  }

  private async makeRequest(endpoint: string, method: string = 'GET', body?: any) {
    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error (${method} ${endpoint}):`, error);
      throw error;
    }
  }

  // Enhanced API methods based on backend
  async createTrader(): Promise<CreateTraderResponse> {
    return this.makeRequest('/trader/create', 'POST', {});
  }

  async startTrader(traderId: string) {
    return this.makeRequest(`/trader/${traderId}/start`, 'POST');
  }

  async stopTrader(traderId: string) {
    return this.makeRequest(`/trader/${traderId}/stop`, 'POST');
  }

  async getTraderSummary(traderId: string): Promise<TraderSummary> {
    return this.makeRequest(`/trader/${traderId}/summary`);
  }

  async getTraderTrades(traderId: string): Promise<TradesResponse> {
    return this.makeRequest(`/trader/${traderId}/trades`);
  }

  async getTraderSignals(traderId: string): Promise<SignalsResponse> {
    return this.makeRequest(`/trader/${traderId}/signals`);
  }

  async listTraders(): Promise<TradersListResponse> {
    return this.makeRequest('/traders');
  }

  async deleteTrader(traderId: string) {
    return this.makeRequest(`/trader/${traderId}/delete`, 'DELETE');
  }

  async executeManualTrade(traderId: string, direction: 'LONG' | 'SHORT') {
    return this.makeRequest(`/trader/${traderId}/manual-trade`, 'POST', { direction });
  }

  async forceBalanceSignals(traderId: string) {
    return this.makeRequest(`/trader/${traderId}/force-balance`, 'POST');
  }

  async healthCheck() {
    return this.makeRequest('/health');
  }
}

export const api = new TradingAPI();