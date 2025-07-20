import React, { useState, useEffect } from 'react';
import { api } from '../lib/api';
import TraderCard from './TraderCard';
import AnalyticsSection from './AnalyticsSection';
import { Plus, AlertCircle, Activity } from 'lucide-react';

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

const TradingDashboard: React.FC = () => {
  const [traders, setTraders] = useState<TraderSummary[]>([]);
  const [selectedTrader, setSelectedTrader] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTraders = async () => {
    try {
      setError(null);
      const response = await api.listTraders();
      
      if (response.traders && response.traders.length > 0) {
        // Get summary for each trader
        const traderSummaries = await Promise.all(
          response.traders.map(async (traderId: string) => {
            try {
              return await api.getTraderSummary(traderId);
            } catch (err) {
              console.error(`Failed to load trader ${traderId}:`, err);
              return null;
            }
          })
        );
        
        setTraders(traderSummaries.filter(Boolean) as TraderSummary[]);
        
        // Auto-select first trader if none selected
        if (!selectedTrader && traderSummaries.length > 0 && traderSummaries[0]) {
          setSelectedTrader(traderSummaries[0].trader_id);
        }
      } else {
        setTraders([]);
      }
    } catch (err) {
      console.error('Failed to load traders:', err);
      setError('Failed to load traders. Please check if the backend is running.');
    }
  };

  const createTrader = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.createTrader();
      await loadTraders();
      setSelectedTrader(response.trader_id);
    } catch (err) {
      console.error('Failed to create trader:', err);
      setError('Failed to create trader. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const deleteTrader = async (traderId: string) => {
    try {
      await api.deleteTrader(traderId);
      setTraders(prev => prev.filter(t => t.trader_id !== traderId));
      if (selectedTrader === traderId) {
        setSelectedTrader(traders.length > 1 ? traders[0].trader_id : null);
      }
    } catch (err) {
      console.error('Failed to delete trader:', err);
      setError('Failed to delete trader');
    }
  };

  useEffect(() => {
    loadTraders();
    
    // Auto-refresh every 3 seconds
    const interval = setInterval(loadTraders, 3000);
    return () => clearInterval(interval);
  }, []);

  const selectedTraderData = traders.find(t => t.trader_id === selectedTrader);

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold text-foreground">Enhanced Trading Dashboard</h1>
          </div>
          <button
            onClick={createTrader}
            disabled={loading}
            className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg hover:bg-primary/90 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            {loading ? 'Creating...' : 'Create Trader'}
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="flex items-center gap-2 bg-destructive/10 text-destructive p-3 rounded-lg">
            <AlertCircle className="h-4 w-4" />
            {error}
          </div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Traders List */}
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-foreground">Active Traders ({traders.length})</h2>
            {traders.length === 0 ? (
              <div className="text-center p-8 border border-border rounded-lg">
                <p className="text-muted-foreground">No traders created yet</p>
                <button
                  onClick={createTrader}
                  className="mt-4 bg-primary text-primary-foreground px-4 py-2 rounded-lg hover:bg-primary/90"
                >
                  Create Your First Trader
                </button>
              </div>
            ) : (
              traders.map((trader) => (
                <TraderCard
                  key={trader.trader_id}
                  trader={trader}
                  isSelected={selectedTrader === trader.trader_id}
                  onSelect={() => setSelectedTrader(trader.trader_id)}
                  onDelete={() => deleteTrader(trader.trader_id)}
                  onRefresh={loadTraders}
                />
              ))
            )}
          </div>

          {/* Analytics Section */}
          <div className="lg:col-span-2">
            {selectedTraderData ? (
              <AnalyticsSection trader={selectedTraderData} />
            ) : (
              <div className="text-center p-12 border border-border rounded-lg">
                <p className="text-muted-foreground">Select a trader to view analytics</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradingDashboard;