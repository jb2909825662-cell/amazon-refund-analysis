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

# ================== 🔥 【终极封印：JS 穿透 + 物理遮罩】 🔥 ==================
def apply_ultra_mask():
    # 1. CSS 物理遮罩：盖住右下角并拦截点击
    st.markdown("""
        <style>
            /* 隐藏应用内原生组件 */
            header[data-testid="stHeader"], [data-testid="stDecoration"], footer, [data-testid="stStatusWidget"] {
                visibility: hidden !important;
                display: none !important;
            }

            /* 物理屏蔽层：设置极高层级，拦截所有物理点击 */
            .terminal-shield {
                position: fixed;
                bottom: 0;
                right: 0;
                width: 200px;
                height: 60px;
                background: #1e293b; 
                z-index: 2147483647; /* 浏览器允许的最大层级 */
                pointer-events: auto; /* 关键：拦截下方所有点击 */
                display: flex;
                align-items: center;
                justify-content: center;
                border-top-left-radius: 12px;
                box-shadow: -5px -5px 15px rgba(0,0,0,0.3);
                border-left: 1px solid #334155;
                border-top: 1px solid #334155;
            }
            .shield-text {
                color: #94a3b8;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 2px;
            }
            
            /* 全局背景美化 */
            .stApp { background-color: #f1f5f9; background-image: radial-gradient(#cbd5e1 1px, transparent 0); background-size: 30px 30px; }
            .block-container { 
                background-color: #ffffff; padding: 2.5rem 3rem !important; 
                border-radius: 16px; box-shadow: 0 20px 25px rgba(0,0,0,0.1); 
                margin-top: 3rem !important; border: 1px solid #e2e8f0; 
            }
        </style>
        <div class="terminal-shield" id="main-mask">
            <span class="shield-text">● SECURE TERMINAL</span>
        </div>
    """, unsafe_allow_html=True)

    # 2. JS 穿透：每秒巡逻，强行移除外部注入的红色工具栏
    st.html("""
        <script>
            const clearStreamlitUI = () => {
                // 寻找并隐藏外部容器中的管理工具栏
                const selectors = [
                    '.stAppToolbar', 
                    '[data-testid="stAppToolbar"]', 
                    '#tabs-bui3-tabpanel-0',
                    'header'
                ];
                
                // 穿透 Iframe 寻找父级文档中的元素
                try {
                    const topDoc = window.top.document;
                    selectors.forEach(s => {
                        topDoc.querySelectorAll(s).forEach(el => {
                            el.style.display = 'none';
                            el.style.visibility = 'hidden';
                        });
                    });
                    // 特别针对右下角的红色按钮链接
                    topDoc.querySelectorAll('a[href*="streamlit.io"]').forEach(a => a.style.display = 'none');
                } catch (e) {
                    // 如果跨域限制，则在当前层尽力隐藏
                    selectors.forEach(s => {
                        document.querySelectorAll(s).forEach(el => el.style.display = 'none');
                    });
                }
            };
            // 持续监控，防止动态刷新
            setInterval(clearStreamlitUI, 1000);
        </script>
    """, unsafe_allow_javascript=True)

apply_ultra_mask()

# ================== 日志系统 ==================
def init_log_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["时间", "姓名", "部门", "操作", "文件名/备注"])

def log_action(name, dept, action, note=""):
    try:
        init_log_file(); current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
            csv.writer(f).writerow([current_time, name, dept, action, note])
    except: pass

# ================== AI 逻辑 ==================
def translate_reasons_with_llm(unique_reasons):
    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=BASE_URL)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "你是一个专业的亚马逊翻译助手。"}, 
                      {"role": "user", "content": f"将以下列表翻译成中文JSON: {json.dumps(list(unique_reasons))}"}],
            temperature=0.1, response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except: return {}

@st.cache_data(show_spinner=False)
def process_data(df):
    df.columns = [c.strip() for c in df.columns]
    unique_reasons = [str(r) for r in df['reason'].dropna().unique()]
    with st.spinner("AI 正在执行语言解析..."):
        trans_map = translate_reasons_with_llm(unique_reasons)
    
    r_counts = df['reason'].value_counts().reset_index()
    r_counts.columns = ['原因_en', '数量']
    r_counts['原因_display'] = r_counts['原因_en'].apply(lambda x: f"{x} ({trans_map.get(x, x)})")
    return r_counts, trans_map

# ================== UI 主逻辑 ==================
st.title("🛡️ Amazon 退款分析终端 (Pro)")

c1, c2 = st.columns(2)
with c1:
    st.markdown("#### 👤 权限验证")
    u_name = st.text_input("姓名", placeholder="姓名", label_visibility="collapsed")
    u_dept = st.text_input("部门", placeholder="部门", label_visibility="collapsed")

with c2:
    st.markdown("#### 🔐 管理入口")
    pwd = st.text_input("密码", type="password", placeholder="管理员密码", label_visibility="collapsed")
    
    # --- 【联动功能：管理员脱壳】 ---
    if pwd == ADMIN_PASSWORD:
        st.markdown("""
            <style>
                .terminal-shield { display: none !important; } /* 撤销遮罩 */
                header[data-testid="stHeader"] { visibility: visible !important; display: block !important; }
            </style>
            <script>window.top.document.querySelectorAll('.stAppToolbar').forEach(el => el.style.display = 'block');</script>
        """, unsafe_allow_html=True)
        if os.path.exists(LOG_FILE):
            with st.expander("访问日志"):
                st.dataframe(pd.read_csv(LOG_FILE).tail(5), use_container_width=True)
    elif pwd != "": st.error("密码无效")

if u_name and u_dept:
    st.markdown("---")
    st.success(f"**已授权：** {u_dept} | {u_name}")
    up_file = st.file_uploader("📂 载入数据 (CSV)", type="csv")

    if up_file:
        try:
            df = pd.read_csv(up_file)
            r_c, t_m = process_data(df)
            st.markdown("### 📊 分析视图")
            fig = px.bar(r_c, x='数量', y='原因_display', orientation='h', color='数量', color_continuous_scale='Blues')
            st.plotly_chart(fig, use_container_width=True)
            if 'last_f' not in st.session_state or st.session_state.last_f != up_file.name:
                log_action(u_name, u_dept, "分析文件", up_file.name)
                st.session_state.last_f = up_file.name
        except Exception as e: st.error(f"分析出错: {e}")
else:
    st.markdown("""<div style="text-align:center; padding:50px; color:#64748b; background:#f8fafc; border-radius:12px; border:2px dashed #cbd5e1;">
        请输入左侧身份信息以激活分析终端</div>""", unsafe_allow_html=True)
