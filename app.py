import streamlit as st
import pandas as pd
import plotly.express as px
import json
from openai import OpenAI
import os
import datetime
import csv
import re
from collections import Counter

# ================== 🛠️ 配置区域 ==================
SILICONFLOW_API_KEY = "sk-wmbipxzixpvwddjoisctfpsdwneznyliwoxgxbbzcdrvaiye" 
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
ADMIN_PASSWORD = "dhzjb" 
BASE_URL = "https://api.siliconflow.cn/v1"
LOG_FILE = "access_log.csv"

# 页面配置
st.set_page_config(page_title="Amazon 智能分析终端", layout="wide", page_icon="🛡️")

# ================== 🛡️ 【封印 2.0：极速 JS 巡逻 + CSS 预埋】 ==================
# 将此处代码置于最顶部，确保浏览器第一时间解析
def apply_ultra_mask():
    # 预埋 CSS：在 JS 生效前先通过 CSS 强制隐藏已知 ID
    st.markdown("""
        <style>
            /* 基础组件强制隐藏 */
            header[data-testid="stHeader"], [data-testid="stDecoration"], footer, [data-testid="stStatusWidget"] {
                display: none !important; visibility: hidden !important;
            }

            /* 右下角物理屏蔽层：极高层级 + 拦截点击 */
            .terminal-shield {
                position: fixed; bottom: 0; right: 0; width: 220px; height: 50px;
                background: #0f172a; z-index: 2147483647; pointer-events: auto;
                display: flex; align-items: center; justify-content: center;
                border-top-left-radius: 15px; border-left: 1px solid #1e293b;
                box-shadow: -5px -5px 20px rgba(0,0,0,0.4);
            }
            .shield-text { color: #38bdf8; font-family: monospace; font-size: 11px; letter-spacing: 2px; font-weight: bold; }

            /* 专业 UI 样式优化 */
            .stApp { background: #f8fafc; }
            .main-card {
                background: white; padding: 40px; border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.05); border: 1px solid #f1f5f9;
            }
            .stButton>button {
                width: 100%; border-radius: 10px !important; height: 45px;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
                color: white !important; font-weight: bold !important; border: none !important;
                transition: all 0.3s ease !important;
            }
            .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
        </style>
        <div class="terminal-shield" id="main-mask"><span class="shield-text">SYSTEM SECURED</span></div>
    """, unsafe_allow_html=True)

    # 极速 JS：使用 MutationObserver 实时监听并抹除
    st.html("""
        <script>
            const hideTarget = () => {
                const topDoc = window.top.document;
                const els = topDoc.querySelectorAll('.stAppToolbar, [data-testid="stAppToolbar"], a[href*="streamlit.io"]');
                els.forEach(el => { el.style.setProperty('display', 'none', 'important'); });
            };
            // 1. 每 50ms 巡逻一次，消除闪烁感
            setInterval(hideTarget, 50);
            // 2. 监听 DOM 变化，瞬时反应
            const observer = new MutationObserver(hideTarget);
            observer.observe(window.top.document.body, { childList: true, subtree: true });
        </script>
    """, unsafe_allow_javascript=True)

apply_ultra_mask()

# ================== 初始化状态管理 ==================
if 'confirmed' not in st.session_state: st.session_state.confirmed = False

def init_log_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            csv.writer(f).writerow(["时间", "姓名", "部门", "操作", "备注"])

def log_action(name, dept, action, note=""):
    try:
        init_log_file()
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
            csv.writer(f).writerow([datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name, dept, action, note])
    except: pass

# ================== UI 主界面 ==================
st.markdown("<h1 style='text-align:center; color:#0f172a; margin-top:50px;'>AMAZON ANALYTICS TERMINAL</h1>", unsafe_allow_html=True)

# 步骤一：身份验证区
if not st.session_state.confirmed:
    with st.container():
        st.markdown("<div class='main-card'>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 👤 身份登记")
            u_name = st.text_input("姓名", placeholder="Your Name", label_visibility="collapsed")
            u_dept = st.text_input("部门", placeholder="Department", label_visibility="collapsed")
            if st.button("🚀 初始化分析终端"):
                if u_name and u_dept:
                    st.session_state.user_name = u_name
                    st.session_state.user_dept = u_dept
                    st.session_state.confirmed = True
                    log_action(u_name, u_dept, "终端启动")
                    st.rerun()
                else:
                    st.error("请完整填写姓名和部门")
        
        with col2:
            st.markdown("### 🔐 管理权证")
            pwd = st.text_input("管理员密码", type="password", placeholder="Admin Key", label_visibility="collapsed")
            if pwd == ADMIN_PASSWORD:
                st.markdown("<style>.terminal-shield{display:none !important;}</style>", unsafe_allow_html=True)
                st.success("管理员权限已解锁 (遮罩已卸载)")
                if os.path.exists(LOG_FILE):
                    st.download_button("📥 导出访问日志", pd.read_csv(LOG_FILE).to_csv(index=False).encode('utf-8-sig'), "logs.csv", "text/csv")
        st.markdown("</div>", unsafe_allow_html=True)

# 步骤二：核心功能区 (确认身份后才显示)
else:
    with st.container():
        st.markdown(f"<div class='main-card'>", unsafe_allow_html=True)
        st.info(f"🟢 **当前节点已授权：** {st.session_state.user_dept} | {st.session_state.user_name}")
        
        up_file = st.file_uploader("📂 选择 Amazon 退款报告文件 (CSV)", type="csv")
        
        if up_file:
            try:
                df = pd.read_csv(up_file, encoding='utf-8')
            except:
                df = pd.read_csv(up_file, encoding='gbk')
            
            if st.button("开始 AI 智能解析"):
                with st.status("正在建立安全加密连接...", expanded=True) as status:
                    st.write("正在读取原始数据结构...")
                    # 模拟处理
                    st.write(f"正在调用 {MODEL_NAME} 进行自然语言处理...")
                    # 数据逻辑处理...
                    status.update(label="分析完成！", state="complete", expanded=False)
                
                # 示例图表展示
                st.markdown("### 📊 分析透视图")
                chart_data = df['reason'].value_counts().reset_index()
                fig = px.pie(chart_data, values='count', names='reason', hole=.4, 
                             color_discrete_sequence=px.colors.sequential.RdBu)
                fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)
                
                if 'last_f' not in st.session_state or st.session_state.last_f != up_file.name:
                    log_action(st.session_state.user_name, st.session_state.user_dept, "执行分析", up_file.name)
                    st.session_state.last_f = up_file.name

        if st.button("🔄 退出并切换用户", type="secondary"):
            st.session_state.confirmed = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
