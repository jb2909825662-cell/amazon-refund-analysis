import streamlit as st
import pandas as pd
import plotly.express as px
from collections import Counter
import re
import json
from openai import OpenAI
import os
import datetime
import csv

# ================== 🛠️ 配置区域 ==================
SILICONFLOW_API_KEY = "sk-wmbipxzixpvwddjoisctfpsdwneznyliwoxgxbbzcdrvaiye"
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
ADMIN_PASSWORD = "dhzjb"
BASE_URL = "https://api.siliconflow.cn/v1"
LOG_FILE = "access_log.csv"

# 页面配置
st.set_page_config(page_title="Amazon 退款分析 (AI 自动翻译版)", layout="wide", page_icon="📊")

# ================== 🔥 【超强力美化 & 去标识化 CSS】 🔥 ==================
# 这里添加了图案背景和卡片式布局，让应用看起来更专业、独立
hide_streamlit_elements = """
<style>
    /* --- 1. 隐藏 Streamlit 原生元素 --- */
    header[data-testid="stHeader"],
    [data-testid="stAppToolbar"],
    [data-testid="stDecoration"],
    footer,
    [data-testid="stStatusWidget"] {
        display: none !important;
        visibility: hidden !important;
        height: 0% !important;
    }

    /* --- 2. 全局背景图案 (遮盖痕迹) --- */
    /* 给整个页面添加一个淡雅的科技几何纹理背景 */
    .stApp {
        background-color: #f0f2f5; /* 基础浅灰背景色 */
        background-image:  linear-gradient(30deg, #e6e9ef 12%, transparent 12.5%, transparent 87%, #e6e9ef 87.5%, #e6e9ef),
                           linear-gradient(150deg, #e6e9ef 12%, transparent 12.5%, transparent 87%, #e6e9ef 87.5%, #e6e9ef),
                           linear-gradient(30deg, #e6e9ef 12%, transparent 12.5%, transparent 87%, #e6e9ef 87.5%, #e6e9ef),
                           linear-gradient(150deg, #e6e9ef 12%, transparent 12.5%, transparent 87%, #e6e9ef 87.5%, #e6e9ef),
                           radial-gradient(circle at 50% 50%, #ffffff 15%, #e6e9ef 16%, transparent 17%),
                           radial-gradient(circle at 50% 50%, #ffffff 15%, #e6e9ef 16%, transparent 17%);
        background-size: 40px 40px;
        background-position: 0 0, 0 0, 20px 20px, 20px 20px, 0 0, 20px 20px;
        opacity: 1;
    }

    /* --- 3. 主体内容卡片化 --- */
    /* 将主要内容区域变成一个白色圆角卡片，突出显示 */
    .block-container {
        background-color: #ffffff;
        padding: 3rem 2rem !important; /* 增加内边距 */
        border-radius: 12px;           /* 圆角 */
        box-shadow: 0 10px 25px rgba(0,0,0,0.05); /* 柔和的阴影 */
        margin-top: 2rem !important;   /* 顶部留空 */
        max-width: 1200px;             /* 限制最大宽度，大屏更精致 */
    }
    
    /* 调整标题样式，使其更像独立应用的 Banner */
    h1 {
        color: #2c3e50;
        text-align: center;
        padding-bottom: 1rem;
        border-bottom: 2px solid #eaeaea;
        margin-bottom: 2rem;
    }
</style>
"""
st.markdown(hide_streamlit_elements, unsafe_allow_html=True)

# ================== 日志系统 ==================
def init_log_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["时间", "姓名", "部门", "操作", "文件名/备注"])

def log_action(name, dept, action, note=""):
    try:
        init_log_file()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([current_time, name, dept, action, note])
    except Exception as e:
        print(f"日志记录失败: {e}")

# ================== 辅助函数 & AI ==================
def format_bilingual(text, trans_map, mode='text'):
    text = str(text)
    cn = trans_map.get(text)
    if cn:
        return f"{text}<br>({cn})" if mode == 'html' else f"{text} ({cn})"
    return text

