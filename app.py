import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# ضبط الواجهة لتناسب شاشات اللابتوب والآيباد
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

# الشريط الجانبي - تحويل الرمز تلقائياً إلى حروف كبيرة
st.sidebar.header("🔍 إعدادات السهم")
input_symbol = st.sidebar.text_input("رمز السهم (Ticker):", value="TSLA")
ticker_symbol = input_symbol.strip().upper()
period = st.sidebar.selectbox("الفترة الزمنية:", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)

if ticker_symbol:
    with st.spinner('جاري جلب البيانات...'):
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
                expirations = stock.expirations
                if expirations:
                    selected_exp = st.selectbox("اختر تاريخ انتهاء العقد:", expirations[:6])
                    opt_chain = stock.option_chain(selected_exp)
                    calls = opt_chain.calls
                    puts = opt_chain.puts

                    call_wall = calls.loc[calls['openInterest'].idxmax()]['strike'] if not calls.empty and calls['openInterest'].sum() > 0 else 0
                    put_wall = puts.loc[puts['openInterest'].idxmax()]['strike'] if not puts.empty and puts['openInterest'].sum() > 0 else 0

                    col_a, col_b = st.columns(2)
                    col_a.warning(f"🧱 Call Wall (أعلى مستوى اهتمام عقود الشراء): ${call_wall}")
                    col_b.success(f"🛡️ Put Wall (أعلى مستوى اهتمام عقود البيع): ${put_wall}")

                    fig_opt = go.Figure()
                    fig_opt.add_trace(go.Bar(x=calls['strike'], y=calls['openInterest'], name='Calls Open Interest', marker_color='#2ECC71'))
                    fig_opt.add_trace(go.Bar(x=puts['strike'], y=puts['openInterest'], name='Puts Open Interest', marker_color='#E74C3C'))
                    fig_opt.update_layout(template="plotly_dark", barmode='group', title="توزيع عقود الخيارات (Calls vs Puts)", height=450)
                    st.plotly_chart(fig_opt, use_container_width=True)
                else:
                    st.info("بيانات الخيارات غير متاحة لهذا الرمز حالياً.")
            except Exception:
                st.error("تعذر جلب بيانات سلاسل الخيارات حالياً.")

        with tab3:
            st.subheader("رصد الفجوات السعرية (Gaps)")
            hist['Gap_%'] = ((hist['Open'] - hist['Close'].shift(1)) / hist['Close'].shift(1)) * 100
            gaps = hist[abs(hist['Gap_%']) >= 0.8][['Open', 'High', 'Low', 'Close', 'Gap_%']]
            if not gaps.empty:
                st.write("الفجوات السعرية البارزة (أكبر من 0.8%):")
                # تم إصلاح التنسيق لتجنب الاعتماد على مكتبات إضافية
                st.dataframe(gaps.style.format({'Gap_%': '{:.2f}%', 'Open': '${:.2f}', 'High': '${:.2f}', 'Low': '${:.2f}', 'Close': '${:.2f}'}))
            else:
                st.info("لا توجد فجوات سعرية ملحوظة في الفترة المختارة.")
    else:
        st.error("لم نتمكن من العثور على بيانات لهذا الرمز، يرجى التأكد من الرمز وإعادة المحاولة.")
