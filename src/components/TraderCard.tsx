import React, { useState } from 'react';
import { api } from '../lib/api';
import { Play, Square, Trash2, TrendingUp, TrendingDown, DollarSign, Activity, AlertTriangle } from 'lucide-react';

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

interface TraderCardProps {
  trader: TraderSummary;
  isSelected: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onRefresh: () => void;
}

const TraderCard: React.FC<TraderCardProps> = ({ trader, isSelected, onSelect, onDelete, onRefresh }) => {
  const [loading, setLoading] = useState(false);

  const handleStartStop = async () => {
    try {
      setLoading(true);
      if (trader.is_running) {
        await api.stopTrader(trader.trader_id);
      } else {
        await api.startTrader(trader.trader_id);
      }
      onRefresh();
    } catch (err) {
      console.error('Failed to start/stop trader:', err);
    } finally {
      setLoading(false);
    }
  };

  const executeManualTrade = async (direction: 'LONG' | 'SHORT') => {
    try {
      setLoading(true);
      await api.executeManualTrade(trader.trader_id, direction);
      onRefresh();
    } catch (err) {
      console.error('Failed to execute manual trade:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = () => {
    if (trader.last_error) return 'text-destructive';
    if (trader.is_running) return 'text-success';
    return 'text-muted-foreground';
  };

  const getStatusText = () => {
    if (trader.last_error) return 'ERROR';
    if (trader.is_running) return 'RUNNING';
    return 'STOPPED';
  };

  return (
    <div 
      className={`p-4 border rounded-lg cursor-pointer transition-all ${
        isSelected 
          ? 'border-primary bg-primary/5' 
          : 'border-border hover:border-primary/50'
      }`}
      onClick={onSelect}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${trader.is_running ? 'bg-success' : 'bg-muted-foreground'}`} />
          <span className="font-medium text-sm text-foreground">
            ID: {trader.trader_id}
          </span>
        </div>
        <span className={`text-xs font-medium ${getStatusColor()}`}>
          {getStatusText()}
        </span>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 mb-1">
            <DollarSign className="h-3 w-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">Balance</span>
          </div>
          <div className="text-sm font-semibold text-foreground">
            ${trader.balance.toFixed(2)}
          </div>
        </div>

        <div className="text-center">
          <div className="flex items-center justify-center gap-1 mb-1">
            <TrendingUp className="h-3 w-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">ROE</span>
          </div>
          <div className={`text-sm font-semibold ${
            trader.roe > 0 ? 'text-success' : trader.roe < 0 ? 'text-destructive' : 'text-muted-foreground'
          }`}>
            {trader.roe.toFixed(2)}%
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-muted-foreground mb-1">
          <span>Progress to Target</span>
          <span>{((trader.roe / trader.target_roe) * 100).toFixed(1)}%</span>
        </div>
        <div className="w-full bg-secondary rounded-full h-2">
          <div 
            className="bg-primary h-2 rounded-full transition-all"
            style={{ width: `${Math.min(100, Math.max(0, (trader.roe / trader.target_roe) * 100))}%` }}
          />
        </div>
      </div>

      {/* Trade Stats */}
      <div className="grid grid-cols-3 gap-2 mb-3 text-xs">
        <div className="text-center">
          <div className="text-muted-foreground">Trades</div>
          <div className="font-medium text-foreground">{trader.total_trades}</div>
        </div>
        <div className="text-center">
          <div className="text-muted-foreground">Win Rate</div>
          <div className="font-medium text-foreground">{trader.win_rate.toFixed(1)}%</div>
        </div>
        <div className="text-center">
          <div className="text-muted-foreground">Active</div>
          <div className="font-medium text-foreground">{trader.active_trades}</div>
        </div>
      </div>

      {/* Signal Balance */}
      <div className="mb-3">
        <div className="text-xs text-muted-foreground mb-1">Signal Balance (L/S)</div>
        <div className="text-sm font-medium text-foreground">
          {trader.long_signals}/{trader.short_signals}
        </div>
      </div>

      {/* Error Display */}
      {trader.last_error && (
        <div className="mb-3 p-2 bg-destructive/10 border border-destructive/20 rounded text-xs text-destructive">
          <div className="flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" />
            <span className="font-medium">Error:</span>
          </div>
          <div className="mt-1">{trader.last_error}</div>
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2">
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleStartStop();
          }}
          disabled={loading}
          className={`flex items-center gap-1 px-2 py-1 text-xs rounded ${
            trader.is_running
              ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90'
              : 'bg-success text-white hover:bg-success/90'
          } disabled:opacity-50`}
        >
          {trader.is_running ? <Square className="h-3 w-3" /> : <Play className="h-3 w-3" />}
          {loading ? '...' : trader.is_running ? 'Stop' : 'Start'}
        </button>

        {/* Manual Trade Buttons */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            executeManualTrade('LONG');
          }}
          disabled={loading || trader.active_trades >= 2}
          className="px-2 py-1 text-xs bg-primary text-primary-foreground rounded hover:bg-primary/90 disabled:opacity-50"
        >
          Long
        </button>

        <button
          onClick={(e) => {
            e.stopPropagation();
            executeManualTrade('SHORT');
          }}
          disabled={loading || trader.active_trades >= 2}
          className="px-2 py-1 text-xs bg-secondary text-secondary-foreground rounded hover:bg-secondary/90 disabled:opacity-50"
        >
          Short
        </button>

        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="ml-auto p-1 text-destructive hover:bg-destructive/10 rounded"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
};

export default TraderCard;