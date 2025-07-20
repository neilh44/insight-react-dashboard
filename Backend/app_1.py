from flask import Flask, jsonify, request
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import threading
import time
import random
import requests
import uuid
from datetime import datetime
import logging

# Add CORS support for frontend
from flask_cors import CORS

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@dataclass
class Trade:
    id: str
    signal: str
    entry_price: float
    quantity: float
    leverage: int
    stop_loss: float
    take_profit: float
    timestamp: str
    status: str = "open"
    exit_price: Optional[float] = None
    pnl: float = 0.0

@dataclass
class Signal:
    id: str
    direction: str
    price: float
    confidence: float
    timestamp: str
    long_ratio: float
    short_ratio: float

class EnhancedTrader:
    def __init__(self, trader_id: str):
        self.id = trader_id
        self.balance = 1000.0
        self.initial_balance = 1000.0
        self.max_balance = 1000.0
        self.trades: List[Trade] = []
        self.signals: List[Signal] = []
        self.active_trades: List[Trade] = []
        self.is_running = False
        self.thread = None
        self.last_error = None
        
        # Risk parameters
        self.base_risk = 0.05
        self.base_reward = 0.15
        self.leverage = 10
        self.symbol = "EPICUSDT"
        
        # Signal tracking
        self.long_count = 0
        self.short_count = 0
        
        logger.info(f"Created new trader: {trader_id}")
    
    def get_current_price(self) -> float:
        """Get EPICUSDT price from Binance with better error handling"""
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=EPICUSDT"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            price = float(response.json()['price'])
            logger.debug(f"Current EPICUSDT price: ${price}")
            return price
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch price from Binance: {e}")
            return 1.0  # Fallback price
        except (KeyError, ValueError) as e:
            logger.warning(f"Invalid price data from Binance: {e}")
            return 1.0
    
    def calculate_drawdown(self) -> float:
        """Calculate current drawdown percentage"""
        if self.max_balance <= self.initial_balance:
            return 0.0
        return max(0, (self.max_balance - self.balance) / self.max_balance)
    
    def get_dynamic_risk_reward(self) -> tuple:
        """Dynamic risk-reward based on drawdown"""
        drawdown = self.calculate_drawdown()
        
        if drawdown < 0.05:  # 0-5%
            return self.base_risk, self.base_reward
        elif drawdown < 0.15:  # 5-15%
            return 0.08, 0.25
        elif drawdown < 0.25:  # 15-25%
            return 0.12, 0.40
        else:  # >25%
            return 0.15, 0.50
    
    def generate_signal(self) -> Signal:
        """Generate balanced LONG/SHORT signals with intelligent rebalancing"""
        try:
            price = self.get_current_price()
            total_signals = self.long_count + self.short_count
            
            # Calculate ratios
            long_ratio = self.long_count / max(total_signals, 1)
            short_ratio = self.short_count / max(total_signals, 1)
            
            # Signal generation logic
            if total_signals < 10:
                direction = random.choice(["LONG", "SHORT"])
                confidence = 0.5
            elif long_ratio > 0.6:
                direction = "SHORT"
                confidence = 0.8
            elif short_ratio > 0.6:
                direction = "LONG"
                confidence = 0.8
            else:
                # Weighted random based on imbalance
                weights = [short_ratio, long_ratio]
                direction = random.choices(["LONG", "SHORT"], weights=weights)[0]
                confidence = 0.6
            
            # Update counters
            if direction == "LONG":
                self.long_count += 1
            else:
                self.short_count += 1
            
            signal = Signal(
                id=str(uuid.uuid4())[:8],
                direction=direction,
                price=price,
                confidence=confidence,
                timestamp=datetime.now().isoformat(),
                long_ratio=long_ratio,
                short_ratio=short_ratio
            )
            
            self.signals.append(signal)
            logger.info(f"Generated {direction} signal at ${price}")
            return signal
            
        except Exception as e:
            logger.error(f"Error generating signal: {e}")
            self.last_error = f"Signal generation error: {e}"
            raise
    
    def execute_trade(self, signal: Signal) -> Optional[Trade]:
        """Execute trade based on signal with enhanced validation and logging"""
        try:
            logger.info(f"Attempting to execute {signal.direction} trade for trader {self.id}")
            
            # Enhanced validation checks
            if len(self.active_trades) >= 2:
                logger.warning(f"Max active trades reached: {len(self.active_trades)}")
                self.last_error = "Maximum active trades (2) reached"
                return None
            
            if self.balance <= 50:  # Increased minimum balance
                logger.warning(f"Insufficient balance: ${self.balance}")
                self.last_error = f"Insufficient balance: ${self.balance}"
                return None
            
            if signal.price <= 0:
                logger.error(f"Invalid signal price: {signal.price}")
                self.last_error = f"Invalid signal price: {signal.price}"
                return None
            
            risk_pct, reward_pct = self.get_dynamic_risk_reward()
            logger.info(f"Using risk: {risk_pct*100:.1f}%, reward: {reward_pct*100:.1f}%")
            
            # Calculate position details with enhanced safety checks
            risk_amount = min(self.balance * risk_pct, self.balance * 0.15)  # Cap at 15%
            
            if signal.direction == "LONG":
                stop_loss = signal.price * (1 - risk_pct / self.leverage)
                take_profit = signal.price * (1 + reward_pct / self.leverage)
            else:
                stop_loss = signal.price * (1 + risk_pct / self.leverage)
                take_profit = signal.price * (1 - reward_pct / self.leverage)
            
            # Enhanced validation for stop loss and take profit
            if stop_loss <= 0 or take_profit <= 0:
                logger.error(f"Invalid SL/TP: SL={stop_loss}, TP={take_profit}")
                self.last_error = f"Invalid stop loss or take profit calculated"
                return None
            
            # Check if SL and TP make sense
            if signal.direction == "LONG" and stop_loss >= signal.price:
                logger.error(f"Invalid LONG SL: {stop_loss} >= {signal.price}")
                self.last_error = "Invalid stop loss for LONG position"
                return None
            
            if signal.direction == "SHORT" and stop_loss <= signal.price:
                logger.error(f"Invalid SHORT SL: {stop_loss} <= {signal.price}")
                self.last_error = "Invalid stop loss for SHORT position"
                return None
            
            stop_loss_pct = abs(signal.price - stop_loss) / signal.price
            if stop_loss_pct == 0 or stop_loss_pct > 0.2:  # Max 20% risk
                logger.error(f"Invalid stop loss percentage: {stop_loss_pct*100:.2f}%")
                self.last_error = f"Stop loss percentage out of range: {stop_loss_pct*100:.2f}%"
                return None
                
            position_value = risk_amount / stop_loss_pct
            quantity = max(0.01, position_value / signal.price * 0.9)  # Increased minimum quantity
            
            trade = Trade(
                id=str(uuid.uuid4())[:8],
                signal=signal.direction,
                entry_price=signal.price,
                quantity=quantity,
                leverage=self.leverage,
                stop_loss=stop_loss,
                take_profit=take_profit,
                timestamp=datetime.now().isoformat()
            )
            
            self.trades.append(trade)
            self.active_trades.append(trade)
            
            logger.info(f"Trade executed successfully: {trade.id} - {signal.direction} at ${signal.price}")
            logger.info(f"SL: ${stop_loss:.4f}, TP: ${take_profit:.4f}, Qty: {quantity:.4f}")
            
            self.last_error = None  # Clear any previous errors
            return trade
            
        except Exception as e:
            error_msg = f"Trade execution error: {str(e)}"
            logger.error(error_msg)
            self.last_error = error_msg
            return None
    
    def check_trade_exits(self):
        """Check if any trades should be closed with better logging"""
        try:
            current_price = self.get_current_price()
            
            for trade in self.active_trades[:]:
                should_close = False
                exit_reason = ""
                
                if trade.signal == "LONG":
                    if current_price <= trade.stop_loss:
                        should_close = True
                        exit_reason = "Stop Loss"
                    elif current_price >= trade.take_profit:
                        should_close = True
                        exit_reason = "Take Profit"
                else:  # SHORT
                    if current_price >= trade.stop_loss:
                        should_close = True
                        exit_reason = "Stop Loss"
                    elif current_price <= trade.take_profit:
                        should_close = True
                        exit_reason = "Take Profit"
                
                if should_close:
                    logger.info(f"Closing trade {trade.id} due to {exit_reason}")
                    self.close_trade(trade, current_price, exit_reason)
                    
        except Exception as e:
            logger.error(f"Error checking trade exits: {e}")
            self.last_error = f"Trade exit check error: {e}"
    
    def close_trade(self, trade: Trade, exit_price: float, reason: str):
        """Close a trade and update balance with enhanced logging"""
        try:
            trade.exit_price = exit_price
            trade.status = f"closed_{reason.lower().replace(' ', '_')}"
            
            # Calculate PnL
            if trade.signal == "LONG":
                price_change = (exit_price - trade.entry_price) / trade.entry_price
            else:
                price_change = (trade.entry_price - exit_price) / trade.entry_price
            
            trade.pnl = trade.quantity * trade.entry_price * price_change * trade.leverage
            
            # Update balance
            old_balance = self.balance
            self.balance += trade.pnl
            self.max_balance = max(self.max_balance, self.balance)
            
            logger.info(f"Trade {trade.id} closed: {reason}")
            logger.info(f"PnL: ${trade.pnl:.2f}, Balance: ${old_balance:.2f} → ${self.balance:.2f}")
            
            # Remove from active trades
            if trade in self.active_trades:
                self.active_trades.remove(trade)
                
        except Exception as e:
            logger.error(f"Error closing trade: {e}")
            self.last_error = f"Trade close error: {e}"
    
    def get_roe(self) -> float:
        """Calculate Return on Equity"""
        return ((self.balance - self.initial_balance) / self.initial_balance) * 100
    
    def trading_loop(self):
        """Main trading loop with enhanced error handling"""
        logger.info(f"Starting trading loop for trader {self.id}")
        
        while self.is_running:
            try:
                # Check existing trades
                self.check_trade_exits()
                
                # Generate new trade (20% probability, reduced for stability)
                if random.random() < 0.2 and len(self.active_trades) < 2:
                    logger.info("Attempting to generate new trade...")
                    signal = self.generate_signal()
                    trade = self.execute_trade(signal)
                    
                    if trade:
                        logger.info(f"New trade executed: {trade.id}")
                    else:
                        logger.warning("Failed to execute new trade")
                
                # Stop if target achieved or balance too low
                if self.get_roe() >= 100:
                    logger.info(f"Target ROE achieved! Current ROE: {self.get_roe():.2f}%")
                    self.is_running = False
                    break
                
                if self.balance <= 10:
                    logger.warning(f"Balance too low: ${self.balance}, stopping trading")
                    self.is_running = False
                    break
                    
                time.sleep(15)  # Wait 15 seconds
                
            except Exception as e:
                error_msg = f"Trading loop error: {str(e)}"
                logger.error(error_msg)
                self.last_error = error_msg
                time.sleep(5)
                
        logger.info(f"Trading loop stopped for trader {self.id}")
    
    def start_trading(self):
        """Start automated trading with validation"""
        try:
            if self.is_running:
                logger.warning(f"Trading already running for trader {self.id}")
                return False
                
            if self.balance <= 50:
                error_msg = f"Insufficient balance to start trading: ${self.balance}"
                logger.error(error_msg)
                self.last_error = error_msg
                return False
            
            logger.info(f"Starting automated trading for trader {self.id}")
            self.is_running = True
            self.last_error = None
            self.thread = threading.Thread(target=self.trading_loop)
            self.thread.daemon = True
            self.thread.start()
            return True
            
        except Exception as e:
            error_msg = f"Failed to start trading: {str(e)}"
            logger.error(error_msg)
            self.last_error = error_msg
            return False
    
    def stop_trading(self):
        """Stop trading and close all positions"""
        try:
            logger.info(f"Stopping trading for trader {self.id}")
            self.is_running = False
            current_price = self.get_current_price()
            
            for trade in self.active_trades[:]:
                self.close_trade(trade, current_price, "Manual Close")
                
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=5)
                
            logger.info(f"Trading stopped for trader {self.id}")
            
        except Exception as e:
            logger.error(f"Error stopping trading: {e}")
            self.last_error = f"Stop trading error: {e}"

