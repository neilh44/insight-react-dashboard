import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from 'recharts';
import { TrendingUp, TrendingDown, Activity, Signal, Target, AlertTriangle } from 'lucide-react';

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

interface AnalyticsSectionProps {
  trader: TraderSummary;
}

const AnalyticsSection: React.FC<AnalyticsSectionProps> = ({ trader }) => {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [tradesResponse, signalsResponse] = await Promise.all([
          api.getTraderTrades(trader.trader_id),
          api.getTraderSignals(trader.trader_id)
        ]);
        
        setTrades(tradesResponse.trades);
        setSignals(signalsResponse.signals);
      } catch (err) {
        console.error('Failed to load analytics data:', err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
    
    // Refresh every 5 seconds
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [trader.trader_id]);

  // Prepare performance chart data
  const performanceData = trades
    .filter(trade => trade.status.includes('closed'))
    .map((trade, index) => {
      const cumulativePnL = trades
        .slice(0, index + 1)
        .filter(t => t.status.includes('closed'))
        .reduce((sum, t) => sum + t.pnl, 0);
      
      return {
        index: index + 1,
        pnl: trade.pnl,
        cumulative: cumulativePnL,
        timestamp: new Date(trade.timestamp).toLocaleDateString()
      };
    });

  // Prepare signal distribution data
  const signalDistribution = [
    { name: 'LONG', value: trader.long_signals, color: '#10b981' },
    { name: 'SHORT', value: trader.short_signals, color: '#ef4444' }
  ];

  // Calculate win/loss distribution
  const closedTrades = trades.filter(trade => trade.status.includes('closed'));
  const winningTrades = closedTrades.filter(trade => trade.pnl > 0);
  const losingTrades = closedTrades.filter(trade => trade.pnl <= 0);
  
  const winLossData = [
    { name: 'Wins', value: winningTrades.length, color: '#10b981' },
    { name: 'Losses', value: losingTrades.length, color: '#ef4444' }
  ];

  // Recent signals chart data
  const recentSignals = signals.slice(-10).map((signal, index) => ({
    index: index + 1,
    price: signal.price,
    direction: signal.direction,
    confidence: signal.confidence,
    time: new Date(signal.timestamp).toLocaleTimeString()
  }));

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse">
          <div className="h-8 bg-muted rounded w-1/3 mb-4"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-muted rounded"></div>
            ))}
          </div>
          <div className="h-64 bg-muted rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-foreground">Analytics - Trader {trader.trader_id}</h2>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${trader.is_running ? 'bg-success' : 'bg-muted-foreground'}`} />
          <span className="text-sm text-muted-foreground">
            {trader.is_running ? 'Running' : 'Stopped'}
          </span>
        </div>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 border border-border rounded-lg bg-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Current Balance</p>
              <p className="text-2xl font-bold text-foreground">${trader.balance.toFixed(2)}</p>
            </div>
            <TrendingUp className="h-8 w-8 text-primary" />
          </div>
        </div>

        <div className="p-4 border border-border rounded-lg bg-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">ROE</p>
              <p className={`text-2xl font-bold ${
                trader.roe > 0 ? 'text-success' : trader.roe < 0 ? 'text-destructive' : 'text-muted-foreground'
              }`}>
                {trader.roe.toFixed(2)}%
              </p>
            </div>
            <Target className="h-8 w-8 text-primary" />
          </div>
        </div>

        <div className="p-4 border border-border rounded-lg bg-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Win Rate</p>
              <p className="text-2xl font-bold text-foreground">{trader.win_rate.toFixed(1)}%</p>
            </div>
            <Activity className="h-8 w-8 text-primary" />
          </div>
        </div>

        <div className="p-4 border border-border rounded-lg bg-card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Trades</p>
              <p className="text-2xl font-bold text-foreground">{trader.total_trades}</p>
            </div>
            <Signal className="h-8 w-8 text-primary" />
          </div>
        </div>
      </div>

      {/* Performance Chart */}
      <div className="p-6 border border-border rounded-lg bg-card">
        <h3 className="text-lg font-semibold text-foreground mb-4">Performance Chart</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={performanceData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="index" stroke="hsl(var(--muted-foreground))" />
            <YAxis stroke="hsl(var(--muted-foreground))" />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: 'hsl(var(--card))', 
                border: '1px solid hsl(var(--border))',
                borderRadius: '6px'
              }}
            />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="cumulative" 
              stroke="hsl(var(--primary))" 
              strokeWidth={2}
              name="Cumulative P&L"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Signal Distribution */}
        <div className="p-6 border border-border rounded-lg bg-card">
          <h3 className="text-lg font-semibold text-foreground mb-4">Signal Distribution</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={signalDistribution}
                cx="50%"
                cy="50%"
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}`}
              >
                {signalDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Win/Loss Distribution */}
        <div className="p-6 border border-border rounded-lg bg-card">
          <h3 className="text-lg font-semibold text-foreground mb-4">Win/Loss Distribution</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={winLossData}
                cx="50%"
                cy="50%"
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}`}
              >
                {winLossData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Signals */}
      <div className="p-6 border border-border rounded-lg bg-card">
        <h3 className="text-lg font-semibold text-foreground mb-4">Recent Signals</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={recentSignals}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="time" stroke="hsl(var(--muted-foreground))" />
            <YAxis stroke="hsl(var(--muted-foreground))" />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: 'hsl(var(--card))', 
                border: '1px solid hsl(var(--border))',
                borderRadius: '6px'
              }}
            />
            <Bar dataKey="price" fill="hsl(var(--primary))" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recent Trades Table */}
      <div className="p-6 border border-border rounded-lg bg-card">
        <h3 className="text-lg font-semibold text-foreground mb-4">Recent Trades</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left p-2 text-muted-foreground">ID</th>
                <th className="text-left p-2 text-muted-foreground">Direction</th>
                <th className="text-left p-2 text-muted-foreground">Entry Price</th>
                <th className="text-left p-2 text-muted-foreground">Exit Price</th>
                <th className="text-left p-2 text-muted-foreground">P&L</th>
                <th className="text-left p-2 text-muted-foreground">Status</th>
              </tr>
            </thead>
            <tbody>
              {trades.slice(-10).reverse().map((trade) => (
                <tr key={trade.id} className="border-b border-border">
                  <td className="p-2 text-foreground">{trade.id}</td>
                  <td className="p-2">
                    <span className={`px-2 py-1 rounded text-xs ${
                      trade.signal === 'LONG' 
                        ? 'bg-success/10 text-success' 
                        : 'bg-destructive/10 text-destructive'
                    }`}>
                      {trade.signal}
                    </span>
                  </td>
                  <td className="p-2 text-foreground">${trade.entry_price.toFixed(6)}</td>
                  <td className="p-2 text-foreground">
                    {trade.exit_price ? `$${trade.exit_price.toFixed(6)}` : '-'}
                  </td>
                  <td className={`p-2 ${
                    trade.pnl > 0 ? 'text-success' : trade.pnl < 0 ? 'text-destructive' : 'text-muted-foreground'
                  }`}>
                    ${trade.pnl.toFixed(2)}
                  </td>
                  <td className="p-2">
                    <span className={`px-2 py-1 rounded text-xs ${
                      trade.status === 'open'
                        ? 'bg-warning/10 text-warning'
                        : trade.status.includes('profit') || trade.pnl > 0
                        ? 'bg-success/10 text-success'
                        : 'bg-destructive/10 text-destructive'
                    }`}>
                      {trade.status.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsSection;