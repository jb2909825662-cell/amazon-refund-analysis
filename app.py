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
st.set_page_config(page_title="Amazon 退款分析终端", layout="wide", page_icon="🛡️")

# ================== 🔥 【高级物理遮罩 & 企业级配色 CSS】 🔥 ==================
theme_css = """
<style>
    /* 1. 强力隐藏原生组件 */
    header[data-testid="stHeader"], 
    [data-testid="stDecoration"], 
    footer, 
    [data-testid="stStatusWidget"] {
        visibility: hidden !important;
        display: none !important;
    }

    /* 2. 物理屏蔽罩：彻底遮挡并拦截右下角点击 */
    .terminal-shield {
        position: fixed;
        bottom: 0;
        right: 0;
        width: 180px;
        height: 50px;
        background: #1e293b; /* 深色科技蓝，遮盖红色按钮 */
        z-index: 9999999;
        pointer-events: auto; /* 关键：拦截下方所有点击 */
        display: flex;
        align-items: center;
        justify-content: center;
        border-top-left-radius: 10px;
        box-shadow: -2px -2px 10px rgba(0,0,0,0.2);
        border-left: 1px solid #334155;
        border-top: 1px solid #334155;
    }
    
    .shield-text {
        color: #94a3b8;
        font-family: 'Courier New', Courier, monospace;
        font-size: 11px;
        font-weight: bold;
        letter-spacing: 1px;
    }

    /* 3. 全局背景美化：极客灰几何纹理 */
    .stApp {
        background-color: #f1f5f9;
        background-image: radial-gradient(#cbd5e1 1px, transparent 0);
        background-size: 30px 30px;
    }

    /* 4. 内容容器卡片化 */
    .block-container {
        background-color: #ffffff;
        padding: 2.5rem 3rem !important;
        border-radius: 16px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
        margin-top: 3rem !important;
        margin-bottom: 3rem !important;
        border: 1px solid #e2e8f0;
    }

    /* 5. 按钮与输入框配色优化 */
    .stButton>button {
        background-color: #0f172a !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 0.5rem 1rem !important;
    }
    
    /* 标题样式 */
    h1 {
        color: #0f172a;
        font-weight: 800 !important;
        text-align: center;
        margin-bottom: 2rem !important;
        text-transform: uppercase;
        letter-spacing: -1px;
    }
</style>

<div class="terminal-shield">
    <span class="shield-text">● SECURE TERMINAL</span>
</div>
"""
st.markdown(theme_css, unsafe_allow_html=True)

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
    user_prompt = f"请将以下 Amazon 退款原因列表翻译成中文。输入数据: {reasons_str}。要求: 1.翻译简练专业。2.返回 JSON 字典(Key为英文,Value为中文)。3.直接返回内容，不要Markdown。"
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except Exception as e:
        st.error(f"AI 翻译接口调用失败: {e}")
        return {}

@st.cache_data(show_spinner=False)
def process_data(df):
    df.columns = [c.strip() for c in df.columns]
    if 'reason' not in df.columns: return None, None, None, None, "缺少 'reason' 列"

    unique_reasons = [str(r) for r in df['reason'].dropna().unique()]
    with st.spinner("AI 正在执行智能语言解析..."):
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
    reason_rows = "".join([f"<tr><td>{r['原因_html']}</td><td>{r['数量']}</td><td>{r['占比']}%</td></tr>" for _, r in sorted_reasons.iterrows()])
    return f"""
    <html><head><meta charset="utf-8"><style>
        body {{ font-family: sans-serif; background:#f8fafc; padding:30px; }}
        .box {{ background:white; padding:30px; border-radius:12px; box-shadow:0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color:#1e293b; text-align:center; }}
        table {{ width:100%; border-collapse:collapse; margin-top:20px; }}
        th {{ background:#334155; color:white; padding:12px; text-align:left; }}
        td {{ padding:10px; border-bottom:1px solid #e2e8f0; }}
    </style></head><body><div class="box"><h1>Amazon 退款分析报告</h1><table><tr><th>退款原因</th><th>频次</th><th>占比</th></tr>{reason_rows}</table></div></body></html>
    """

# ================== UI 主逻辑 ==================
st.title("🛡️ Amazon 退款分析终端 (Pro)")

# 登录与管理区
c1, c2 = st.columns(2)
with c1:
    st.markdown("#### 👤 权限验证")
    u_name = st.text_input("姓名", placeholder="姓名", label_visibility="collapsed")
    u_dept = st.text_input("部门", placeholder="部门", label_visibility="collapsed")
    st.session_state.user_name = u_name
    st.session_state.user_dept = u_dept

with c2:
    st.markdown("#### 🔐 管理入口")
    pwd = st.text_input("密码", type="password", placeholder="管理员密码", label_visibility="collapsed")
    if pwd == ADMIN_PASSWORD:
        if os.path.exists(LOG_FILE):
            with st.expander("访问日志"):
                st.dataframe(pd.read_csv(LOG_FILE).tail(5), use_container_width=True)
    elif pwd != "": st.error("密码无效")

# 操作区
if u_name and u_dept:
    st.markdown("---")
    st.success(f"**已授权：** {u_dept} | {u_name}")
    up_file = st.file_uploader("📂 载入数据 (CSV)", type="csv")

    if up_file:
        try:
            df = pd.read_csv(up_file, encoding="utf-8")
        except:
            df = pd.read_csv(up_file, encoding="gbk")

        if df is not None:
            if 'last_file' not in st.session_state or st.session_state.last_file != up_file.name:
                log_action(u_name, u_dept, "执行分析", up_file.name)
                st.session_state.last_file = up_file.name

            res = process_data(df)
            if len(res) == 5: st.error(res[4])
            else:
                r_c, s_c, kws, t_m = res
                st.markdown("### 📊 核心指标视图")
                fig = px.bar(r_c, x='数量', y='原因_display', orientation='h', 
                             color='数量', color_continuous_scale='Blues')
                fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig, use_container_width=True)
                
                rep = generate_html_report(df, r_c, s_c, kws, t_m)
                st.download_button("📥 导出分析报告 (HTML)", rep, file_name="Refund_Report.html", mime="text/html", use_container_width=True)
else:
    st.markdown("""<div style="text-align:center; padding:50px; color:#64748b; background:#f8fafc; border-radius:12px; border:2px dashed #cbd5e1;">
        请输入左侧身份信息以激活分析终端</div>""", unsafe_allow_html=True)
