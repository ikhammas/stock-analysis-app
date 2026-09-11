import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st

def get_pivots_numpy(highs, lows, order=2):
    pivots = []
    n = len(highs)
    if n < (order * 2 + 1):
        return pivots
    for i in range(order, n - order):
        if all(highs[i] >= highs[i-j] for j in range(1, order+1)) and all(highs[i] >= highs[i+j] for j in range(1, order+1)):
            pivots.append((i, highs[i], 'H'))
        elif all(lows[i] <= lows[i-j] for j in range(1, order+1)) and all(lows[i] <= lows[i+j] for j in range(1, order+1)):
            pivots.append((i, lows[i], 'L'))
    return pivots

def detect_navarro_200(df):
    try:
        if df is None or len(df) < 15:
            return None

        highs = df['High'].values
        lows = df['Low'].values
        pivots = get_pivots_numpy(highs, lows, order=2)

        if len(pivots) < 5:
            return None

        # تصفية الـ Pivots المتعاقبة لتجنب التكرار (H بعد H أو L بعد L)
        filtered_pivots = []
        for p in pivots:
            if not filtered_pivots or filtered_pivots[-1][2] != p[2]:
                filtered_pivots.append(p)

        if len(filtered_pivots) < 5:
            return None

        max_checks = min(6, len(filtered_pivots) - 4)
        for offset in range(max_checks):
            end_idx = len(filtered_pivots) - offset
            start_idx = end_idx - 5
            pts = filtered_pivots[start_idx:end_idx]
            
            types = [p[2] for p in pts]
            vals = [p[1] for p in pts]

            # Navarro 200 Bullish: L-H-L-H-L
            if types == ['L', 'H', 'L', 'H', 'L']:
                X, A, B, C, D = vals
                XA, AB, BC, CD = A - X, A - B, C - B, C - D
                if XA > 0 and AB > 0 and BC > 0 and CD > 0:
                    ab_xa = AB / XA
                    bc_ab = BC / AB
                    # توسيع مرونة النسب لتشمل نموذج NVDA الموضح في الشارت
                    if (0.30 <= ab_xa <= 0.90) and (0.70 <= bc_ab <= 1.30):
                        return "Navarro 200 شرائي (Bullish) 🟢"

            # Navarro 200 Bearish: H-L-H-L-H
            elif types == ['H', 'L', 'H', 'L', 'H']:
                X, A, B, C, D = vals
                XA, AB, BC, CD = X - A, B - A, B - C, D - C
                if XA > 0 and AB > 0 and BC > 0 and CD > 0:
                    ab_xa = AB / XA
                    bc_ab = BC / AB
                    if (0.30 <= ab_xa <= 0.90) and (0.70 <= bc_ab <= 1.30):
                        return "Navarro 200 بيعي (Bearish) 🔴"
        return None
    except Exception:
        return None

def scan_navarro_patterns(symbols_list):
    results = []
    tf_scan_config = {
        "30 دقيقة": {"interval": "30m", "period": "1mo"},
        "60 دقيقة": {"interval": "60m", "period": "2mo"},
        "ساعتان (2h)": {"interval": "60m", "period": "2mo", "resample": "2h"},
        "يومي (Daily)": {"interval": "1d", "period": "6mo"}
    }
    
    for sym in symbols_list:
        try:
            tk = yf.Ticker(sym)
            for tf_name, cfg in tf_scan_config.items():
                data = tk.history(period=cfg["period"], interval=cfg["interval"])
                if data.empty:
                    continue
                
                # تجميع البيانات لإطار الساعتين عند الحاجة
                if "resample" in cfg:
                    data = data.resample('2h').agg({
                        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
                    }).dropna()
                
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