# Global traders storage
traders: Dict[str, EnhancedTrader] = {}

# API Endpoints with enhanced error handling
@app.route('/api/trader/create', methods=['POST'])
def create_trader():
    try:
        trader_id = str(uuid.uuid4())[:8]
        traders[trader_id] = EnhancedTrader(trader_id)
        logger.info(f"Created new trader: {trader_id}")
        return jsonify({"trader_id": trader_id, "status": "created"})
    except Exception as e:
        logger.error(f"Error creating trader: {e}")
        return jsonify({"error": f"Failed to create trader: {str(e)}"}), 500

@app.route('/api/trader/<trader_id>/start', methods=['POST'])
def start_trader(trader_id):
    try:
        if trader_id not in traders:
            return jsonify({"error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        success = trader.start_trading()
        
        if success:
            return jsonify({
                "status": "started", 
                "target_roe": "100%",
                "balance": trader.balance,
                "message": "Trading started successfully"
            })
        else:
            return jsonify({
                "error": "Failed to start trading",
                "reason": trader.last_error or "Unknown error",
                "balance": trader.balance
            }), 400
            
    except Exception as e:
        logger.error(f"Error starting trader {trader_id}: {e}")
        return jsonify({"error": f"Failed to start trader: {str(e)}"}), 500

@app.route('/api/trader/<trader_id>/stop', methods=['POST'])
def stop_trader(trader_id):
    try:
        if trader_id not in traders:
            return jsonify({"error": "Trader not found"}), 404
        
        traders[trader_id].stop_trading()
        return jsonify({"status": "stopped"})
        
    except Exception as e:
        logger.error(f"Error stopping trader {trader_id}: {e}")
        return jsonify({"error": f"Failed to stop trader: {str(e)}"}), 500

@app.route('/api/trader/<trader_id>/summary', methods=['GET'])
def get_summary(trader_id):
    try:
        if trader_id not in traders:
            return jsonify({"error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        total_trades = len(trader.trades)
        winning_trades = len([t for t in trader.trades if t.pnl > 0])
        win_rate = (winning_trades / max(total_trades, 1)) * 100
        
        return jsonify({
            "trader_id": trader_id,
            "balance": round(trader.balance, 2),
            "roe": round(trader.get_roe(), 2),
            "target_roe": 100.0,
            "drawdown": round(trader.calculate_drawdown() * 100, 2),
            "total_trades": total_trades,
            "active_trades": len(trader.active_trades),
            "win_rate": round(win_rate, 1),
            "signals_generated": len(trader.signals),
            "long_signals": trader.long_count,
            "short_signals": trader.short_count,
            "signal_balance": f"{trader.long_count}/{trader.short_count}",
            "is_running": trader.is_running,
            "current_price": trader.get_current_price(),
            "last_error": trader.last_error
        })
        
    except Exception as e:
        logger.error(f"Error getting summary for {trader_id}: {e}")
        return jsonify({"error": f"Failed to get summary: {str(e)}"}), 500

@app.route('/api/trader/<trader_id>/trades', methods=['GET'])
def get_trades(trader_id):
    try:
        if trader_id not in traders:
            return jsonify({"error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        return jsonify({
            "trades": [asdict(trade) for trade in trader.trades],
            "total_trades": len(trader.trades),
            "active_trades": len(trader.active_trades)
        })
        
    except Exception as e:
        logger.error(f"Error getting trades for {trader_id}: {e}")
        return jsonify({"error": f"Failed to get trades: {str(e)}"}), 500

@app.route('/api/trader/<trader_id>/signals', methods=['GET'])
def get_signals(trader_id):
    try:
        if trader_id not in traders:
            return jsonify({"error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        return jsonify({
            "signals": [asdict(signal) for signal in trader.signals[-20:]],  # Last 20 signals
            "total_signals": len(trader.signals),
            "balance_ratio": f"L:{trader.long_count} S:{trader.short_count}"
        })
        
    except Exception as e:
        logger.error(f"Error getting signals for {trader_id}: {e}")
        return jsonify({"error": f"Failed to get signals: {str(e)}"}), 500

@app.route('/api/trader/<trader_id>/force-balance', methods=['POST'])
def force_balance(trader_id):
    try:
        if trader_id not in traders:
            return jsonify({"error": "Trader not found"}), 404
        
        trader = traders[trader_id]
        trader.long_count = 0
        trader.short_count = 0
        logger.info(f"Reset signal balance for trader {trader_id}")
        return jsonify({"status": "signals_reset", "balance": "0/0"})
        
    except Exception as e:
        logger.error(f"Error resetting balance for {trader_id}: {e}")
        return jsonify({"error": f"Failed to reset balance: {str(e)}"}), 500

@app.route('/api/traders', methods=['GET'])
def list_traders():
    try:
        return jsonify({
            "traders": list(traders.keys()),
            "total": len(traders)
        })
    except Exception as e:
        logger.error(f"Error listing traders: {e}")
        return jsonify({"error": f"Failed to list traders: {str(e)}"}), 500

@app.route('/api/trader/<trader_id>/manual-trade', methods=['POST'])
def manual_trade(trader_id):
    """Manual trade execution endpoint with enhanced validation"""
    try:
        if trader_id not in traders:
            return jsonify({"error": "Trader not found"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        direction = data.get('direction', '').upper()
        
        if direction not in ['LONG', 'SHORT']:
            return jsonify({"error": "Direction must be LONG or SHORT"}), 400
        
        trader = traders[trader_id]
        
        # Check if trader can execute trades
        if len(trader.active_trades) >= 2:
            return jsonify({"error": "Maximum active trades reached (2)"}), 400
            
        if trader.balance <= 50:
            return jsonify({"error": f"Insufficient balance: ${trader.balance}"}), 400
        
        # Create manual signal
        current_price = trader.get_current_price()
        signal = Signal(
            id=str(uuid.uuid4())[:8],
            direction=direction,
            price=current_price,
            confidence=0.9,
            timestamp=datetime.now().isoformat(),
            long_ratio=trader.long_count / max(len(trader.signals), 1),
            short_ratio=trader.short_count / max(len(trader.signals), 1)
        )
        
        trader.signals.append(signal)
        if direction == "LONG":
            trader.long_count += 1
        else:
            trader.short_count += 1
        
        # Execute trade
        trade = trader.execute_trade(signal)
        
        if trade:
            logger.info(f"Manual trade executed: {trade.id}")
            return jsonify({
                "status": "trade_executed",
                "trade_id": trade.id,
                "signal": direction,
                "entry_price": trade.entry_price,
                "stop_loss": trade.stop_loss,
                "take_profit": trade.take_profit
            })
        else:
            error_msg = trader.last_error or "Failed to execute trade - check balance or active trades"
            return jsonify({"error": error_msg}), 400
            
    except Exception as e:
        logger.error(f"Manual trade error for {trader_id}: {e}")
        return jsonify({"error": f"Manual trade failed: {str(e)}"}), 500

@app.route('/api/trader/<trader_id>/delete', methods=['DELETE'])
def delete_trader(trader_id):
    try:
        if trader_id not in traders:
            return jsonify({"error": "Trader not found"}), 404
        
        traders[trader_id].stop_trading()
        del traders[trader_id]
        logger.info(f"Deleted trader: {trader_id}")
        return jsonify({"status": "deleted"})
        
    except Exception as e:
        logger.error(f"Error deleting trader {trader_id}: {e}")
        return jsonify({"error": f"Failed to delete trader: {str(e)}"}), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "active_traders": len(traders),
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("🚀 Enhanced Paper Trading API System Starting...")
    print("📊 Target: 100% ROE through intelligent risk management")
    print("⚖️  Features: Balanced signals, dynamic scaling, drawdown recovery")
    print("🔧 Enhanced: Better error handling, logging, and validation")
    app.run(debug=True, host='0.0.0.0', port=5000)