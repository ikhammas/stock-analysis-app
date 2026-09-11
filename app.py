import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------
# 1. Black-Scholes Gamma Engine (Numpy Only)
# ---------------------------------------------------------
def calculate_gamma(S, K, T, r, sigma):
    """حساب الجاما رياضياً بدالة التوزيع الطبيعي باستخدام numpy مباشرة"""
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    # دالة الكثافة الاحتمالية للتوزيع الطبيعي المعياري
    pdf_d1 = (1.0 / np.sqrt(2 * np.pi)) * np.exp(-0.5 * d1**2)
    gamma = pdf_d1 / (S * sigma * np.sqrt(T))
    return gamma

def get_gex_data(ticker_symbol):
    """استخراج سلاسل الخيارات وحساب صافي الجاما ومستوى الـ Flip"""
    tk = yf.Ticker(ticker_symbol)
    try:
        expirations = tk.options
        if not expirations:
            return None, None, None
    except Exception:
        return None, None, None

    hist = tk.history(period="1d")
    if hist.empty:
        return None, None, None
    spot_price = hist['Close'].iloc[-1]
    
    target_exp = expirations[0]
    opt = tk.option_chain(target_exp)
    calls, puts = opt.calls, opt.puts

    r = 0.045
    days_to_exp = (pd.to_datetime(target_exp) - pd.Timestamp.now()).days
    T = max(days_to_exp, 1) / 365.0

    df_gex = []

    for _, row in calls.iterrows():
        K = row['strike']
        oi = row['openInterest'] if pd.notnull(row['openInterest']) else 0
        iv = row['impliedVolatility'] if pd.notnull(row['impliedVolatility']) else 0
        if oi > 0 and iv > 0:
            g = calculate_gamma(spot_price, K, T, r, iv)
            gex = g * oi * 100 * (spot_price**2) * 0.01
            df_gex.append({'strike': K, 'call_gex': gex, 'put_gex': 0})

    for _, row in puts.iterrows():
        K = row['strike']
        oi = row['openInterest'] if pd.notnull(row['openInterest']) else 0
        iv = row['impliedVolatility'] if pd.notnull(row['impliedVolatility']) else 0
        if oi > 0 and iv > 0:
            g = calculate_gamma(spot_price, K, T, r, iv)
            gex = -1 * g * oi * 100 * (spot_price**2) * 0.01
            df_gex.append({'strike': K, 'call_gex': 0, 'put_gex': gex})

    if not df_gex:
        return None, spot_price, None

    df = pd.DataFrame(df_gex).groupby('strike').sum().reset_index()
    df['net_gex'] = df['call_gex'] + df['put_gex']
    
    zero_cross = df.iloc[(df['net_gex']).abs().argsort()[:1]]
    flip_level = zero_cross['strike'].values[0] if not zero_cross.empty else spot_price

    return df, spot_price, flip_level

# ---------------------------------------------------------
# 2. Volume Profile Engine
# ---------------------------------------------------------
def calc_volume_profile(df, bins=30):
    """حساب توزيع الحجم على مستويات السعر للـ POC"""
    counts, bin_edges = np.histogram(df['Close'], bins=bins, weights=df['Volume'])
    price_bins = [(bin_edges[i] + bin_edges[i+1])/2 for i in range(len(bin_edges)-1)]
    poc_idx = np.argmax(counts)
    poc_price = price_bins[poc_idx]
    profile_df = pd.DataFrame({'price': price_bins, 'volume': counts})
    return profile_df, poc_price

