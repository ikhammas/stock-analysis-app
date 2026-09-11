def detect_navarro_200(df):
    """محرك مرن لاكتشاف نموذج Navarro 200"""
    if len(df) < 30:
        return None

    highs = df['High'].values
    lows = df['Low'].values
    
    # استخدام order أصغر لالتقاط النقاط الأساسية
    pivots = get_pivots_numpy(highs, lows, order=3)

    if len(pivots) < 5:
        return None

    # فحص آخر مجموعات من الـ Pivots لضمان عدم تفويت النموذج بسبب القمم الفرعية
    for offset in range(len(pivots) - 4):
        pts = pivots[-(5 + offset): len(pivots) - offset if offset > 0 else None]
        if len(pts) < 5:
            continue

        types = [p[2] for p in pts]
        vals = [p[1] for p in pts]

        # Navarro 200 Bullish: L-H-L-H-L
        if types == ['L', 'H', 'L', 'H', 'L']:
            X, A, B, C, D = vals
            XA = A - X
            AB = A - B
            BC = C - B
            CD = C - D
            
            if XA > 0 and AB > 0 and BC > 0 and CD > 0:
                ab_xa = AB / XA
                bc_ab = BC / AB
                
                # توسيع النطاق المرن للتطابق مع النماذج الواقعية
                if (0.35 <= ab_xa <= 0.85) and (0.75 <= bc_ab <= 1.25):
                    return "Navarro 200 شرائي (Bullish) 🟢"

        # Navarro 200 Bearish: H-L-H-L-H
        elif types == ['H', 'L', 'H', 'L', 'H']:
            X, A, B, C, D = vals
            XA = X - A
            AB = B - A
            BC = B - C
            CD = D - C
            
            if XA > 0 and AB > 0 and BC > 0 and CD > 0:
                ab_xa = AB / XA
                bc_ab = BC / AB
                
                if (0.35 <= ab_xa <= 0.85) and (0.75 <= bc_ab <= 1.25):
                    return "Navarro 200 بيعي (Bearish) 🔴"

    return None

def scan_navarro_patterns(symbols_list):
    results = []
    # إضافة إطار الساعتين (2h / 120m) وتوسيع فترات المسح
    tf_scan_config = {
        "30 دقيقة": {"interval": "30m", "period": "1mo"},
        "60 دقيقة": {"interval": "60m", "period": "2mo"},
        "ساعتان (120m)": {"interval": "60m", "period": "3mo", "resample": "2h"},
        "180 دقيقة (3 ساعات)": {"interval": "60m", "period": "3mo", "resample": "3h"},
        "يومي (Daily)": {"interval": "1d", "period": "6mo"}
    }
    
    for sym in symbols_list:
        try:
            tk = yf.Ticker(sym)
            for tf_name, cfg in tf_scan_config.items():
                data = tk.history(period=cfg["period"], interval=cfg["interval"])
                if not data.empty and "resample" in cfg:
                    data = data.resample(cfg["resample"], origin='start').agg({
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
