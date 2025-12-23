import streamlit as st
import pandas as pd
import json
from openai import OpenAI
import os
import datetime
import csv
import re
from collections import Counter
import streamlit.components.v1 as components # 用于在 Streamlit 中渲染 ECharts

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
    st.markdown("""
        <style>
            /* 1. 基础组件隐藏 */
            header[data-testid="stHeader"], [data-testid="stDecoration"], footer, [data-testid="stStatusWidget"] {
                display: none !important; visibility: hidden !important;
            }

            /* 2. 右下角物理屏蔽层 */
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
            
            label[data-testid="stWidgetLabel"] p {
                font-weight: 600 !important; color: #334155 !important; font-size: 14px !important;
            }

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

    st.html("""
        <script>
            const hideTarget = () => {
                const topDoc = window.top.document;
                const els = topDoc.querySelectorAll('.stAppToolbar, [data-testid="stAppToolbar"], a[href*="streamlit.io"]');
                els.forEach(el => { el.style.setProperty('display', 'none', 'important'); });
            };
            setInterval(hideTarget, 50);
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

# ================== 🎨 颜色算法 (红绿灯渐变) ==================
def get_traffic_color(value, min_val, max_val):
    """
    根据数值计算颜色：
    低值 -> 绿色 (#2ecc71)
    中值 -> 黄色 (#f1c40f)
    高值 -> 红色 (#e74c3c)
    """
    if max_val == min_val: return "#e74c3c"
    
    # 归一化 (0.0 - 1.0)
    ratio = (value - min_val) / (max_val - min_val)
    
    # 简单的插值算法
    if ratio < 0.5:
        # Green to Yellow
        r = int(46 + (241 - 46) * (ratio * 2))
        g = int(204 + (196 - 204) * (ratio * 2))
        b = int(113 + (15 - 113) * (ratio * 2))
    else:
        # Yellow to Red
        r = int(241 + (231 - 241) * ((ratio - 0.5) * 2))
        g = int(196 + (76 - 196) * ((ratio - 0.5) * 2))
        b = int(15 + (60 - 15) * ((ratio - 0.5) * 2))
        
    return f"#{r:02x}{g:02x}{b:02x}"

# ================== AI 与 数据处理核心逻辑 ==================
def translate_reasons_with_llm(unique_reasons):
    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=BASE_URL)
    reasons_str = json.dumps(list(unique_reasons))
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "你是一个专业的亚马逊翻译助手。"}, 
                      {"role": "user", "content": f"将以下列表翻译成中文JSON: {reasons_str}"}],
            temperature=0.1, response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except: return {}

def format_bilingual(text, trans_map, mode='text'):
    text = str(text)
    cn = trans_map.get(text)
    if cn: return f"{text}<br>({cn})" if mode == 'html' else f"{text} ({cn})"
    return text

@st.cache_data(show_spinner=False)
def process_data(df):
    df.columns = [c.strip() for c in df.columns]
    unique_reasons = [str(r) for r in df['reason'].dropna().unique()]
    
    # AI 翻译
    with st.spinner("AI 正在执行语言解析..."):
        trans_map = translate_reasons_with_llm(unique_reasons)
    
    # 原因分析
    r_counts = df['reason'].value_counts().reset_index()
    r_counts.columns = ['原因_en', '数量']
    r_counts['原因_display'] = r_counts['原因_en'].apply(lambda x: format_bilingual(x, trans_map, 'text'))
    r_counts['原因_html'] = r_counts['原因_en'].apply(lambda x: format_bilingual(x, trans_map, 'html'))
    r_counts['占比'] = (r_counts['数量'] / len(df) * 100).round(2)
    
    # ECharts 需要数据按升序排列才能在水平柱状图中显示为从上到下的降序
    r_counts = r_counts.sort_values('数量', ascending=True) 
    
    # SKU 分析
    sku_counts = df['sku'].value_counts().reset_index().head(10)
    sku_counts.columns = ['SKU', '退款数量']
    
    # 关键词分析
    keywords = []
    if 'customer-comments' in df.columns:
        stop_words = {'the','to','and','a','of','in','is','it','was','for','on','my','i','with','not','returned','item','amazon','unit','nan','this','that','but','have'}
        text = " ".join(df['customer-comments'].dropna().astype(str)).lower()
        words = re.findall(r'\w+', text)
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

    return r_counts, sku_counts, Counter(keywords).most_common(12), trans_map

