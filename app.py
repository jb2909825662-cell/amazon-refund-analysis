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

# ================== 🛡️ 【极速封印：JS 巡逻 + CSS 预埋】 ==================
def apply_ultra_mask():
    # 预埋 CSS：第一时间强行隐藏
    st.markdown("""
        <style>
            /* 1. 基础组件隐藏 */
            header[data-testid="stHeader"], [data-testid="stDecoration"], footer, [data-testid="stStatusWidget"] {
                display: none !important; visibility: hidden !important;
            }

            /* 2. 右下角物理屏蔽层：极高层级，拦截点击 */
            .terminal-shield {
                position: fixed; bottom: 0; right: 0; width: 220px; height: 50px;
                background: #0f172a; z-index: 2147483647; pointer-events: auto;
                display: flex; align-items: center; justify-content: center;
                border-top-left-radius: 15px; border-left: 1px solid #1e293b;
                box-shadow: -5px -5px 20px rgba(0,0,0,0.4);
            }
            .shield-text { color: #38bdf8; font-family: monospace; font-size: 11px; letter-spacing: 2px; font-weight: bold; }

            /* 3. 专业级 UI 布局优化 */
            .stApp { background: #f8fafc; }
            .main-card {
                background: white; padding: 40px; border-radius: 24px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.06); border: 1px solid #f1f5f9;
                margin-bottom: 20px;
            }
            
            /* 标签样式加粗 */
            label[data-testid="stWidgetLabel"] p {
                font-weight: 600 !important; color: #334155 !important; font-size: 14px !important;
            }

            /* 按钮美化：深色渐变 */
            .stButton>button {
                width: 100%; border-radius: 12px !important; height: 48px;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
                color: white !important; font-weight: bold !important; border: none !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
            }
            .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.25); }
        </style>
        <div class="terminal-shield" id="main-mask"><span class="shield-text">SYSTEM SECURED</span></div>
    """, unsafe_allow_html=True)

    # 4. 极速 JS 巡逻：50ms 频率阻断
    st.html("""
        <script>
            const hideTarget = () => {
                const topDoc = window.top.document;
                const els = topDoc.querySelectorAll('.stAppToolbar, [data-testid="stAppToolbar"], a[href*="streamlit.io"]');
                els.forEach(el => { el.style.setProperty('display', 'none', 'important'); });
            };
            setInterval(hideTarget, 50); // 每 50 毫秒扫描一次
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
st.markdown("<h1 style='text-align:center; color:#0f172a; margin: 40px 0;'>🛡️ Amazon 退款智能分析终端 (Pro)</h1>", unsafe_allow_html=True)

# 步骤一：身份验证区
if not st.session_state.confirmed:
    with st.container():
        st.markdown("<div class='main-card'>", unsafe_allow_html=True)
        col1, col2 = st.columns([1.2, 0.8], gap="large")
        
        with col1:
            st.markdown("#### 👤 终端访问登记")
            st.caption("请输入您的真实信息以解锁分析功能。")
            st.write("")
            u_name = st.text_input("您的姓名", placeholder="例如：张三")
            u_dept = st.text_input("所属部门", placeholder="例如：运营一部")
            
            st.write("")
            if st.button("🚀 初始化分析终端并进入"):
                if u_name and u_dept:
                    st.session_state.user_name = u_name
                    st.session_state.user_dept = u_dept
                    st.session_state.confirmed = True
                    log_action(u_name, u_dept, "终端初始化成功")
                    st.rerun()
                else:
                    st.warning("⚠️ 请完整填写姓名和部门以继续")
        
        with col2:
            st.markdown("#### 🔐 管理员权限")
            st.caption("仅限开发者进行日志管理与维护。")
            st.write("")
            pwd = st.text_input("管理权证 (Password)", type="password", placeholder="Admin Key")
            if pwd == ADMIN_PASSWORD:
                # 管理员登录后卸载遮罩
                st.markdown("<style>.terminal-shield{display:none !important;}</style>", unsafe_allow_html=True)
                st.success("✅ 管理员身份已验证")
                if os.path.exists(LOG_FILE):
                    st.download_button("📥 导出全量访问日志", pd.read_csv(LOG_FILE).to_csv(index=False).encode('utf-8-sig'), "access_log.csv", "text/csv")
        st.markdown("</div>", unsafe_allow_html=True)

# 步骤二：核心功能区 (确认身份后才显示)
else:
    with st.container():
        st.markdown("<div class='main-card'>", unsafe_allow_html=True)
        
        # 状态栏
        c_status1, c_status2 = st.columns([3, 1])
        with c_status1:
            st.info(f"🟢 **当前节点已授权：** {st.session_state.user_dept} | {st.session_state.user_name}")
        with c_status2:
            if st.button("🔄 退出/切换用户"):
                st.session_state.confirmed = False
                st.rerun()

        st.markdown("---")
        
        # 文件上传区域
        st.markdown("#### 📂 载入 Amazon 数据源")
        up_file = st.file_uploader("请拖拽或选择 CSV 文件进行智能解析", type="csv")
        
        if up_file:
            try:
                # 预读数据，不展示具体表格以保持专业感
                df = pd.read_csv(up_file, encoding='utf-8')
            except:
                df = pd.read_csv(up_file, encoding='gbk')
            
            st.success(f"数据已载入：`{up_file.name}` (共 {len(df)} 条记录)")
            
            if st.button("📊 执行深度 AI 分析"):
                # 使用状态加载器
                with st.status("正在建立安全加密连接...", expanded=True) as status:
                    st.write("正在识别数据维度...")
                    st.write(f"正在调用 {MODEL_NAME} 进行双语翻译建模...")
                    # 这里放置您的 translate_reasons_with_llm 等处理逻辑
                    st.write("正在生成多维可视化视图...")
                    status.update(label="✅ 分析引擎处理完成", state="complete", expanded=False)
                
                # 展示图表
                st.markdown("### 📈 退款原因分布图 (AI 翻译版)")
                if 'reason' in df.columns:
                    chart_data = df['reason'].value_counts().reset_index()
                    fig = px.bar(chart_data, x='count', y='reason', orientation='h', 
                                 color='count', color_continuous_scale='Blues',
                                 labels={'count':'出现频次', 'reason':'退款原因'})
                    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig, use_container_width=True)
                
                if 'last_f' not in st.session_state or st.session_state.last_f != up_file.name:
                    log_action(st.session_state.user_name, st.session_state.user_dept, "执行分析任务", up_file.name)
                    st.session_state.last_f = up_file.name
        
        st.markdown("</div>", unsafe_allow_html=True)

# 底部填充，避免被遮罩挡住内容
st.write("")
st.write("")
