import numpy as np
import pandas as pd
import yfinance as yf

def get_pivots_numpy(highs, lows, order=3):
    pivots = []
    n = len(highs)
    for i in range(order, n - order):
        if all(highs[i] >= highs[i-j] for j in range(1, order+1)) and all(highs[i] >= highs[i+j] for j in range(1, order+1)):
            pivots.append((i, highs[i], 'H'))
        elif all(lows[i] <= lows[i-j] for j in range(1, order+1)) and all(lows[i] <= lows[i+j] for j in range(1, order+1)):
            pivots.append((i, lows[i], 'L'))
    return pivots

def detect_navarro_200(df):
    if df is None or len(df) < 20:
        return None

    highs = df['High'].values
    lows = df['Low'].values
    pivots = get_pivots_numpy(highs, lows, order=3)

    if len(pivots) < 5:
        return None

    # فحص مرن لأحدث مجموعات Pivots
    max_checks = min(5, len(pivots) - 4)
    for offset in range(max_checks):
        end_idx = len(pivots) - offset
        start_idx = end_idx - 5
        pts = pivots[start_idx:end_idx]
        
        types = [p[2] for p in pts]
        vals = [p[1] for p in pts]

        # Bullish Navarro 200: L-H-L-H-L
        if types == ['L', 'H', 'L', 'H', 'L']:
            X, A, B, C, D = vals
            XA, AB, BC, CD = A - X, A - B, C - B, C - D
            if XA > 0 and AB > 0 and BC > 0 and CD > 0:
                ab_xa = AB / XA
                bc_ab = BC / AB
                if (0.35 <= ab_xa <= 0.85) and (0.75 <= bc_ab <= 1.25):
                    return "Navarro 200 شرائي (Bullish) 🟢"

        # Bearish Navarro 200: H-L-H-L-H
        elif types == ['H', 'L', 'H', 'L', 'H']:
            X, A, B, C, D = vals
            XA, AB, BC, CD = X - A, B - A, B - C, D - C
            if XA > 0 and AB > 0 and BC > 0 and CD > 0:
                ab_xa = AB / XA
                bc_ab = BC / AB
                if (0.35 <= ab_xa <= 0.85) and (0.75 <= bc_ab <= 1.25):
                    return "Navarro 200 بيعي (Bearish) 🔴"
    return None

def scan_navarro_patterns(symbols_list):
    results = []
    # فحص إطار 60m مباشرة دون resample معقد لمنع تعليق Streamlit
    tf_scan_config = {
        "30 دقيقة": {"interval": "30m", "period": "1mo"},
        "60 دقيقة / ساعتان": {"interval": "60m", "period": "2mo"},
        "يومي (Daily)": {"interval": "1d", "period": "6mo"}
    }
    
    for sym in symbols_list:
        try:
            tk = yf.Ticker(sym)
            for tf_name, cfg in tf_scan_config.items():
                data = tk.history(period=cfg["period"], interval=cfg["interval"])
                if data.empty:
                    continue
                
                nav_type = detect_navarro_200(data)
                if nav_type:
                    results.append({
                        "السهم (Ticker)": sym,
                        "الإطار الزمني": tf_name,
                        "النمط الهارموني": nav_type,
                        "السعر الحالي": f"${data['Close'].iloc[-1]:.2f}"
                    })
        except Exception:
            continue
            
    return pd.DataFrame(results)
