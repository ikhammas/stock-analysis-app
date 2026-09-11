import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# ضبط الواجهة
st.set_page_config(
    page_title="AlphaPulse - منصة تحليل الأسهم والجاما",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# تصميم داكن احترافي
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FAFAFA; }
    .stMetric { background-color: #161B22; padding: 15px; border-radius: 10px; border: 1px solid #30363D; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ AlphaPulse | منصة تحليل الأسهم ومستويات الجاما")
st.caption("أداة تحليل مخصصة ومجانية 100% تعمل على الويب والآيباد بدون اشتراكات")

# الشريط الجانبي
st.sidebar.header("🔍 إعدادات السهم")
input_symbol = st.sidebar.text_input("رمز السهم (Ticker):", value="TSLA")
ticker_symbol = input_symbol.strip().upper()
period = st.sidebar.selectbox("الفترة الزمنية:", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)

if ticker_symbol:
    stock = yf.Ticker(ticker_symbol)
    try:
        hist = stock.history(period=period)
    except Exception:
        hist = pd.DataFrame()

    if not hist.empty:
        last_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2]
        change = ((last_price - prev_price) / prev_price) * 100

        # كروت المقاييس
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("السعر الحالي", f"${last_price:.2f}", f"{change:.2f}%")
        c2.metric("أعلى سعر بالفترة", f"${hist['High'].max():.2f}")
        c3.metric("أدنى سعر بالفترة", f"${hist['Low'].min():.2f}")
        c4.metric("حجم التداول اليومي", f"{hist['Volume'].iloc[-1]:,}")

        # التبويبات الرئيسية
        tab1, tab2, tab3 = st.tabs(["📈 التحليل الفني والشارت", "📊 عقود الخيارات ومستويات الجاما (GEX)", "🔍 الفجوات والنماذج السعرية"])

        with tab1:
            st.subheader(f"الشارت التفاعلي لسهم {ticker_symbol}")
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=hist.index,
                open=hist['Open'], high=hist['High'],
                low=hist['Low'], close=hist['Close'],
                name="السعر"
            ))
            hist['SMA20'] = hist['Close'].rolling(20).mean()
            hist['SMA50'] = hist['Close'].rolling(50).mean()
            fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA20'], mode='lines', name='SMA 20', line=dict(color='orange', width=1.5)))
            fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA50'], mode='lines', name='SMA 50', line=dict(color='cyan', width=1.5)))

            fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=550)
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            st.subheader("تحليل الاهتمام المفتوح ومستويات GEX")
            try:
                exp_dates = stock.options
                if exp_dates:
                    # اختيار تاريخ ينتهي لاحقاً أو التاريخ الأول
                    selected_exp = st.selectbox("اختر تاريخ انتهاء العقد:", exp_dates, index=0)
                    opt_chain = stock.option_chain(selected_exp)
                    calls = opt_chain.calls
                    puts = opt_chain.puts

                    # فلترة العقود التي تملك اهتمام مفتوح أكبر من صفر
                    calls_active = calls[calls['openInterest'] > 0]
                    puts_active = puts[puts['openInterest'] > 0]

                    if not calls_active.empty and not puts_active.empty:
                        call_wall = calls_active.loc[calls_active['openInterest'].idxmax()]['strike']
                        put_wall = puts_active.loc[puts_active['openInterest'].idxmax()]['strike']

                        col_a, col_b = st.columns(2)
                        col_a.warning(f"🧱 Call Wall (أعلى اهتمام عقود الشراء): ${call_wall:.1f}")
                        col_b.success(f"🛡️ Put Wall (أعلى اهتمام عقود البيع): ${put_wall:.1f}")

                        # حد عرض حول السعر الحالي
                        lower_b = last_price * 0.75
                        upper_b = last_price * 1.25
                        calls_plot = calls_active[(calls_active['strike'] >= lower_b) & (calls_active['strike'] <= upper_b)]
                        puts_plot = puts_active[(puts_active['strike'] >= lower_b) & (puts_active['strike'] <= upper_b)]

                        fig_opt = go.Figure()
                        fig_opt.add_trace(go.Bar(x=calls_plot['strike'], y=calls_plot['openInterest'], name='Calls Open Interest', marker_color='#2ECC71'))
                        fig_opt.add_trace(go.Bar(x=puts_plot['strike'], y=puts_plot['openInterest'], name='Puts Open Interest', marker_color='#E74C3C'))
                        fig_opt.update_layout(template="plotly_dark", barmode='group', title=f"توزيع عقود الخيارات لـ {ticker_symbol} (تاريخ: {selected_exp})", height=480)
                        st.plotly_chart(fig_opt, use_container_width=True)
                    else:
                        st.info("⚠️ هذا التاريخ لا يحتوي على بيانات اهتمام مفتوح (Open Interest) نشطة حالياً. يرجى اختيار تاريخ آخر من القائمة أعلاه (مثل عقود الأسبوع القادم).")
                else:
                    st.info("لا تتوفر بيانات خيارات لهذا الرمز حالياً.")
            except Exception:
                st.error("تعذر جلب بيانات الخيارات لهذا التاريخ، يرجى اختيار تاريخ آخر.")

        with tab3:
            st.subheader("رصد الفجوات السعرية (Gaps)")
            hist['Gap_%'] = ((hist['Open'] - hist['Close'].shift(1)) / hist['Close'].shift(1)) * 100
            gaps = hist[abs(hist['Gap_%']) >= 0.8][['Open', 'High', 'Low', 'Close', 'Gap_%']]
            if not gaps.empty:
                st.write("الفجوات السعرية البارزة (أكبر من 0.8%):")
                st.dataframe(gaps.style.format({'Gap_%': '{:.2f}%', 'Open': '${:.2f}', 'High': '${:.2f}', 'Low': '${:.2f}', 'Close': '${:.2f}'}))
            else:
                st.info("لا توجد فجوات سعرية ملحوظة في الفترة المختارة.")
    else:
        st.error("لم نتمكن من العثور على بيانات لهذا الرمز، يرجى التأكد من الرمز وإعادة المحاولة.")
