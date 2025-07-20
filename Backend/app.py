from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass, asdict
import csv
import os
import threading
import uuid
import random

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend integration

# Global storage for trader instances
traders = {}
trading_threads = {}

# Initialize logging system
def initialize_logging():
    """Initialize comprehensive logging system"""
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f'logs/paper_trading_{timestamp}.log'
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("🚀 FLASK PAPER TRADING API INITIALIZED")
    
    return logger

logger = initialize_logging()

@dataclass
class TradeEntry:
    """Data structure for individual trade entries"""
    trade_id: str
    timestamp: datetime
    symbol: str
    side: str  # 'LONG' or 'SHORT'
    entry_price: float
    quantity: float
    leverage: int
    risk_pct: float
    reward_pct: float
    stop_loss: float
    take_profit: float
    current_roe: float
    drawdown: float
    max_roe: float
    trade_status: str  # 'OPEN', 'CLOSED_WIN', 'CLOSED_LOSS'
    exit_price: Optional[float] = None
    exit_timestamp: Optional[datetime] = None
    actual_return_pct: Optional[float] = None
    notes: str = ""
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        # Convert datetime objects to strings
        if isinstance(result['timestamp'], datetime):
            result['timestamp'] = result['timestamp'].isoformat()
        if result['exit_timestamp'] and isinstance(result['exit_timestamp'], datetime):
            result['exit_timestamp'] = result['exit_timestamp'].isoformat()
        return result

