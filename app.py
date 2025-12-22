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

# ================== 🛠️ 【配置区域】 请在这里修改 ==================

# 1. 硅基流动 API Key (必填)
SILICONFLOW_API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" 

# 2. AI 模型选择
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

# 3. 管理员密码
ADMIN_PASSWORD = "dhzjb" 

# 4. 其他配置
BASE_URL = "https://api.siliconflow.cn/v1"
LOG_FILE = "access_log.csv"

# ==============================================================

# 页面配置
st.set_page_config(page_title="Amazon 退款分析 (AI 自动翻译版)", layout="wide")

# 🔥🔥🔥【最终修复版 CSS】确保箭头可见 + 隐藏多余按钮 🔥🔥🔥
hide_streamlit_style = """
<style>
    /* 1. 顶部 Header 容器：背景设为透明，但不隐藏，确保箭头活着 */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* 2. 隐藏 Header 里的装饰彩条 */
    [data-testid="stDecoration"] {
        display: none !important;
    }

    /* 3. 隐藏右上角的三点菜单 */
    [data-testid="stMainMenu"] {
        visibility: hidden !important;
        display: none !important;
    }

    /* 4. 隐藏 Deploy 按钮 */
    .stDeployButton {
        visibility: hidden !important;
        display: none !important;
    }

    /* 5. 隐藏 Header 右侧的动作区 (确保不留白) */
    [data-testid="stHeaderActionElements"] {
        display: none !important;
    }

    /* 6. 强力隐藏右下角的 Toolbar (Manage app) */
    [data-testid="stToolbar"] {
        visibility: hidden !important;
        display: none !important;
        height: 0 !important;
    }

    /* 7. 隐藏底部 Footer */
    footer {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* 8. 隐藏状态组件 */
    [data-testid="stStatusWidget"] {
        visibility: hidden !important;
        display: none !important;
    }

    /* 9. 【核心】强制显示侧边栏箭头，并设为深色 */
    [data-testid="stSidebarCollapsedControl"] {
        visibility: visible !important;
        display: block !important;
        color: #333333 !important;
        z-index: 100000 !important;
    }

    /* 10. 调整顶部间距 */
    .block-container {
        padding-top: 2rem !important;
    }
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
# 🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥


# ================== 0. 日志系统逻辑 ==================

def init_log_file():
    """初始化日志文件，如果不存在则创建表头"""
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["时间", "姓名", "部门", "操作", "文件名/备注"])

def log_action(name, dept, action, note=""):
    """记录用户操作"""
    try:
        init_log_file()
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([current_time, name, dept, action, note])
    except Exception as e:
        print(f"日志记录失败: {e}")

# ================== 1. 辅助函数 & AI 逻辑 ==================

def format_bilingual(text, trans_map, mode='text'):
    """全局辅助函数，用于将英文转为双语格式"""
    text = str(text)
    cn = trans_map.get(text)
    if cn:
        if mode == 'html':
            # HTML 报告用：两行显示
            return f"{text}<br>({cn})"
        else:
            # 图表用：一行显示
            return f"{text} ({cn})"
    else:
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
        content = content.replace("```json", "").replace("```", "").strip()
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
    # 升序排列，让 Plotly 水平柱状图从上到下是由大到小
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

# ================== HTML 报告生成器 (红色表头) ==================
def generate_html_report(df, reason_counts, sku_counts, keywords, trans_map):
    # 生成报告时需要降序，让数量大的在表格上方
    sorted_reasons = reason_counts.sort_values('数量', ascending=False)
    
    reason_rows = ""
    for _, r in sorted_reasons.iterrows():
        reason_rows += f"""
        <tr><td style="text-align:left">{r['原因_html']}</td><td>{r['数量']}</td><td>{r['占比']}%</td></tr>
        """

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
            
            rows = ""
            for _, row in sku_reason.iterrows():
                rows += f"<tr><td style='text-align:left'>{row['原因_html']}</td><td>{row['频次']}</td><td>{row['占比']}%</td></tr>"
            
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
            
            /* --- 红色表头样式 --- */
            th {{ 
                background:#b94136; 
                color:#ffffff;
                padding:12px; 
                text-align:left; 
                border: none;
            }}

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

st.title("🤖 Amazon 退款智能分析 (Pro)")

# --- 侧边栏：用户信息录入 ---
st.sidebar.header("👤 用户信息登记")
st.sidebar.info("请先填写下方信息，才能进行分析操作。")

# 使用 session_state 记住用户信息
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""
if 'user_dept' not in st.session_state:
    st.session_state.user_dept = ""

user_name = st.sidebar.text_input("您的姓名", value=st.session_state.user_name)
user_dept = st.sidebar.text_input("所属部门", value=st.session_state.user_dept)

# 更新 session_state
st.session_state.user_name = user_name
st.session_state.user_dept = user_dept

# --- 侧边栏：管理员查看日志 ---
st.sidebar.markdown("---")
with st.sidebar.expander("🔐 管理员：查看使用记录"):
    # 使用配置好的变量 ADMIN_PASSWORD
    password_input = st.text_input("请输入管理员密码", type="password")
    
    if password_input == ADMIN_PASSWORD:
        if os.path.exists(LOG_FILE):
            try:
                log_df = pd.read_csv(LOG_FILE)
                st.dataframe(log_df, hide_index=True)
                
                # 提供下载日志按钮
                csv_data = log_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 导出日志数据 (CSV)",
                    csv_data,
                    "access_log.csv",
                    "text/csv"
                )
            except Exception as e:
                st.error("日志文件读取失败")
        else:
            st.info("暂无使用记录")
    elif password_input != "":
        st.error("密码错误")

# --- 主界面逻辑 ---

# 只有当姓名和部门都填写了，才显示上传组件
if user_name and user_dept:
    st.caption(f"欢迎，**{user_dept}** 的 **{user_name}**！🚀 已接入 AI 模型: {MODEL_NAME}")
    
    uploaded_file = st.file_uploader("📂 请上传 Amazon 退款报告 (CSV)", type="csv")

    if uploaded_file:
        df = None
        # 读取文件
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
            # === 🎯 触发日志记录 ===
            # 使用 session_state 防止页面交互时重复记录同一文件
            if 'last_uploaded_file' not in st.session_state or st.session_state.last_uploaded_file != uploaded_file.name:
                log_action(user_name, user_dept, "分析文件", uploaded_file.name)
                st.session_state.last_uploaded_file = uploaded_file.name

            # 开始处理
            result = process_data(df)
            
            if len(result) == 5: 
                 st.error(result[4])
            else:
                r_counts, s_counts, kws, trans_map = result
                
                if r_counts is not None:
                    # 图表
                    fig = px.bar(r_counts, x='数量', y='原因_display', orientation='h',
                                 title="退款原因分布 (中英对照)", text='数量', height=600)
                    fig.update_layout(xaxis_title="", yaxis_title="")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 报告
                    html_report = generate_html_report(df, r_counts, s_counts, kws, trans_map)
                    
                    st.success("✅ 分析完成！")
                    st.download_button(
                        "📥 下载完整 HTML 分析报告",
                        html_report,
                        file_name="Amazon_Refund_AI_Report.html",
                        mime="text/html"
                    )
else:
    st.warning("👈 请先在左侧侧边栏填写【姓名】和【部门】，即可开始使用工具。")