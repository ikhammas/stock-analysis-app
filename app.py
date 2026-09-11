import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------
# 1. Black-Scholes Gamma Engine
# ---------------------------------------------------------
def calculate_gamma(S, K, T, r, sigma):
    """حساب قيمة الجاما باستخدام نموذج بلاك-شولز"""
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    return gamma

def get_gex_data(ticker_symbol):
    """استخراج سلاسل الخيارات وحساب صافي الجاما والجاما فليب"""
    tk = yf.Ticker(ticker_symbol)
    try:
        expirations = tk.expirations
        if not expirations:
            return None, None, None
    except Exception:
        return None, None, None

    spot_price = tk.history(period="1d")['Close'].iloc[-1]
    
    # اختيار أقرب تاريخ انتهاء (أو تجميع أول تاريخين)
    target_exp = expirations[0]
    opt = tk.option_chain(target_exp)
    calls, puts = opt.calls, opt.puts

    r = 0.045 # معدل الخالي من المخاطرة التقديري (4.5%)
    # حساب الأيام المتبقية للانقضاء
    days_to_exp = (pd.to_datetime(target_exp) - pd.Timestamp.now()).days
    T = max(days_to_exp, 1) / 365.0

    df_gex = []

    # معالجة عقود الكول (Positive GEX)
    for _, row in calls.iterrows():
        K = row['strike']
        oi = row['openInterest'] if pd.notnull(row['openInterest']) else 0
        iv = row['impliedVolatility'] if pd.notnull(row['impliedVolatility']) else 0
        if oi > 0 and iv > 0:
            g = calculate_gamma(spot_price, K, T, r, iv)
            gex = g * oi * 100 * (spot_price**2) * 0.01
            df_gex.append({'strike': K, 'call_gex': gex, 'put_gex': 0})

    # معالجة عقود البوت (Negative GEX)
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
    
    # تحديد مستوى Flip Level (تقريبي)
    df['cum_gex'] = df['net_gex'].cumsum()
    zero_cross = df.iloc[(df['net_gex']).abs().argsort()[:1]]
    flip_level = zero_cross['strike'].values[0] if not zero_cross.empty else spot_price

    return df, spot_price, flip_level

# ---------------------------------------------------------
# 2. Volume Profile Engine
# ---------------------------------------------------------
def calc_volume_profile(df, bins=30):
    """توزيع الحجم على مستويات السعر لحساب POC"""
    price_min = df['Low'].min()
    price_max = df['High'].max()
    counts, bin_edges = np.histogram(df['Close'], bins=bins, weights=df['Volume'])
    
    price_bins = [(bin_edges[i] + bin_edges[i+1])/2 for i in range(len(bin_edges)-1)]
    poc_idx = np.argmax(counts)
    poc_price = price_bins[poc_idx]
    
    profile_df = pd.DataFrame({'price': price_bins, 'volume': counts})
    return profile_df, poc_price

# ---------------------------------------------------------
# 3. Streamlit Interface Setup
# ---------------------------------------------------------
st.set_page_config(page_title="AlphaPulse Analytics Pro", layout="wide")
st.title("⚡ AlphaPulse — Advanced Trading Dashboard")

# القائمة الجانبية (Sidebar)
st.sidebar.header("🕹️ التحكم والمخاطر")
symbol = st.sidebar.text_input("رمز السهم (Ticker):", value="NVDA").upper()
period = st.sidebar.selectbox("الفترة الزمنية:", ["1mo", "3mo", "6mo", "1y"], index=1)

st.sidebar.markdown("---")
st.sidebar.subheader("📐 حاسبة حجم الصفقة (Position Size)")
account_size = st.sidebar.number_input("حجم الحساب ($):", value=10000, step=500)
risk_pct = st.sidebar.number_input("نسبة المخاطرة (%):", value=1.0, step=0.5) / 100
entry_p = st.sidebar.number_input("سعر الدخول ($):", value=100.0)
stop_p = st.sidebar.number_input("وقف الخسارة ($):", value=95.0)

if entry_p > stop_p and entry_p > 0:
    risk_amt = account_size * risk_pct
    risk_per_share = entry_p - stop_p
    shares = int(risk_amt / risk_per_share)
    total_val = shares * entry_p
    st.sidebar.success(f"**عدد الأسهم:** {shares}\n\n**إجمالي قيمة الصفقة:** ${total_val:,.2f}\n\n**أقصى خسارة:** ${risk_amt:,.2f}")
else:
    st.sidebar.info("أدخل سعر دخول أعلى من وقف الخسارة للحساب.")

# ---------------------------------------------------------
# Main Execution Flow
# ---------------------------------------------------------
stock = yf.Ticker(symbol)
hist = stock.history(period=period)

if hist.empty:
    st.error("لم يتم العثور على بيانات لهذا السهم. تأكد من الرمز.")
else:
    # تقسيم الشاشة إلى تبويبين
    tab1, tab2 = st.tabs(["📈 التحليل الفني وVolume Profile", "📊 تحليل الجاما (GEX) والخيارات"])

    with tab1:
        vp_df, poc_price = calc_volume_profile(hist)
        
        fig = make_subplots(rows=1, cols=2, column_widths=[0.8, 0.2], shared_yaxes=True, horizontal_spacing=0.02)
        
        # الشموع اليابانية
        fig.add_trace(go.Candlestick(
            x=hist.index, open=hist['Open'], high=hist['High'],
            low=hist['Low'], close=hist['Close'], name="السعر"
        ), row=1, col=1)
        
        # خط الـ POC
        fig.add_hline(y=poc_price, line_dash="dash", line_color="orange", 
                      annotation_text=f"POC: {poc_price:.2f}", row=1, col=1)

        # Volume Profile الجانبي
        fig.add_trace(go.Bar(
            y=vp_df['price'], x=vp_df['volume'], orientation='h',
            marker_color='rgba(100, 149, 237, 0.5)', name="Volume Profile"
        ), row=1, col=2)

        fig.update_layout(title=f"رسم السعر مع Volume Profile — {symbol}", 
                          height=600, showlegend=False, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("تحليل Net Gamma Exposure (GEX)")
        with st.spinner("جاري حساب الجاما واختراق المستويات..."):
            gex_df, spot_price, flip_level = get_gex_data(symbol)

        if gex_df is not None:
            col1, col2 = st.columns(2)
            col1.metric("سعر السهم الحالي (Spot):", f"${spot_price:.2f}")
            col2.metric("مستوى GEX Flip Tipping Point:", f"${flip_level:.2f}")

            # رسم اعمدة الجاما حسب الـ Strike
            fig_gex = go.Figure()
            colors = ['green' if val >= 0 else 'red' for val in gex_df['net_gex']]
            
            fig_gex.add_trace(go.Bar(
                x=gex_df['strike'], y=gex_df['net_gex'],
                marker_color=colors, name="Net GEX"
            ))
            
            fig_gex.add_vline(x=spot_price, line_dash="solid", line_color="blue", annotation_text="Spot")
            fig_gex.add_vline(x=flip_level, line_dash="dot", line_color="orange", annotation_text="Flip Level")

            fig_gex.update_layout(
                title=f"توزيع صافي الجاما (Net GEX Profile) — {symbol}",
                xaxis_title="Strike Price", yaxis_title="Net GEX ($)",
                height=500
            )
            st.plotly_chart(fig_gex, use_container_width=True)
        else:
            st.warning("تعذر استخراج بيانات الخيارات لهذا السهم أو لا توجد عقود نشطة حالياً.")