class EnhancedPaperTrader:
    def __init__(self, 
                 trader_id: str,
                 symbol: str = "EPICUSDT",
                 leverage: int = 10,
                 base_risk_pct: float = 5,
                 base_reward_pct: float = 15,
                 win_rate: float = 0.35,
                 target_roe: float = 100,
                 adjustment_factor: float = 1.5,
                 initial_balance: float = 1000,
                 max_trades_per_session: int = 50):
        
        self.trader_id = trader_id
        self.symbol = symbol.upper()
        self.leverage = leverage
        self.base_risk_pct = base_risk_pct
        self.base_reward_pct = base_reward_pct
        self.win_rate = win_rate
        self.target_roe = target_roe
        self.adjustment_factor = adjustment_factor
        self.initial_balance = initial_balance
        self.max_trades_per_session = max_trades_per_session
        
        # Trading state
        self.current_balance = initial_balance
        self.current_roe = 0
        self.max_roe = 0
        self.open_trades: List[TradeEntry] = []
        self.closed_trades: List[TradeEntry] = []
        self.trade_counter = 0
        self.is_running = False
        self.status = "STOPPED"
        
        # Signal generation tracking for true 50/50 distribution
        self.signal_history = []
        self.long_count = 0
        self.short_count = 0
        
        # Binance API endpoints
        self.base_url = "https://api.binance.com"
        self.futures_url = "https://fapi.binance.com"
        
        # Create logs directory and CSV file
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.csv_filename = f"logs/paper_trades_{symbol}_{trader_id}_{timestamp}.csv"
        self.create_csv_header()
        
        logger.info(f"💾 Enhanced Trader {trader_id} initialized for {symbol}")
        
    def create_csv_header(self):
        """Create CSV file with headers"""
        headers = [
            'trade_id', 'timestamp', 'symbol', 'side', 'entry_price', 'quantity',
            'leverage', 'risk_pct', 'reward_pct', 'stop_loss', 'take_profit',
            'current_roe', 'drawdown', 'max_roe', 'trade_status', 'exit_price',
            'exit_timestamp', 'actual_return_pct', 'notes'
        ]
        
        with open(self.csv_filename, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(headers)
    
    def log_trade_to_csv(self, trade: TradeEntry):
        """Log trade entry to CSV file"""
        with open(self.csv_filename, 'a', newline='') as file:
            writer = csv.writer(file)
            trade_dict = asdict(trade)
            writer.writerow(trade_dict.values())
    
    def get_current_price(self) -> Optional[float]:
        """Fetch current price from Binance API"""
        try:
            url = f"{self.futures_url}/fapi/v1/ticker/price"
            params = {"symbol": self.symbol}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return float(data['price'])
            else:
                logger.error(f"Error fetching price: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Exception fetching price: {e}")
            return None
    
    def calculate_drawdown(self) -> float:
        """Calculate current drawdown percentage"""
        if self.max_roe <= 0:
            return 0
        return max(0, (self.max_roe - self.current_roe) / (100 + self.max_roe) * 100)
    
    def generate_balanced_signal(self) -> str:
        """
        Generate truly balanced 50/50 LONG/SHORT signals with adaptive balancing
        """
        total_signals = len(self.signal_history)
        
        # For first few trades, use pure random
        if total_signals < 10:
            signal = random.choice(['LONG', 'SHORT'])
        else:
            # Calculate current imbalance
            long_ratio = self.long_count / total_signals
            short_ratio = self.short_count / total_signals
            
            # If there's significant imbalance (>60%), force balance
            if long_ratio > 0.60:
                signal = 'SHORT'
            elif short_ratio > 0.60:
                signal = 'LONG'
            else:
                # Use weighted random to gradually balance
                long_weight = 1 - long_ratio  # Lower weight if already high ratio
                short_weight = 1 - short_ratio
                
                total_weight = long_weight + short_weight
                rand_val = random.random()
                
                if rand_val < (long_weight / total_weight):
                    signal = 'LONG'
                else:
                    signal = 'SHORT'
        
        # Update counters
        self.signal_history.append(signal)
        if signal == 'LONG':
            self.long_count += 1
        else:
            self.short_count += 1
        
        # Log signal statistics
        if len(self.signal_history) > 0:
            current_long_ratio = self.long_count / len(self.signal_history)
            logger.info(f"🎯 Signal: {signal} | LONG Ratio: {current_long_ratio:.2%}")
        
        return signal
    
    def calculate_adaptive_risk_reward(self, win_rate: float) -> Tuple[float, float]:
        """
        Enhanced adaptive risk-reward calculation based on win rate and remaining ROE target
        """
        remaining_roe_needed = max(0, self.target_roe - self.current_roe)
        trades_remaining = max(1, self.max_trades_per_session - len(self.closed_trades))
        
        # Base adjustments based on win rate
        if len(self.closed_trades) < 3:  # Not enough data, use base values
            risk_pct = self.base_risk_pct
            reward_pct = self.base_reward_pct
        else:
            # If win rate is decreasing (below 50%), increase risk/reward ratio
            if win_rate < 0.5:
                # Lower win rate = higher risk/reward ratio needed
                win_rate_deficit = (0.5 - win_rate) * 100  # Convert to percentage points
                adjustment_multiplier = 1 + (win_rate_deficit * self.adjustment_factor / 100)
                
                # Increase reward more aggressively when win rate is low
                reward_pct = self.base_reward_pct * adjustment_multiplier
                # Slightly increase risk too, but less aggressively
                risk_pct = min(self.base_risk_pct * (1 + win_rate_deficit / 300), 12)
            else:
                # Higher win rate = can reduce risk/reward ratio
                win_rate_surplus = (win_rate - 0.5) * 100
                reduction_factor = max(0.7, 1 - (win_rate_surplus * 0.01))  # Max 30% reduction
                
                reward_pct = self.base_reward_pct * reduction_factor
                risk_pct = self.base_risk_pct * reduction_factor
        
        # Urgency factor based on remaining ROE needed vs trades remaining
        if remaining_roe_needed > 0 and trades_remaining > 0:
            roe_per_trade_needed = remaining_roe_needed / trades_remaining
            
            # If we need high ROE per trade, increase reward target
            if roe_per_trade_needed > 2:  # Need more than 2% ROE per trade
                urgency_multiplier = min(2.5, roe_per_trade_needed / 2)
                reward_pct *= urgency_multiplier
                risk_pct = min(risk_pct * 1.2, 15)  # Slightly increase risk too
        
        # Final caps
        risk_pct = max(2, min(risk_pct, 15))    # 2-15% risk range
        reward_pct = max(8, min(reward_pct, 50))  # 8-50% reward range
        
        # Ensure reward is always higher than risk for positive expectancy
        if reward_pct < risk_pct * 1.5:
            reward_pct = risk_pct * 2
        
        logger.info(f"📊 Risk: {risk_pct:.1f}% | Reward: {reward_pct:.1f}% | Win Rate: {win_rate:.1%}")
        
        return round(risk_pct, 2), round(reward_pct, 2)
    
    
    def calculate_optimal_position_size(self, risk_pct: float, entry_price: float, stop_loss: float) -> float:
        """Calculate optimal position size with enhanced risk management"""
        # Maximum risk amount per trade
        risk_amount = self.current_balance * (risk_pct / 100)
        
        # Price difference for stop loss
        price_diff = abs(entry_price - stop_loss)
        
        if price_diff == 0:
            return 0
        
        # Position size calculation
        stop_loss_pct = price_diff / entry_price
        position_value = risk_amount / stop_loss_pct
        quantity = position_value / entry_price
        
        # Add safety factor - never risk more than calculated
        safety_factor = 0.95  # 5% safety margin
        quantity *= safety_factor
        
        return round(quantity, 8)
    
    def place_enhanced_trade(self, side: str) -> Optional[TradeEntry]:
        """Place an enhanced paper trade with adaptive parameters"""
        current_price = self.get_current_price()
        if not current_price:
            logger.error("Cannot place trade - no current price")
            return None
        
        # Replace this line:
        drawdown = self.calculate_drawdown()
        risk_pct, reward_pct = self.calculate_adaptive_risk_reward(drawdown)

        # With this:
        if len(self.closed_trades) >= 3:
            winning_trades = sum(1 for trade in self.closed_trades if trade.actual_return_pct > 0)
            current_win_rate = winning_trades / len(self.closed_trades)
        else:
            current_win_rate = 0.5
            
        risk_pct, reward_pct = self.calculate_adaptive_risk_reward(current_win_rate)
        
        self.trade_counter += 1
        trade_id = f"PT_{self.symbol}_{self.trade_counter:04d}"
        
        # Enhanced stop loss and take profit calculation
        if side == "LONG":
            # For long positions
            stop_loss_distance = risk_pct / 100 / self.leverage
            take_profit_distance = reward_pct / 100 / self.leverage
            
            stop_loss = current_price * (1 - stop_loss_distance)
            take_profit = current_price * (1 + take_profit_distance)
        else:  # SHORT
            # For short positions
            stop_loss_distance = risk_pct / 100 / self.leverage
            take_profit_distance = reward_pct / 100 / self.leverage
            
            stop_loss = current_price * (1 + stop_loss_distance)
            take_profit = current_price * (1 - take_profit_distance)
        
        quantity = self.calculate_optimal_position_size(risk_pct, current_price, stop_loss)
        
        if quantity <= 0:
            logger.error("Invalid quantity calculated")
            return None
        
        trade = TradeEntry(
        trade_id=trade_id,
        timestamp=datetime.now(),
        symbol=self.symbol,
        side=side,
        entry_price=current_price,
        quantity=quantity,
        leverage=self.leverage,
        risk_pct=risk_pct,
        reward_pct=reward_pct,
        stop_loss=stop_loss,
        take_profit=take_profit,
        current_roe=self.current_roe,
        drawdown=self.calculate_drawdown(),  # Changed this line
        max_roe=self.max_roe,
        trade_status="OPEN",
        notes=f"🎯 Balanced Signal: {side} | R/R: {risk_pct:.1f}%/{reward_pct:.1f}% | WR: {current_win_rate:.1%}"  # Added win rate to notes
    )
        
        self.open_trades.append(trade)
        self.log_trade_to_csv(trade)
        
        logger.info(f"📈 ENHANCED TRADE: {trade_id} - {side} at ${current_price:.6f} | SL: ${stop_loss:.6f} | TP: ${take_profit:.6f}")
        
        return trade
    
    def check_trade_exits(self):
        """Check if any open trades should be closed"""
        current_price = self.get_current_price()
        if not current_price:
            return
        
        trades_to_close = []
        
        for trade in self.open_trades:
            should_close = False
            exit_reason = ""
            
            if trade.side == "LONG":
                if current_price <= trade.stop_loss:
                    should_close = True
                    exit_reason = "Stop Loss Hit"
                elif current_price >= trade.take_profit:
                    should_close = True
                    exit_reason = "Take Profit Hit"
            else:  # SHORT
                if current_price >= trade.stop_loss:
                    should_close = True
                    exit_reason = "Stop Loss Hit"
                elif current_price <= trade.take_profit:
                    should_close = True
                    exit_reason = "Take Profit Hit"
            
            if should_close:
                self.close_enhanced_trade(trade, current_price, exit_reason)
                trades_to_close.append(trade)
        
        # Remove closed trades
        for trade in trades_to_close:
            self.open_trades.remove(trade)
    
    def close_enhanced_trade(self, trade: TradeEntry, exit_price: float, reason: str):
        """Close a trade with enhanced return calculation"""
        trade.exit_price = exit_price
        trade.exit_timestamp = datetime.now()
        
        # Calculate price change percentage
        if trade.side == "LONG":
            price_change_pct = (exit_price - trade.entry_price) / trade.entry_price * 100
        else:  # SHORT
            price_change_pct = (trade.entry_price - exit_price) / trade.entry_price * 100
        
        # Apply leverage
        leveraged_return_pct = price_change_pct * self.leverage
        trade.actual_return_pct = leveraged_return_pct
        
        # Update balance and ROE
        old_balance = self.current_balance
        self.current_balance = self.current_balance * (1 + leveraged_return_pct / 100)
        self.current_roe = (self.current_balance - self.initial_balance) / self.initial_balance * 100
        
        # Update max ROE
        if self.current_roe > self.max_roe:
            self.max_roe = self.current_roe
        
        # Determine trade outcome
        if leveraged_return_pct > 0:
            trade.trade_status = "CLOSED_WIN"
            outcome_emoji = "✅"
        else:
            trade.trade_status = "CLOSED_LOSS"
            outcome_emoji = "❌"
        
        trade.notes = f"🎯 {trade.side} | {reason} | {outcome_emoji} {leveraged_return_pct:.2f}%"
        
        self.closed_trades.append(trade)
        self.log_trade_to_csv(trade)
        
        logger.info(f"🔒 TRADE CLOSED: {trade.trade_id} - {reason} - {outcome_emoji} {leveraged_return_pct:.2f}% | Balance: ${self.current_balance:.2f} | ROE: {self.current_roe:.2f}%")
    
    def get_enhanced_summary(self) -> Dict:
        """Get enhanced portfolio summary with additional metrics"""
        total_trades = len(self.closed_trades)
        winning_trades = len([t for t in self.closed_trades if t.trade_status == "CLOSED_WIN"])
        
        # Calculate signal balance
        long_signals = self.long_count
        short_signals = self.short_count
        total_signals = len(self.signal_history)
        
        # Calculate average returns
        if self.closed_trades:
            avg_win = np.mean([t.actual_return_pct for t in self.closed_trades if t.trade_status == "CLOSED_WIN"]) if winning_trades > 0 else 0
            avg_loss = np.mean([t.actual_return_pct for t in self.closed_trades if t.trade_status == "CLOSED_LOSS"]) if (total_trades - winning_trades) > 0 else 0
        else:
            avg_win = 0
            avg_loss = 0
        
        return {
            "trader_id": self.trader_id,
            "symbol": self.symbol,
            "current_balance": round(self.current_balance, 2),
            "initial_balance": self.initial_balance,
            "current_roe": round(self.current_roe, 2),
            "max_roe": round(self.max_roe, 2),
            "drawdown": round(self.calculate_drawdown(), 2),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate": round(winning_trades / total_trades, 3) if total_trades > 0 else 0,
            "open_trades": len(self.open_trades),
            "target_roe": self.target_roe,
            "target_achieved": self.current_roe >= self.target_roe,
            "progress_pct": round(min(100, self.current_roe / self.target_roe * 100), 1),
            "status": self.status,
            "is_running": self.is_running,
            "leverage": self.leverage,
            "signal_balance": {
                "long_count": long_signals,
                "short_count": short_signals,
                "total_signals": total_signals,
                "long_ratio": round(long_signals / total_signals, 3) if total_signals > 0 else 0,
                "short_ratio": round(short_signals / total_signals, 3) if total_signals > 0 else 0,
                "is_balanced": abs(long_signals - short_signals) <= max(2, total_signals * 0.1) if total_signals > 0 else True
            },
            "performance_metrics": {
                "avg_win_pct": round(avg_win, 2),
                "avg_loss_pct": round(avg_loss, 2),
                "profit_factor": round(abs(avg_win / avg_loss), 2) if avg_loss != 0 else 0,
                "trades_remaining": max(0, self.max_trades_per_session - total_trades)
            }
        }
    
    def start_enhanced_trading(self, max_trades: int = 50, check_interval: int = 15):
        """Start the enhanced paper trading bot"""
        self.is_running = True
        self.status = "RUNNING"
        self.max_trades_per_session = max_trades
        
        logger.info(f"🚀 Starting Enhanced Paper Trading Bot {self.trader_id}")
        logger.info(f"🎯 Target: {self.target_roe}% ROE in max {max_trades} trades")
        
        try:
            while (self.is_running and 
                   len(self.closed_trades) < max_trades and 
                   self.current_roe < self.target_roe):
                
                # Check for trade exits first
                self.check_trade_exits()
                
                # Place new trades if we have capacity (max 2 open trades)
                if len(self.open_trades) < 2:
                    # Generate balanced signal
                    signal = self.generate_balanced_signal()
                    
                    # Execute trade with higher probability for faster results
                    if np.random.random() < 0.3:  # 30% execution probability
                        trade = self.place_enhanced_trade(signal)
                        
                        if trade:
                            logger.info(f"🎯 New trade placed: {signal}")
                
                # Check if target achieved
                if self.current_roe >= self.target_roe:
                    logger.info(f"🎉 TARGET ACHIEVED! ROE: {self.current_roe:.2f}%")
                    break
                
                # Sleep between checks
                time.sleep(check_interval)
                
        except Exception as e:
            logger.error(f"Error in enhanced trading loop: {e}")
        finally:
            self.stop_trading()
    
    def stop_trading(self):
        """Stop the enhanced paper trading bot"""
        self.is_running = False
        self.status = "STOPPED"
        
        # Close any remaining open trades
        current_price = self.get_current_price()
        if current_price:
            for trade in self.open_trades[:]:
                self.close_enhanced_trade(trade, current_price, "Session Ended")
                self.open_trades.remove(trade)
        
        summary = self.get_enhanced_summary()
        logger.info(f"🛑 Enhanced Trading stopped for {self.trader_id}")
        logger.info(f"📊 Final Stats: ROE: {summary['current_roe']}% | Win Rate: {summary['win_rate']:.1%} | Trades: {summary['total_trades']}")

# Update the API routes to use the enhanced trader

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/trader/create', methods=['POST'])
def create_enhanced_trader():
    """Create a new enhanced trader instance"""
    try:
        data = request.json
        trader_id = str(uuid.uuid4())[:8]
        
        trader = EnhancedPaperTrader(
            trader_id=trader_id,
            symbol=data.get('symbol', 'EPICUSDT'),
            leverage=data.get('leverage', 10),
            base_risk_pct=data.get('base_risk_pct', 5),
            base_reward_pct=data.get('base_reward_pct', 15),
            target_roe=data.get('target_roe', 100),
            initial_balance=data.get('initial_balance', 1000),
            adjustment_factor=data.get('adjustment_factor', 1.5),
            max_trades_per_session=data.get('max_trades', 50)
        )
        
        traders[trader_id] = trader
        
        return jsonify({
            "success": True,
            "trader_id": trader_id,
            "message": "Enhanced trader created successfully",
            "summary": trader.get_enhanced_summary()
        })
        
    except Exception as e:
        logger.error(f"Error creating enhanced trader: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trader/<trader_id>/start', methods=['POST'])
def start_enhanced_trader(trader_id):
    """Start enhanced trading for a specific trader"""
    try:
        if trader_id not in traders:
            return jsonify({"success": False, "error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        
        if trader.is_running:
            return jsonify({"success": False, "error": "Trader is already running"})
        
        data = request.json or {}
        max_trades = data.get('max_trades', 50)
        check_interval = data.get('check_interval', 15)
        
        # Start enhanced trading in a separate thread
        thread = threading.Thread(
            target=trader.start_enhanced_trading,
            args=(max_trades, check_interval),
            daemon=True
        )
        thread.start()
        trading_threads[trader_id] = thread
        
        return jsonify({
            "success": True,
            "message": "Enhanced trading started",
            "summary": trader.get_enhanced_summary()
        })
        
    except Exception as e:
        logger.error(f"Error starting enhanced trader: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trader/<trader_id>/stop', methods=['POST'])
def stop_enhanced_trader(trader_id):
    """Stop enhanced trading for a specific trader"""
    try:
        if trader_id not in traders:
            return jsonify({"success": False, "error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        trader.stop_trading()
        
        return jsonify({
            "success": True,
            "message": "Enhanced trading stopped",
            "summary": trader.get_enhanced_summary()
        })
        
    except Exception as e:
        logger.error(f"Error stopping enhanced trader: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trader/<trader_id>/summary', methods=['GET'])
def get_enhanced_trader_summary(trader_id):
    """Get enhanced portfolio summary for a specific trader"""
    try:
        if trader_id not in traders:
            return jsonify({"success": False, "error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        summary = trader.get_enhanced_summary()
        
        return jsonify({
            "success": True,
            "summary": summary
        })
        
    except Exception as e:
        logger.error(f"Error getting enhanced summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trader/<trader_id>/trades', methods=['GET'])
def get_enhanced_trader_trades(trader_id):
    """Get all trades for a specific trader"""
    try:
        if trader_id not in traders:
            return jsonify({"success": False, "error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        
        all_trades = []
        
        # Add open trades
        for trade in trader.open_trades:
            all_trades.append(trade.to_dict())
        
        # Add closed trades
        for trade in trader.closed_trades:
            all_trades.append(trade.to_dict())
        
        # Sort by timestamp
        all_trades.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return jsonify({
            "success": True,
            "trades": all_trades,
            "total_count": len(all_trades),
            "open_count": len(trader.open_trades),
            "closed_count": len(trader.closed_trades)
        })
        
    except Exception as e:
        logger.error(f"Error getting enhanced trades: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trader/<trader_id>/trade/manual', methods=['POST'])
def place_enhanced_manual_trade(trader_id):
    """Place a manual enhanced trade"""
    try:
        if trader_id not in traders:
            return jsonify({"success": False, "error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        data = request.json
        side = data.get('side', '').upper()
        
        if side not in ['LONG', 'SHORT']:
            return jsonify({"success": False, "error": "Invalid side. Use 'LONG' or 'SHORT'"}), 400
        
        trade = trader.place_enhanced_trade(side)
        
        if trade:
            return jsonify({
                "success": True,
                "message": f"Manual {side} trade placed with enhanced logic",
                "trade": trade.to_dict(),
                "summary": trader.get_enhanced_summary()
            })
        else:
            return jsonify({"success": False, "error": "Failed to place enhanced trade"})
        
    except Exception as e:
        logger.error(f"Error placing enhanced manual trade: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trader/<trader_id>/price', methods=['GET'])
def get_current_price_enhanced(trader_id):
    """Get current price for trader's symbol"""
    try:
        if trader_id not in traders:
            return jsonify({"success": False, "error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        current_price = trader.get_current_price()
        
        if current_price:
            return jsonify({
                "success": True,
                "symbol": trader.symbol,
                "price": current_price,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({"success": False, "error": "Failed to fetch price"})
        
    except Exception as e:
        logger.error(f"Error getting price: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/traders', methods=['GET'])
def list_enhanced_traders():
    """List all active enhanced traders"""
    try:
        trader_list = []
        for trader_id, trader in traders.items():
            trader_list.append(trader.get_enhanced_summary())
        
        return jsonify({
            "success": True,
            "traders": trader_list,
            "count": len(trader_list)
        })
        
    except Exception as e:
        logger.error(f"Error listing enhanced traders: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trader/<trader_id>/delete', methods=['DELETE'])
def delete_enhanced_trader(trader_id):
    """Delete an enhanced trader instance"""
    try:
        if trader_id not in traders:
            return jsonify({"success": False, "error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        trader.stop_trading()
        
        # Remove from traders and threads
        del traders[trader_id]
        if trader_id in trading_threads:
            del trading_threads[trader_id]
        
        return jsonify({
            "success": True,
            "message": f"Enhanced trader {trader_id} deleted successfully"
        })
        
    except Exception as e:
        logger.error(f"Error deleting enhanced trader: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trader/<trader_id>/signals', methods=['GET'])
def get_signal_statistics(trader_id):
    """Get signal generation statistics for a trader"""
    try:
        if trader_id not in traders:
            return jsonify({"success": False, "error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        
        return jsonify({
            "success": True,
            "signal_stats": {
                "total_signals": len(trader.signal_history),
                "long_count": trader.long_count,
                "short_count": trader.short_count,
                "long_ratio": round(trader.long_count / len(trader.signal_history), 3) if trader.signal_history else 0,
                "short_ratio": round(trader.short_count / len(trader.signal_history), 3) if trader.signal_history else 0,
                "is_balanced": abs(trader.long_count - trader.short_count) <= max(2, len(trader.signal_history) * 0.1) if trader.signal_history else True,
                "recent_signals": trader.signal_history[-10:] if len(trader.signal_history) >= 10 else trader.signal_history
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting signal statistics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trader/<trader_id>/force-balance', methods=['POST'])
def force_signal_balance(trader_id):
    """Force rebalance the signal generation for a trader"""
    try:
        if trader_id not in traders:
            return jsonify({"success": False, "error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        
        # Reset signal counters to force rebalancing
        total_signals = len(trader.signal_history)
        if total_signals > 0:
            # Calculate ideal balance
            ideal_long = total_signals // 2
            ideal_short = total_signals - ideal_long
            
            trader.long_count = ideal_long
            trader.short_count = ideal_short
            
            logger.info(f"🔄 Signal balance forced for {trader_id}: {ideal_long} LONG, {ideal_short} SHORT")
        
        return jsonify({
            "success": True,
            "message": "Signal balance has been reset",
            "new_balance": {
                "long_count": trader.long_count,
                "short_count": trader.short_count,
                "total_signals": len(trader.signal_history)
            }
        })
        
    except Exception as e:
        logger.error(f"Error forcing signal balance: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/trader/<trader_id>/optimize', methods=['POST'])
def optimize_trader_parameters(trader_id):
    """Optimize trader parameters based on current performance"""
    try:
        if trader_id not in traders:
            return jsonify({"success": False, "error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        
        # Get current performance
        summary = trader.get_enhanced_summary()
        
        # Optimization suggestions based on current state
        suggestions = []
        
        if summary['current_roe'] < 0:
            # If in loss, suggest reducing risk and increasing reward
            new_risk = max(2, trader.base_risk_pct * 0.8)
            new_reward = min(40, trader.base_reward_pct * 1.3)
            suggestions.append(f"Reduce risk to {new_risk:.1f}% and increase reward to {new_reward:.1f}%")
            
        elif summary['drawdown'] > 20:
            # If high drawdown, increase adjustment factor
            new_adjustment = min(2.5, trader.adjustment_factor * 1.2)
            suggestions.append(f"Increase adjustment factor to {new_adjustment:.1f} for better drawdown recovery")
            
        elif summary['win_rate'] < 0.3:
            # If low win rate, suggest different reward ratio
            new_reward = min(50, trader.base_reward_pct * 1.5)
            suggestions.append(f"Increase reward target to {new_reward:.1f}% to compensate for low win rate")
        
        if summary['progress_pct'] < 50 and summary['total_trades'] > 20:
            suggestions.append("Consider increasing leverage or position sizing for faster progress")
        
        return jsonify({
            "success": True,
            "current_performance": summary,
            "optimization_suggestions": suggestions,
            "trader_parameters": {
                "base_risk_pct": trader.base_risk_pct,
                "base_reward_pct": trader.base_reward_pct,
                "adjustment_factor": trader.adjustment_factor,
                "leverage": trader.leverage
            }
        })
        
    except Exception as e:
        logger.error(f"Error optimizing trader: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Starting Enhanced Flask Paper Trading API Server")
    logger.info("📡 Enhanced API Endpoints available:")
    logger.info("   POST /api/trader/create - Create new enhanced trader")
    logger.info("   POST /api/trader/<id>/start - Start enhanced trading")
    logger.info("   POST /api/trader/<id>/stop - Stop enhanced trading")
    logger.info("   GET  /api/trader/<id>/summary - Get enhanced portfolio summary")
    logger.info("   GET  /api/trader/<id>/trades - Get all trades")
    logger.info("   POST /api/trader/<id>/trade/manual - Place manual enhanced trade")
    logger.info("   GET  /api/trader/<id>/price - Get current price")
    logger.info("   GET  /api/trader/<id>/signals - Get signal statistics")
    logger.info("   POST /api/trader/<id>/force-balance - Force signal rebalancing")
    logger.info("   POST /api/trader/<id>/optimize - Get optimization suggestions")
    logger.info("   GET  /api/traders - List all enhanced traders")
    logger.info("   DELETE /api/trader/<id>/delete - Delete enhanced trader")
    logger.info("="*80)
    logger.info("🎯 Key Enhancements:")
    logger.info("   • True 50/50 signal generation with adaptive balancing")
    logger.info("   • Enhanced risk-reward adjustment based on drawdown")
    logger.info("   • Optimized for achieving 100% ROE in minimum trades")
    logger.info("   • Advanced position sizing and risk management")
    logger.info("   • Real-time performance tracking and optimization")
    logger.info("="*80)
    
    app.run(debug=True, host='0.0.0.0', port=5000)