# ================== 📊 ECharts 图表构建器 (Python -> JS JSON) ==================
def generate_echarts_option(df_counts):
    # 准备数据
    categories = df_counts['原因_display'].tolist()
    values = df_counts['数量'].tolist()
    
    min_v = min(values) if values else 0
    max_v = max(values) if values else 100
    
    # 构建带有单独样式的 data 数组
    data_with_style = []
    for v in values:
        color = get_traffic_color(v, min_v, max_v)
        data_with_style.append({
            "value": v,
            "itemStyle": {
                "color": color,
                "borderRadius": [0, 4, 4, 0] # 现代感的圆角
            }
        })

    # ECharts 配置项 (JSON 结构)
    option = {
        "backgroundColor": "#ffffff",
        "animationDuration": 1500, # 丝滑入场动画
        "animationEasing": "cubicOut",
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"}
        },
        "grid": {
            "left": "3%",
            "right": "4%",
            "bottom": "3%",
            "containLabel": True
        },
        "xAxis": {
            "type": "value",
            "boundaryGap": [0, 0.01],
            "splitLine": {"show": False} # 去掉背景网格线，更干净
        },
        "yAxis": {
            "type": "category",
            "data": categories,
            "axisLabel": {
                "fontSize": 14,
                "fontWeight": "bold",
                "color": "#333"
            },
            "axisTick": {"show": False},
            "axisLine": {"show": False}
        },
        "series": [
            {
                "name": "退款数量",
                "type": "bar",
                "data": data_with_style,
                "barWidth": "60%",
                "label": {
                    "show": True,
                    "position": "insideRight", # 文字在柱子内部右侧
                    "formatter": "{c}",
                    "color": "#ffffff",    # 🔥 强制白色
                    "fontSize": 18,        # 🔥 强制 20px 大号字体
                    "fontWeight": "bold",  # 🔥 强制加粗
                    "padding": [0, 10, 0, 0] #稍微右边留点空隙
                }
            }
        ]
    }
    return option