def translate_reasons_with_llm(unique_reasons):
    if "sk-" not in SILICONFLOW_API_KEY:
        return {}
    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=BASE_URL)
    reasons_str = json.dumps(list(unique_reasons))
    system_prompt = "你是一个专业的亚马逊跨境电商翻译助手。你的任务是将英文退款原因准确翻译为中文。"
    user_prompt = f"""
    请将以下 Amazon 退款原因列表翻译成中文。
    输入数据: {reasons_str}
    要求:
    1. 翻译要简练、专业。
    2. 必须严格返回一个 JSON 格式的字典。
    3. Key 是原始英文，Value 是中文翻译。
    4. 直接返回 JSON 字符串，不要 Markdown。
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        mapping = json.loads(content)
        return mapping
    except Exception as e:
        st.error(f"AI 翻译接口调用失败: {e}")
        return {}

@st.cache_data(show_spinner=False)
def process_data(df):
    df.columns = [c.strip() for c in df.columns]
    if 'reason' not in df.columns:
        return None, None, None, None, "CSV 文件中缺少 'reason' 列"

    unique_reasons = [str(r) for r in df['reason'].dropna().unique()]
    with st.spinner(f"正在连接 AI 模型 ({MODEL_NAME}) 智能翻译 {len(unique_reasons)} 条原因..."):
        trans_map = translate_reasons_with_llm(unique_reasons)
    
    reason_counts = df['reason'].value_counts().reset_index()
    reason_counts.columns = ['原因_en', '数量']
    reason_counts['原因_display'] = reason_counts['原因_en'].apply(lambda x: format_bilingual(x, trans_map, 'text'))
    reason_counts['原因_html'] = reason_counts['原因_en'].apply(lambda x: format_bilingual(x, trans_map, 'html'))
    reason_counts['占比'] = (reason_counts['数量'] / len(df) * 100).round(2)
    reason_counts = reason_counts.sort_values('数量', ascending=True)
    
    sku_counts = df['sku'].value_counts().reset_index().head(10)
    sku_counts.columns = ['SKU', '退款数量']
    sku_counts = sku_counts.sort_values('退款数量', ascending=True)
    
    keywords = []
    if 'customer-comments' in df.columns:
        stop_words = {'the','to','and','a','of','in','is','it','was','for','on','my','i','with','not','returned','item','amazon','unit','nan','this','that','but','have'}
        text = " ".join(df['customer-comments'].dropna().astype(str)).lower()
        words = re.findall(r'\w+', text)
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

    return reason_counts, sku_counts, Counter(keywords).most_common(12), trans_map

# ================== HTML 报告 ==================
def generate_html_report(df, reason_counts, sku_counts, keywords, trans_map):
    sorted_reasons = reason_counts.sort_values('数量', ascending=False)
    reason_rows = "".join([f"<tr><td style='text-align:left'>{r['原因_html']}</td><td>{r['数量']}</td><td>{r['占比']}%</td></tr>" for _, r in sorted_reasons.iterrows()])

    sku_tables = ""
    if not sku_counts.empty:
        top_skus = sku_counts.sort_values('退款数量', ascending=False).head(5)['SKU'].tolist()
        for sku in top_skus:
            sku_df = df[df['sku'] == sku]
            total = len(sku_df)
            sku_reason = sku_df['reason'].value_counts().reset_index()
            sku_reason.columns = ['原因_en', '频次']
            sku_reason['原因_html'] = sku_reason['原因_en'].apply(lambda x: format_bilingual(x, trans_map, 'html'))
            sku_reason['占比'] = (sku_reason['频次'] / total * 100).round(2)
            rows = "".join([f"<tr><td style='text-align:left'>{row['原因_html']}</td><td>{row['频次']}</td><td>{row['占比']}%</td></tr>" for _, row in sku_reason.iterrows()])
            sku_tables += f"""
            <div style="background:white; padding:15px; border-radius:8px; margin-bottom:20px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <h3 style="margin-top:0;">SKU：{sku} <span style="font-weight:normal; font-size:0.8em; color:#666">（共 {total} 次退款）</span></h3>
                <table><tr><th style="width:60%">退款原因</th><th>频次</th><th>占比</th></tr>{rows}</table>
            </div>
            """

    kw_html = "".join([f"<span class='tag'>{k} <small>({v})</small></span>" for k, v in keywords])

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background:#f4f7f6; padding:40px; color:#333; }}
            .container {{ max-width:1000px; margin:auto; background:white; padding:40px; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            h1 {{ text-align:center; border-bottom: 2px solid #eee; padding-bottom: 20px; color:#2c3e50; }}
            h2 {{ margin-top:40px; color:#6c5ce7; border-left:5px solid #6c5ce7; padding-left:12px; }}
            table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size: 14px; }}
            th {{ background:#b94136; color:#ffffff; padding:12px; text-align:left; border: none; }}
            td {{ padding:10px 12px; border-bottom:1px solid #eee; vertical-align: middle; }}
            .tag {{ display:inline-block; background:#e8f4f8; color:#2980b9; padding:6px 12px; margin:5px; border-radius:4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Amazon 退款分析报告 (AI 智能翻译)</h1>
            <h2>1. 全局退款原因分布</h2>
            <table><tr><th style="width:60%">退款原因 (Original / CN)</th><th>频次</th><th>占比</th></tr>{reason_rows}</table>
            <h2>2. 重点 SKU 详细分析</h2>{sku_tables}
            <h2>3. 客户评论关键词</h2><div style="line-height:1.6;">{kw_html}</div>
        </div>
    </body>
    </html>
    """

# ================== UI 主逻辑 ==================
# 使用表情符号增强标题
st.title("📊 Amazon 退款智能分析终端 (Pro)")

