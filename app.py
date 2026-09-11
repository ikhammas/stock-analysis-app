import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# ضبط الواجهة
st.set_page_config(
    page_title="AlphaPulse - منصة تحليل الأسهم والجاما المتقدمة",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# استايل داكن
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FAFAFA; }
    .stMetric { background-color: #161B22; padding: 15px; border-radius: 10px; border: 1px solid #30363D; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ AlphaPulse | منصة التحليل الفني ومستويات الجاما (GEX)")
st.caption("إصدار متكامل للتحليل اللحظي واليومي، سلاسل الخيارات، ومستويات الجاما الحرجة")

# 1. الشريط الجانبي - الإعدادات والخيارات
st.sidebar.header("🔍 إعدادات السهم")
input_symbol = st.sidebar.text_input("رمز السهم (Ticker):", value="TSLA")
ticker_symbol = input_symbol.strip().upper()

# إعداد الفواصل الزمنية
timeframe_options = {
    "5 دقائق": {"interval": "5m", "period": "5d"},
    "15 دقيقة": {"interval": "15m", "period": "1mo"},
    "30 دقيقة": {"interval": "30m", "period": "1mo"},
    "60 دقيقة (ساعة)": {"interval": "60m", "period": "2mo"},
    "ساعتان (120m)": {"interval": "60m", "period": "3mo", "resample": "2h"},
    "3 ساعات (180m)": {"interval": "60m", "period": "3mo", "resample": "3h"},
    "يومي (Daily)": {"interval": "1d", "period": "6mo"},
    "أسبوعي (Weekly)": {"interval": "1wk", "period": "2y"}
}

selected_tf = st.sidebar.selectbox("الاطار الزمني:", list(timeframe_options.keys()), index=2)
tf_config = timeframe_options[selected_tf]

st.sidebar.subheader("🎛️ المؤشرات الفنية")
show_rsi = st.sidebar.checkbox("مؤشر RSI", value=True)
show_macd = st.sidebar.checkbox("مؤشر MACD", value=True)
show_bb = st.sidebar.checkbox("نطاقات بولينجر (Bollinger Bands)", value=False)
show_sma = st.sidebar.checkbox("المتوسطات المتحركة (SMA 20/50)", value=True)

if ticker_symbol:
    stock = yf.Ticker(ticker_symbol)
    try:
        hist = stock.history(period=tf_config["period"], interval=tf_config["interval"])
        
        if not hist.empty and hist.index.tz is not None:
            hist.index = hist.index.tz_convert('America/New_York')
            
        if not hist.empty and "resample" in tf_config:
            rule = tf_config["resample"]
            hist = hist.resample(rule, origin='start').agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
            
    except Exception:
        hist = pd.DataFrame()

    if not hist.empty:
        last_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else last_price
        change = ((last_price - prev_price) / prev_price) * 100

        # كروت المقاييس
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("السعر الحالي", f"${last_price:.2f}", f"{change:.2f}%")
        c2.metric("أعلى سعر بالفترة", f"${hist['High'].max():.2f}")
        c3.metric("أدنى سعر بالفترة", f"${hist['Low'].min():.2f}")
        c4.metric("حجم التداول", f"{int(hist['Volume'].iloc[-1]):,}")

        # التبويبات الرئيسية
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 التحليل الفني والمؤشرات", 
            "📊 تحليل الجاما (GEX) والخيارات", 
            "🔍 الفجوات ونقاط الارتكاز (Pivot Points)",
            "📋 التقرير والبيانات"
        ])

        # --- Tab 1: الشارت التفاعلي والمؤشرات ---
        with tab1:
            st.subheader(f"الشارت التفاعلي لسهم {ticker_symbol} ({selected_tf})")
            
            # إعداد الحسابات الفنية
            hist['SMA20'] = hist['Close'].rolling(20).mean()
            hist['SMA50'] = hist['Close'].rolling(50).mean()
            
            # RSI
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            hist['RSI'] = 100 - (100 / (1 + rs))

            # MACD
            exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
            exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
            hist['MACD'] = exp1 - exp2
            hist['Signal'] = hist['MACD'].ewm(span=9, adjust=False).mean()

            # Bollinger Bands
            hist['BB_Mid'] = hist['Close'].rolling(20).mean()
            hist['BB_Std'] = hist['Close'].rolling(20).std()
            hist['BB_Upper'] = hist['BB_Mid'] + (hist['BB_Std'] * 2)
            hist['BB_Lower'] = hist['BB_Mid'] - (hist['BB_Std'] * 2)

            # إنشاء الشارت المتعدد الأجزاء
            rows = 1
            if show_rsi: rows += 1
            if show_macd: rows += 1
            
            row_heights = [0.6] + [0.2] * (rows - 1)
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=row_heights)

            # تنسيق قيم محور السينات للأطر اللحظية
            is_intraday = 'm' in tf_config['interval']
            x_values = hist.index.strftime('%Y-%m-%d %H:%M') if is_intraday else hist.index

            fig.add_trace(go.Candlestick(
                x=x_values, open=hist['Open'], high=hist['High'],
                low=hist['Low'], close=hist['Close'], name="السعر"
            ), row=1, col=1)

            if show_sma:
                fig.add_trace(go.Scatter(x=x_values, y=hist['SMA20'], mode='lines', name='SMA 20', line=dict(color='orange', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=x_values, y=hist['SMA50'], mode='lines', name='SMA 50', line=dict(color='cyan', width=1)), row=1, col=1)

            if show_bb:
                fig.add_trace(go.Scatter(x=x_values, y=hist['BB_Upper'], mode='lines', name='Upper BB', line=dict(color='rgba(173, 216, 230, 0.5)')), row=1, col=1)
                fig.add_trace(go.Scatter(x=x_values, y=hist['BB_Lower'], mode='lines', name='Lower BB', line=dict(color='rgba(173, 216, 230, 0.5)', fill='tonexty')), row=1, col=1)

            current_row = 2
            if show_rsi:
                fig.add_trace(go.Scatter(x=x_values, y=hist['RSI'], mode='lines', name='RSI', line=dict(color='purple')), row=current_row, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=current_row, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=current_row, col=1)
                current_row += 1

            if show_macd:
                fig.add_trace(go.Scatter(x=x_values, y=hist['MACD'], mode='lines', name='MACD', line=dict(color='blue')), row=current_row, col=1)
                fig.add_trace(go.Scatter(x=x_values, y=hist['Signal'], mode='lines', name='Signal', line=dict(color='orange')), row=current_row, col=1)

            # التصحيح: ربط نوع المحور السيني داخل xaxis
            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=650)
            if is_intraday:
                fig.update_xaxes(type='category')

            st.plotly_chart(fig, use_container_width=True)

        # --- Tab 2: تحليل الخيارات والجاما (Net GEX Profile) ---
        with tab2:
            st.subheader("تحليل الجاما وصافي الاهتمام (Net GEX Profile)")
            try:
                exp_dates = stock.options
                if exp_dates:
                    selected_exp = st.selectbox("اختر تاريخ انتهاء العقد:", exp_dates, index=0)
                    opt_chain = stock.option_chain(selected_exp)
                    calls = opt_chain.calls
                    puts = opt_chain.puts

                    calls_active = calls[calls['openInterest'] > 0].copy()
                    puts_active = puts[puts['openInterest'] > 0].copy()

                    if not calls_active.empty and not puts_active.empty:
                        df_gex = pd.merge(calls_active[['strike', 'openInterest']], 
                                          puts_active[['strike', 'openInterest']], 
                                          on='strike', how='outer', suffixes=('_call', '_put')).fillna(0)
                        
                        df_gex['Net_OI'] = df_gex['openInterest_call'] - df_gex['openInterest_put']
                        
                        call_wall = calls_active.loc[calls_active['openInterest'].idxmax()]['strike']
                        put_wall = puts_active.loc[puts_active['openInterest'].idxmax()]['strike']
                        zero_gamma_strike = df_gex.iloc[(df_gex['Net_OI'].abs()).idxmin()]['strike']

                        col_a, col_b, col_c = st.columns(3)
                        col_a.warning(f"🧱 Call Wall: ${call_wall:.1f}")
                        col_b.success(f"🛡️ Put Wall: ${put_wall:.1f}")
                        col_c.info(f"⚖️ Zero Gamma Level (تقديري): ${zero_gamma_strike:.1f}")

                        lower_b = last_price * 0.75
                        upper_b = last_price * 1.25
                        df_gex_plot = df_gex[(df_gex['strike'] >= lower_b) & (df_gex['strike'] <= upper_b)]

                        fig_gex = go.Figure()
                        colors = ['#2ECC71' if val >= 0 else '#E74C3C' for val in df_gex_plot['Net_OI']]
                        fig_gex.add_trace(go.Bar(x=df_gex_plot['strike'], y=df_gex_plot['Net_OI'], marker_color=colors, name='Net Open Interest'))
                        fig_gex.add_vline(x=last_price, line_dash="dash", line_color="yellow", annotation_text="السعر الحالي")
                        
                        fig_gex.update_layout(
                            template="plotly_dark", 
                            title=f"صافي الاهتمام المفتوح Net OI لـ {ticker_symbol}",
                            height=480
                        )
                        st.plotly_chart(fig_gex, use_container_width=True)
                    else:
                        st.info("لا توجد بيانات اهتمام نشطة في هذا التاريخ.")
                else:
                    st.info("بيانات الخيارات غير متاحة.")
            except Exception:
                st.error("تعذر جلب سلاسل الخيارات للتاريخ المحدد.")

        # --- Tab 3: الفجوات السعرية ونقاط الارتكاز ---
        with tab3:
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.subheader("📌 نقاط الارتكاز اليومية (Pivot Points)")
                h = hist['High'].iloc[-1]
                l = hist['Low'].iloc[-1]
                c = hist['Close'].iloc[-1]
                
                pp = (h + l + c) / 3
                r1 = (2 * pp) - l
                s1 = (2 * pp) - h
                r2 = pp + (h - l)
                s2 = pp - (h - l)

                pivots_df = pd.DataFrame({
                    "المستوى": ["مقاومة 2 (R2)", "مقاومة 1 (R1)", "ارتكاز (Pivot Point)", "دعم 1 (S1)", "دعم 2 (S2)"],
                    "السعر": [f"${r2:.2f}", f"${r1:.2f}", f"${pp:.2f}", f"${s1:.2f}", f"${s2:.2f}"]
                })
                st.table(pivots_df)

            with col_right:
                st.subheader("🔍 الفجوات السعرية البارزة (Gaps)")
                hist['Gap_%'] = ((hist['Open'] - hist['Close'].shift(1)) / hist['Close'].shift(1)) * 100
                gaps = hist[abs(hist['Gap_%']) >= 0.8][['Open', 'High', 'Low', 'Close', 'Gap_%']]
                if not gaps.empty:
                    st.dataframe(gaps.style.format({'Gap_%': '{:.2f}%', 'Open': '${:.2f}', 'High': '${:.2f}', 'Low': '${:.2f}', 'Close': '${:.2f}'}))
                else:
                    st.info("لا توجد فجوات سعرية ملحوظة في الفترة المختارة.")

        # --- Tab 4: التقرير والبيانات ---
        with tab4:
            st.subheader("📊 ملخص المنصة وتصدير البيانات")
            
            rsi_val = hist['RSI'].dropna().iloc[-1] if 'RSI' in hist.columns and not hist['RSI'].dropna().empty else 50
            if rsi_val > 70:
                rsi_status = "تشبع شرائي (Overbought)"
            elif rsi_val < 30:
                rsi_status = "تشبع بيعي (Oversold)"
            else:
                rsi_status = "منطقة محايدة"

            st.write(f"* **حالة مؤشر RSI:** {rsi_status} ({rsi_val:.2f})")
            st.write(f"* **المتوسطات:** السعر الحالي (${last_price:.2f}) مقارنة بـ SMA 20 (${hist['SMA20'].iloc[-1]:.2f})")

            csv = hist.to_csv().encode('utf-8')
            st.download_button(
                label="📥 تحميل البيانات التاريخية (CSV)",
                data=csv,
                file_name=f"{ticker_symbol}_data_{selected_tf}.csv",
                mime="text/csv"
            )

    else:
        st.error("تعذر العثور على بيانات بهذا الإطار الزمني لهذا الرمز.")