# ---------------------------------------------------------
# 3. Streamlit Interface & Logic
# ---------------------------------------------------------
st.set_page_config(page_title="AlphaPulse Analytics Pro", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FAFAFA; }
    .stMetric { background-color: #161B22; padding: 15px; border-radius: 10px; border: 1px solid #30363D; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ AlphaPulse | منصة التحليل الفني وحسابات الجاما (GEX)")

# القائمة الجانبية
st.sidebar.header("🔍 إعدادات السهم والمخاطر")
symbol = st.sidebar.text_input("رمز السهم (Ticker):", value="TSLA").strip().upper()

timeframe_options = {
    "5 دقائق": {"interval": "5m", "period": "5d"},
    "15 دقيقة": {"interval": "15m", "period": "1mo"},
    "30 دقيقة": {"interval": "30m", "period": "1mo"},
    "60 دقيقة (ساعة)": {"interval": "60m", "period": "2mo"},
    "يومي (Daily)": {"interval": "1d", "period": "6mo"},
    "أسبوعي (Weekly)": {"interval": "1wk", "period": "2y"}
}

selected_tf = st.sidebar.selectbox("الاطار الزمني:", list(timeframe_options.keys()), index=4)
tf_config = timeframe_options[selected_tf]

st.sidebar.markdown("---")
st.sidebar.subheader("📐 حاسبة حجم الصفقة (Position Sizing)")
account_size = st.sidebar.number_input("حجم الحساب ($):", value=10000, step=500)
risk_pct = st.sidebar.number_input("نسبة المخاطرة (%):", value=1.0, step=0.5) / 100
entry_p = st.sidebar.number_input("سعر الدخول ($):", value=200.0)
stop_p = st.sidebar.number_input("وقف الخسارة ($):", value=190.0)

if entry_p > stop_p and entry_p > 0:
    risk_amt = account_size * risk_pct
    risk_per_share = entry_p - stop_p
    shares = int(risk_amt / risk_per_share)
    total_val = shares * entry_p
    st.sidebar.success(f"**عدد الأسهم:** {shares}\n\n**القيمة الإجمالية:** ${total_val:,.2f}\n\n**أقصى خسارة:** ${risk_amt:,.2f}")

# جلب البيانات
if symbol:
    stock = yf.Ticker(symbol)
    try:
        hist = stock.history(period=tf_config["period"], interval=tf_config["interval"])
        if not hist.empty and hist.index.tz is not None:
            hist.index = hist.index.tz_convert('America/New_York')
    except Exception:
        hist = pd.DataFrame()

    if not hist.empty:
        last_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else last_price
        change = ((last_price - prev_price) / prev_price) * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("السعر الحالي", f"${last_price:.2f}", f"{change:.2f}%")
        c2.metric("أعلى سعر بالفترة", f"${hist['High'].max():.2f}")
        c3.metric("أدنى سعر بالفترة", f"${hist['Low'].min():.2f}")
        c4.metric("حجم التداول", f"{int(hist['Volume'].iloc[-1]):,}")

        tab1, tab2 = st.tabs(["📈 التحليل الفني و Volume Profile", "📊 تحليل الجاما (GEX Profile)"])

        with tab1:
            vp_df, poc_price = calc_volume_profile(hist)
            is_intraday = 'm' in tf_config['interval']
            x_values = hist.index.strftime('%Y-%m-%d %H:%M') if is_intraday else hist.index

            fig = make_subplots(rows=1, cols=2, column_widths=[0.8, 0.2], shared_yaxes=True, horizontal_spacing=0.02)
            
            fig.add_trace(go.Candlestick(
                x=x_values, open=hist['Open'], high=hist['High'],
                low=hist['Low'], close=hist['Close'], name="السعر"
            ), row=1, col=1)
            
            fig.add_hline(y=poc_price, line_dash="dash", line_color="orange", annotation_text=f"POC: ${poc_price:.2f}", row=1, col=1)

            fig.add_trace(go.Bar(
                y=vp_df['price'], x=vp_df['volume'], orientation='h',
                marker_color='rgba(100, 149, 237, 0.5)', name="Volume Profile"
            ), row=1, col=2)

            fig.update_layout(template="plotly_dark", height=600, showlegend=False, xaxis_rangeslider_visible=False)
            if is_intraday:
                fig.update_xaxes(type='category', row=1, col=1)

            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader("تحليل Net Gamma Exposure (GEX Profile)")
            with st.spinner("جاري حساب الجاما واختراق المستويات..."):
                gex_df, spot_price, flip_level = get_gex_data(symbol)

            if gex_df is not None:
                col_a, col_b = st.columns(2)
                col_a.metric("سعر السهم الحالي (Spot):", f"${spot_price:.2f}")
                col_b.metric("مستوى GEX Flip (تغير الاتجاه):", f"${flip_level:.2f}")

                lower_b = spot_price * 0.75
                upper_b = spot_price * 1.25
                gex_plot = gex_df[(gex_df['strike'] >= lower_b) & (gex_df['strike'] <= upper_b)]

                fig_gex = go.Figure()
                colors = ['#2ECC71' if val >= 0 else '#E74C3C' for val in gex_plot['net_gex']]
                
                fig_gex.add_trace(go.Bar(
                    x=gex_plot['strike'], y=gex_plot['net_gex'],
                    marker_color=colors, name="Net GEX"
                ))
                
                fig_gex.add_vline(x=spot_price, line_dash="solid", line_color="yellow", annotation_text="Spot")
                fig_gex.add_vline(x=flip_level, line_dash="dot", line_color="cyan", annotation_text="Flip Level")

                fig_gex.update_layout(
                    template="plotly_dark",
                    title=f"توزيع صافي الجاما (Net GEX) لـ {symbol}",
                    xaxis_title="Strike Price", yaxis_title="Net GEX ($)",
                    height=500
                )
                st.plotly_chart(fig_gex, use_container_width=True)
            else:
                st.warning("تعذر استخراج بيانات الخيارات لهذا السهم أو لا توجد عقود نشطة حالياً.")
    else:
        st.error("تعذر العثور على بيانات بهذا الإطار الزمني لهذا الرمز.")