# ================== HTML 报告生成器 (含 ECharts) ==================
def generate_html_report(df, reason_counts, sku_counts, keywords, trans_map, echarts_option):
    # 将 Python 字典转为 JSON 字符串，供 HTML 中的 JS 使用
    echarts_json = json.dumps(echarts_option)

    # 需要倒序用于表格显示 (大数在前)
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
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Amazon Refund Analysis Report</title>
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background:#f4f7f6; padding:40px; color:#333; }}
            .container {{ max-width:1000px; margin:auto; background:white; padding:40px; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            h1 {{ text-align:center; border-bottom: 2px solid #eee; padding-bottom: 20px; color:#2c3e50; }}
            h2 {{ margin-top:40px; color:#6c5ce7; border-left:5px solid #6c5ce7; padding-left:12px; }}
            table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size: 14px; }}
            th {{ background:#b94136; color:#ffffff; padding:12px; text-align:left; border: none; }}
            td {{ padding:10px 12px; border-bottom:1px solid #eee; vertical-align: middle; }}
            .tag {{ display:inline-block; background:#e8f4f8; color:#2980b9; padding:6px 12px; margin:5px; border-radius:4px; }}
            
            /* 图表容器 */
            #main-chart {{
                width: 100%;
                height: 650px; /* 增加高度以适应大字体 */
                margin-bottom: 40px;
                border: 1px solid #f0f0f0;
                border-radius: 8px;
                padding: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Amazon 退款分析报告 (AI 智能翻译)</h1>
            
            <h2>1. 可视化分析概览</h2>
            <div id="main-chart"></div>
            <script type="text/javascript">
                // 初始化图表
                var myChart = echarts.init(document.getElementById('main-chart'));
                var option = {echarts_json}; // 注入 Python 生成的 JSON
                myChart.setOption(option);
                // 响应式调整
                window.addEventListener('resize', function() {{
                    myChart.resize();
                }});
            </script>

            <h2>2. 全局退款原因分布表</h2>
            <table><tr><th style="width:60%">退款原因 (Original / CN)</th><th>频次</th><th>占比</th></tr>{reason_rows}</table>
            
            <h2>3. 重点 SKU 详细分析</h2>{sku_tables}
            
            <h2>4. 客户评论关键词</h2><div style="line-height:1.6;">{kw_html}</div>
        </div>
    </body>
    </html>
    """

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
            df = None
            try:
                up_file.seek(0)
                df = pd.read_csv(up_file, encoding='utf-8')
            except UnicodeDecodeError:
                try:
                    up_file.seek(0)
                    df = pd.read_csv(up_file, encoding='gbk')
                except Exception as e:
                    st.error(f"文件编码识别失败: {e}")
            except pd.errors.EmptyDataError:
                st.error("❌ 上传的文件内容为空！")
            except Exception as e:
                st.error(f"❌ 文件读取发生未知错误: {e}")
            
            if df is not None:
                st.success(f"数据已载入：`{up_file.name}` (共 {len(df)} 条记录)")
                
                if st.button("📊 执行深度 AI 分析"):
                    with st.status("正在建立安全加密连接...", expanded=True) as status:
                        st.write("正在识别数据维度...")
                        st.write(f"正在调用 {MODEL_NAME} 进行双语翻译建模...")
                        
                        r_counts, sku_counts, keywords, trans_map = process_data(df)
                        
                        st.write("正在构建 ECharts 动态可视化...")
                        # 生成 ECharts 配置
                        echarts_option = generate_echarts_option(r_counts)
                        
                        status.update(label="✅ 分析引擎处理完成", state="complete", expanded=False)
                    
                    # === 1. ECharts 动态展示 ===
                    st.markdown("### 📈 退款原因动态分布 (ECharts)")
                    
                    # 在 Streamlit 中渲染 ECharts (HTML iframe 方式)
                    # 这样做的好处是保证了预览效果和下载报告的一致性
                    echarts_html_snippet = f"""
                    <div id="chart-container" style="width:100%; height:600px;"></div>
                    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
                    <script>
                        var chart = echarts.init(document.getElementById('chart-container'));
                        var option = {json.dumps(echarts_option)};
                        chart.setOption(option);
                    </script>
                    """
                    components.html(echarts_html_snippet, height=620)
                    
                    # === 2. 生成报告 (融合 ECharts) ===
                    html_report = generate_html_report(df, r_counts, sku_counts, keywords, trans_map, echarts_option)
                    
                    st.divider()
                    
                    # === 3. 下载按钮区 ===
                    col_down1, col_down2 = st.columns([2, 1])
                    with col_down1:
                        st.markdown("##### 📥 报告已就绪")
                        st.caption("点击右侧按钮下载包含 ECharts 动态图表的完整 HTML 报告。")
                    with col_down2:
                         st.download_button(
                            label="📥 下载完整 HTML 分析报告",
                            data=html_report,
                            file_name="Amazon_Refund_AI_Report.html",
                            mime="text/html",
                            type="primary",
                            use_container_width=True
                        )

                    if 'last_f' not in st.session_state or st.session_state.last_f != up_file.name:
                        log_action(st.session_state.user_name, st.session_state.user_dept, "执行分析任务", up_file.name)
                        st.session_state.last_f = up_file.name
        
        st.markdown("</div>", unsafe_allow_html=True)

# 底部填充
st.write("")
st.write("")

