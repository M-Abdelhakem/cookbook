import streamlit as st
import pandas as pd
import json
import time
import asyncio
from datetime import datetime, timedelta

from tools.auto_trader.auto_trader import AutoTrader

# Initialize session state
if 'auto_trader' not in st.session_state:
    st.session_state.auto_trader = None
    
if 'auto_trader_settings' not in st.session_state:
    st.session_state.auto_trader_settings = {
        'interval_minutes': 5,
        'max_investment': 100000,
        'max_trading_count': 3,
        'target_coins': ["BTC", "ETH", "XRP", "SOL", "ADA"],
        'risk_level': "Balanced",
        'model_options': "gpt-4o-mini"
    }

def show_page():
    st.title("🤖 Auto Trading Agent")
    
    # Move agent start/stop/restart buttons to the top
    control_col1, control_col2, control_col3 = st.columns(3)
    
    with control_col1:
        if st.button("Start Agent", use_container_width=True, type="primary", 
                    disabled=(st.session_state.auto_trader is not None and st.session_state.auto_trader.is_running)):
            
            if not st.session_state.get('upbit_access_key', '') or not st.session_state.get('upbit_secret_key', ''):
                st.error("Upbit API keys are not set. Please set them in the API Settings tab.")
            elif not st.session_state.get('openai_key', ''):
                st.error("OpenAI API key is not set. Please set it in the API Settings tab.")
            else:
                # Create or reuse agent
                if not st.session_state.auto_trader:
                    st.session_state.auto_trader = create_auto_trader()
                
                # Start agent
                success = st.session_state.auto_trader.start()
                if success:
                    st.success("Agent has been started!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to start the agent.")
    
    with control_col2:
        if st.button("Stop Agent", use_container_width=True, 
                    disabled=(st.session_state.auto_trader is None or not st.session_state.auto_trader.is_running)):
            if st.session_state.auto_trader:
                success = st.session_state.auto_trader.stop()
                if success:
                    st.success("Agent has been stopped!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to stop the agent.")
    
    with control_col3:
        if st.button("Restart Agent", use_container_width=True, 
                    disabled=(st.session_state.auto_trader is None)):
            if st.session_state.auto_trader:
                # Stop first
                if st.session_state.auto_trader.is_running:
                    st.session_state.auto_trader.stop()
                
                # Recreate and start
                st.session_state.auto_trader = create_auto_trader()
                success = st.session_state.auto_trader.start()
                
                if success:
                    st.success("Agent has been restarted!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to restart the agent.")
    
    # Main content
    # Agent status and controls
    st.header("Agent Status")
    
    if st.session_state.auto_trader:
        status_info = st.session_state.auto_trader.get_status()
        
        # Display status and timer
        status_col1, status_col2, status_col3 = st.columns(3)
        
        with status_col1:
            st.metric(
                "Current Status", 
                status_info["status"], 
                delta="Running" if status_info["is_running"] else "Stopped",
                delta_color="normal" if status_info["is_running"] else "off"
            )
        
        with status_col2:
            next_check = "Preparing..." 
            time_until = ""
            if status_info["next_check"]:
                next_check = status_info["next_check"]
                # Add "in n minutes" display
                try:
                    next_time = datetime.strptime(status_info["next_check"], "%Y-%m-%d %H:%M:%S")
                    now = datetime.now()
                    if next_time > now:
                        minutes_left = (next_time - now).total_seconds() // 60
                        time_until = f"in {int(minutes_left)} minutes"
                except:
                    pass
            st.metric("Next Analysis Time", next_check, delta=time_until if time_until else None)
        
        with status_col3:
            st.metric(
                "Daily Trade Count", 
                f"{status_info['daily_trading_count']} / {status_info['max_trading_count']}"
            )
        
        # Display progress status text
        st.text(f"Last Analysis: {status_info['last_check'] or 'None'}")
        
        # Progress bar (time remaining until next analysis)
        if status_info["is_running"] and status_info["next_check"]:
            try:
                next_time = datetime.strptime(status_info["next_check"], "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                
                if next_time > now:
                    total_seconds = status_info["interval_minutes"] * 60
                    elapsed = total_seconds - (next_time - now).total_seconds()
                    progress = min(1.0, max(0.0, elapsed / total_seconds))
                    
                    st.progress(progress)
                else:
                    st.progress(1.0)
            except:
                st.progress(0.0)
        else:
            st.progress(0.0)
    else:
        st.info("Agent has not been initialized. Please press the Start button.")
    
    # Operation settings - simplified inputs
    st.header("Operation Settings")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        interval_minutes = st.text_input(
            "Analysis Interval (minutes)", 
            value=str(st.session_state.auto_trader_settings['interval_minutes']),
            key="interval_minutes_setting"
        )
    
    with col2:
        max_trading_count = st.text_input(
            "Maximum Daily Trades", 
            value=str(st.session_state.auto_trader_settings['max_trading_count']),
            key="max_trading_count_setting"
        )
        
    with col3:
        max_investment = st.text_input(
            "Maximum Investment (KRW)", 
            value=str(st.session_state.auto_trader_settings['max_investment']),
            key="max_investment_setting"
        )
    
    # Apply settings button
    if st.button("Apply Settings", key="apply_all_settings", type="primary"):
        try:
            # Validate and convert inputs
            interval_minutes_val = int(interval_minutes)
            max_investment_val = int(max_investment)
            max_trading_count_val = int(max_trading_count)
            
            # Get risk level from sidebar
            risk_level = st.session_state.get('risk_style', 'Balanced')
            
            if st.session_state.auto_trader:
                # Update operation settings
                st.session_state.auto_trader.update_operation_settings(
                    interval_minutes=interval_minutes_val,
                    max_investment=max_investment_val,
                    max_trading_count=max_trading_count_val
                )
                
                # Update investment settings
                new_settings = {
                    'interval_minutes': interval_minutes_val,
                    'max_investment': max_investment_val,
                    'max_trading_count': max_trading_count_val,
                    'risk_level': risk_level,
                    'model_options': st.session_state.get('model_options', 'gpt-4o-mini')
                }
                
                # Save setting changes
                st.session_state.auto_trader_settings.update(new_settings)
                
                # Update agent
                restart_required = st.session_state.auto_trader.update_settings(new_settings)
                
                if restart_required and st.session_state.auto_trader.is_running:
                    st.warning("Some setting changes require agent restart. Please stop and start again.")
                else:
                    st.success("Settings have been applied!")
            else:
                # Only update settings in session state
                st.session_state.auto_trader_settings.update({
                    'interval_minutes': interval_minutes_val,
                    'max_investment': max_investment_val,
                    'max_trading_count': max_trading_count_val,
                    'risk_level': risk_level,
                    'model_options': st.session_state.get('model_options', 'gpt-4o-mini')
                })
                
                st.success("Settings have been saved. They will be applied when the agent starts.")
        except ValueError:
            st.error("Invalid input values. Please enter numbers only.")
    
    # Trade history
    st.header("Trade History")
    
    if st.session_state.auto_trader and st.session_state.auto_trader.trading_history:
        # Create dataframe
        history_data = []
        for trade in st.session_state.auto_trader.trading_history:
            history_data.append({
                "Time": trade.get("timestamp", ""),
                "Action": "Buy" if trade.get("action") == "buy" else "Sell",
                "Coin": trade.get("ticker", ""),
                "Amount/Quantity": trade.get("amount", ""),
                "Reason": trade.get("reason", "")[:50] + "..." if trade.get("reason") and len(trade.get("reason")) > 50 else trade.get("reason", "")
            })
        
        history_df = pd.DataFrame(history_data)
        st.dataframe(history_df, use_container_width=True, height=300)
    else:
        st.info("No trade history yet.")
    
    # Market information
    st.header("Market Information")
    
    market_container = st.container(height=300, border=True)
    
    with market_container:
        if st.session_state.auto_trader:
            market_info = st.session_state.auto_trader.get_market_info()
            
            if market_info:
                market_col1, market_col2, market_col3 = st.columns(3)
                cols = [market_col1, market_col2, market_col3]
                col_idx = 0
                
                for coin, info in market_info.items():
                    price = info["current_price"]
                    change_rate = info["change_rate"]
                    
                    with cols[col_idx % 3]:
                        st.metric(
                            f"{coin}", 
                            f"{int(price):,} KRW", 
                            f"{change_rate:.2f}%",
                            delta_color="normal" if change_rate >= 0 else "inverse"
                        )
                    col_idx += 1
            else:
                st.info("Unable to retrieve market information.")
        else:
            st.info("Agent has not been initialized.")
    
    # Log information
    st.header("Execution Logs")
    
    log_container = st.container(height=300, border=True)
    
    with log_container:
        if st.session_state.auto_trader and st.session_state.auto_trader.logs:
            logs = st.session_state.auto_trader.logs[-10:]  # Show only the 10 most recent logs
            
            for log in reversed(logs):
                level = log.get("level", "INFO")
                timestamp = log.get("timestamp", "")
                message = log.get("message", "")
                
                if level == "ERROR":
                    st.error(f"{timestamp}: {message}")
                elif level == "WARNING":
                    st.warning(f"{timestamp}: {message}")
                else:
                    st.info(f"{timestamp}: {message}")
        else:
            st.info("No log information available.")

def create_auto_trader():
    """Create AutoTrader object based on configuration information"""
    settings = st.session_state.auto_trader_settings
    
    trader = AutoTrader(
        access_key=st.session_state.upbit_access_key,
        secret_key=st.session_state.upbit_secret_key,
        model_options=settings['model_options'],
        interval_minutes=settings['interval_minutes'],
        max_investment=settings['max_investment'],
        max_trading_count=settings['max_trading_count']
    )
    
    # Apply additional settings
    trader.target_coins = settings['target_coins']
    trader.risk_level = settings['risk_level']
    
    return trader
    
if __name__ == "__main__":
    show_page() 