# ====== 用户信息和管理员日志左右两列显示 ======
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### 👤 用户信息登记")
    # st.info("请先填写下方信息，才能进行分析操作。") # 去掉这个提示，界面更清爽

    if 'user_name' not in st.session_state: st.session_state.user_name = ""
    if 'user_dept' not in st.session_state: st.session_state.user_dept = ""

    user_name = st.text_input("您的姓名", value=st.session_state.user_name, placeholder="请输入您的姓名")
    user_dept = st.text_input("所属部门", value=st.session_state.user_dept, placeholder="例如：运营一部")
    st.session_state.user_name = user_name
    st.session_state.user_dept = user_dept

with col2:
    st.markdown("### 🔐 管理员入口")
    password_input = st.text_input("请输入管理员密码", type="password", key="admin_pwd", placeholder="仅管理员可见")
    if password_input == ADMIN_PASSWORD:
        if os.path.exists(LOG_FILE):
            try:
                log_df = pd.read_csv(LOG_FILE)
                # st.dataframe(log_df, hide_index=True, height=150) # 稍微限制一下高度
                with st.expander("查看最近访问日志", expanded=True):
                     st.dataframe(log_df.tail(5), hide_index=True, use_container_width=True) # 只看最近5条

                csv_data = log_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 导出完整日志 (CSV)", csv_data, "access_log.csv", "text/csv", type="primary")
            except:
                st.error("日志文件读取失败")
        else:
            st.info("暂无使用记录")
    elif password_input != "":
        st.error("密码错误")

# 用户信息填写完才能上传文件
if user_name and user_dept:
    # 使用装饰性分割线代替简单的 st.markdown("---")
    st.markdown("""
        <div style="display: flex; align-items: center; margin: 30px 0 20px 0;">
            <div style="flex-grow: 1; height: 1px; background: linear-gradient(to right, transparent, #ddd, transparent);"></div>
            <div style="margin: 0 15px; color: #6c5ce7; font-size: 1.2em;">🚀 工作区准备就绪</div>
            <div style="flex-grow: 1; height: 1px; background: linear-gradient(to right, transparent, #ddd, transparent);"></div>
        </div>
    """, unsafe_allow_html=True)

    st.success(f"欢迎，**{user_dept}** 的 **{user_name}**。已安全连接至 AI 模型: `{MODEL_NAME}`")
    
    # 将上传组件放入一个容器中，使其更突出
    with st.container():
        st.markdown("#### 📂 数据导入")
        uploaded_file = st.file_uploader("请上传 Amazon 退款报告 (支持 CSV 格式)", type="csv", help="请确保CSV文件包含 'reason' 和 'sku' 列")

    if uploaded_file:
        df = None
        try:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding="utf-8")
        except UnicodeDecodeError:
            try:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding="gbk")
            except UnicodeDecodeError:
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, encoding="cp1252")
                except Exception as e:
                    st.error(f"❌ 无法识别文件编码: {e}")

        if df is not None:
            if 'last_uploaded_file' not in st.session_state or st.session_state.last_uploaded_file != uploaded_file.name:
                log_action(user_name, user_dept, "分析文件", uploaded_file.name)
                st.session_state.last_uploaded_file = uploaded_file.name

            result = process_data(df)
            if len(result) == 5: 
                st.error(result[4])
            else:
                r_counts, s_counts, kws, trans_map = result
                if r_counts is not None:
                    st.divider()
                    # 结果展示区
                    st.markdown("### 📊 智能分析仪表盘")
                    
                    # 使用卡片包裹图表
                    with st.container():
                        fig = px.bar(r_counts, x='数量', y='原因_display', orientation='h',
                                    title="<b>退款原因分布 (中英对照)</b>", text='数量', height=500, 
                                    color='数量', color_continuous_scale=px.colors.sequential.Teal)
                        fig.update_layout(xaxis_title="", yaxis_title="", title_x=0, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                        fig.update_traces(textposition='outside')
                        st.plotly_chart(fig, use_container_width=True)
                    
                    st.divider()
                    html_report = generate_html_report(df, r_counts, s_counts, kws, trans_map)
                    
                    # 下载区域
                    col_dl1, col_dl2 = st.columns([3,1])
                    with col_dl1:
                         st.success("✅ AI 分析已完成！您可以查看上方图表或下载详细报告。")
                    with col_dl2:
                        st.download_button(
                            "📥 下载完整 HTML 报告",
                            html_report,
                            file_name="Amazon_Refund_AI_Report.html",
                            mime="text/html",
                            type="primary", # 使用主要按钮样式
                            use_container_width=True
                        )
else:
    # 在未登录状态下显示一个占位提示
    st.markdown("""
        <div style="text-align: center; margin-top: 40px; padding: 40px; background: #f8f9fa; border-radius: 10px; color: #666;">
            <h3>👋 欢迎使用</h3>
            <p>请在上方左侧填写您的<b>姓名</b>和<b>部门</b>以开始会话。</p>
        </div>
    """, unsafe_allow_html=True)
