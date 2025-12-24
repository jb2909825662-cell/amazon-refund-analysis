import streamlit as st
import pandas as pd
import json
from openai import OpenAI
import os
import datetime
import csv
import re
from collections import Counter
import streamlit.components.v1 as components

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
            /* 基础组件隐藏 */
            header[data-testid="stHeader"], [data-testid="stDecoration"], footer, [data-testid="stStatusWidget"] {
                display: none !important; visibility: hidden !important;
            }

            /* 右下角物理屏蔽层 */
            .terminal-shield {
                position: fixed; bottom: 0; right: 0; width: 220px; height: 50px;
                background: #0f172a; z-index: 2147483647; pointer-events: auto;
                display: flex; align-items: center; justify-content: center;
                border-top-left-radius: 15px; border-left: 1px solid #1e293b;
                box-shadow: -5px -5px 20px rgba(0,0,0,0.4);
            }
            .shield-text { color: #38bdf8; font-family: monospace; font-size: 11px; letter-spacing: 2px; font-weight: bold; }

            /* 专业级 UI 布局优化 */
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
if 'analyzed_history' not in st.session_state: st.session_state.analyzed_history = set()
if 'admin_access' not in st.session_state: st.session_state.admin_access = False 

# ================== 📝 日志系统 ==================
def init_log_file():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
            csv.writer(f).writerow(["时间", "姓名", "部门", "操作", "备注"])

def log_action(name, dept, action, note=""):
    try:
        init_log_file()
        cst_timezone = datetime.timezone(datetime.timedelta(hours=8))
        current_time = datetime.datetime.now(cst_timezone).strftime("%Y-%m-%d %H:%M:%S")
        
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
            csv.writer(f).writerow([current_time, name, dept, action, note])
    except Exception as e:
        print(f"日志记录失败: {e}")

# ================== 🎨 颜色算法 ==================
def get_traffic_color(value, min_val, max_val):
    if max_val == min_val: return "#e74c3c"
    ratio = (value - min_val) / (max_val - min_val)
    if ratio < 0.5:
        r = int(46 + (241 - 46) * (ratio * 2))
        g = int(204 + (196 - 204) * (ratio * 2))
        b = int(113 + (15 - 113) * (ratio * 2))
    else:
        r = int(241 + (231 - 241) * ((ratio - 0.5) * 2))
        g = int(196 + (76 - 196) * ((ratio - 0.5) * 2))
        b = int(15 + (60 - 15) * ((ratio - 0.5) * 2))
    return f"#{r:02x}{g:02x}{b:02x}"

# ================== AI 与 数据处理核心逻辑 ==================
def call_llm_translate(text_list, system_prompt):
    """通用的 LLM 翻译列表函数"""
    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=BASE_URL)
    # 扩大翻译列表长度限制，防止评论过多导致漏翻
    if len(text_list) > 100: text_list = text_list[:100]
    
    list_str = json.dumps(text_list)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": system_prompt}, 
                      {"role": "user", "content": f"Translate specific technical terms/comments to Chinese JSON format (Keep original as Key): {list_str}"}],
            temperature=0.1, response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content.strip())
    except: return {}

def format_bilingual(text, trans_map, mode='text'):
    text = str(text).strip()
    cn = trans_map.get(text)
    if cn and cn != text: 
        return f"{text}<br><span style='color:#888;font-size:0.9em'>({cn})</span>" if mode == 'html' else f"{text} ({cn})"
    return text

@st.cache_data(show_spinner=False)
def process_data(df):
    df.columns = [c.strip() for c in df.columns]
    
    # 1. 提取所有唯一退款原因 (去空格)
    unique_reasons = [str(r).strip() for r in df['reason'].dropna().unique()]
    
    # 2. 提前计算 Top 10 SKU
    sku_counts_raw = df['sku'].value_counts().reset_index().head(12)
    sku_counts_raw.columns = ['SKU', '退款数量']
    top_skus = sku_counts_raw['SKU'].tolist()
    
    # 3. 提取 Top SKU 相关的唯一客户评论
    relevant_comments = []
    if 'customer-comments' in df.columns:
        mask = df['sku'].isin(top_skus)
        # 关键修复：统一转换为字符串并去除首尾空格，确保key一致
        raw_comments = df[mask]['customer-comments'].dropna().unique().tolist()
        relevant_comments = [str(c).strip() for c in raw_comments if len(str(c)) > 2]

    # 4. 调用 AI
    with st.spinner("AI 正在解析原因与评论..."):
        # 翻译原因
        reason_map = call_llm_translate(unique_reasons, "你是一个亚马逊后台翻译专家。将列表中的退款原因翻译成中文JSON格式。")
        
        # 翻译评论
        comment_map = {}
        if relevant_comments:
            comment_map = call_llm_translate(relevant_comments, "你是一个亚马逊客服翻译。将列表中的客户抱怨/评论翻译成简练的中文JSON格式，保留原意。")
        
        # 合并字典
        full_trans_map = {**reason_map, **comment_map}

    # 5. 构建统计数据
    r_counts = df['reason'].value_counts().reset_index()
    r_counts.columns = ['原因_en', '数量']
    # 原因列处理时也去除空格
    r_counts['原因_clean'] = r_counts['原因_en'].apply(lambda x: str(x).strip())
    r_counts['原因_display'] = r_counts['原因_clean'].apply(lambda x: format_bilingual(x, full_trans_map, 'text'))
    r_counts['原因_html'] = r_counts['原因_clean'].apply(lambda x: format_bilingual(x, full_trans_map, 'html'))
    r_counts['占比'] = (r_counts['数量'] / len(df) * 100).round(2)
    r_counts = r_counts.sort_values('数量', ascending=True) 
    
    # 关键词提取
    keywords = []
    if 'customer-comments' in df.columns:
        stop_words = {'the','to','and','a','of','in','is','it','was','for','on','my','i','with','not','returned','item','amazon','unit','nan','this','that','but','have'}
        text = " ".join(df['customer-comments'].dropna().astype(str)).lower()
        words = re.findall(r'\w+', text)
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

    return r_counts, sku_counts_raw, Counter(keywords).most_common(12), full_trans_map

# ================== 📊 ECharts 图表构建器 ==================
def generate_echarts_option(df_counts):
    categories = df_counts['原因_display'].tolist()
    values = df_counts['数量'].tolist()
    min_v = min(values) if values else 0
    max_v = max(values) if values else 100
    
    data_with_style = []
    for v in values:
        color = get_traffic_color(v, min_v, max_v)
        data_with_style.append({
            "value": v,
            "itemStyle": {
                "color": color,
                "borderRadius": [0, 4, 4, 0]
            }
        })

    option = {
        "backgroundColor": "#ffffff",
        "animationDuration": 1500,
        "animationEasing": "cubicOut",
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "value", "boundaryGap": [0, 0.01], "splitLine": {"show": False}},
        "yAxis": {
            "type": "category", "data": categories,
            "axisLabel": {"fontSize": 14, "fontWeight": "bold", "color": "#333"},
            "axisTick": {"show": False}, "axisLine": {"show": False}
        },
        "series": [{
            "name": "退款数量", "type": "bar", "data": data_with_style, "barWidth": "60%",
            "label": {
                "show": True, "position": "insideRight", "formatter": "{c}",
                "color": "#ffffff", "fontSize": 20, "fontWeight": "bold", "padding": [0, 10, 0, 0]
            }
        }]
    }
    return option

# ================== HTML 报告生成器 (核心修复区域) ==================
def generate_html_report(df, reason_counts, sku_counts, keywords, trans_map, echarts_option):
    echarts_json = json.dumps(echarts_option)
    sorted_reasons = reason_counts.sort_values('数量', ascending=False)
    
    reason_rows = "".join([f"<tr><td style='text-align:left'>{r['原因_html']}</td><td>{r['数量']}</td><td>{r['占比']}%</td></tr>" for _, r in sorted_reasons.iterrows()])

    sku_tables = ""
    if not sku_counts.empty:
        top_skus = sku_counts.sort_values('退款数量', ascending=False).head(10)['SKU'].tolist()
        
        for sku in top_skus:
            sku_df = df[df['sku'] == sku]
            total = len(sku_df)
            
            # 使用 clean 过的列进行聚合，防止因为空格导致原因分裂
            sku_df['reason_clean'] = sku_df['reason'].astype(str).str.strip()
            
            sku_reason = sku_df['reason_clean'].value_counts().reset_index()
            sku_reason.columns = ['原因_clean', '频次']
            sku_reason['原因_html'] = sku_reason['原因_clean'].apply(lambda x: format_bilingual(x, trans_map, 'html'))
            sku_reason['占比'] = (sku_reason['频次'] / total * 100).round(2)
            
            rows_html = ""
            for _, row in sku_reason.iterrows():
                r_clean = row['原因_clean']
                
                # 提取评论
                comments_list = sku_df[sku_df['reason_clean'] == r_clean]['customer-comments'].dropna().tolist()
                
                if comments_list:
                    formatted_comments = []
                    for c in comments_list:
                        c_str = str(c).strip() # 再次确保去空格
                        c_trans = trans_map.get(c_str)
                        
                        # 核心修复：强制双语 HTML 结构
                        if c_trans and c_trans != c_str:
                            item_html = f"""
                            <div style="margin-bottom: 8px; border-bottom:1px dashed #eee; padding-bottom:4px;">
                                <span style="color:#333;">• {c_str}</span>
                                <div style="color:#e67e22; font-size:0.9em; margin-left:12px; margin-top:2px;">
                                    (CN: {c_trans})
                                </div>
                            </div>
                            """
                            formatted_comments.append(item_html)
                        else:
                            formatted_comments.append(f"<div style='margin-bottom: 6px; border-bottom:1px dashed #eee; padding-bottom:4px;'>• {c_str}</div>")
                    
                    comments_html_block = "".join(formatted_comments)
                    comments_cell = f"<div style='max-height:200px; overflow-y:auto; font-size:12px; line-height:1.4;'>{comments_html_block}</div>"
                else:
                    comments_cell = "<span style='color:#ccc'>- 无具体评论 -</span>"

                rows_html += f"""
                <tr>
                    <td style='text-align:left; vertical-align:top; width:20%'><b>{row['原因_html']}</b></td>
                    <td style='text-align:left; vertical-align:top; width:50%; background-color:#fafafa'>{comments_cell}</td>
                    <td style='vertical-align:top; width:15%'>{row['频次']}</td>
                    <td style='vertical-align:top; width:15%'>{row['占比']}%</td>
                </tr>
                """
            
            sku_tables += f"""
            <div style="background:white; padding:20px; border-radius:12px; margin-bottom:30px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #eee;">
                <h3 style="margin-top:0; color:#2c3e50; border-bottom:1px solid #eee; padding-bottom:10px;">
                    📦 SKU：{sku} 
                    <span style="font-weight:normal; font-size:0.8em; color:#666; float:right">总退款：{total} 单</span>
                </h3>
                <table style="width:100%">
                    <thead>
                        <tr>
                            <th>退款原因</th>
                            <th>客户评论 (Customer Comments)</th>
                            <th>频次</th>
                            <th>占比</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
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
            .container {{ max-width:1200px; margin:auto; background:white; padding:40px; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            h1 {{ text-align:center; border-bottom: 2px solid #eee; padding-bottom: 20px; color:#2c3e50; }}
            h2 {{ margin-top:50px; color:#6c5ce7; border-left:5px solid #6c5ce7; padding-left:15px; font-size: 22px; }}
            table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size: 14px; table-layout: fixed; }}
            th {{ background:#b94136; color:#ffffff; padding:12px; text-align:left; border: none; font-weight:600; }}
            td {{ padding:12px; border-bottom:1px solid #eee; word-wrap: break-word; }}
            .tag {{ display:inline-block; background:#e8f4f8; color:#2980b9; padding:6px 12px; margin:5px; border-radius:4px; font-size:13px; }}
            #main-chart {{ width: 100%; height: 650px; margin-bottom: 40px; border: 1px solid #f0f0f0; border-radius: 8px; padding: 10px; }}
            
            /* 滚动条美化 */
            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: #f1f1f1; }}
            ::-webkit-scrollbar-thumb {{ background: #c1c1c1; border-radius: 3px; }}
            ::-webkit-scrollbar-thumb:hover {{ background: #a8a8a8; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Amazon 退款分析报告 (AI 深度解析版)</h1>
            <h2>1. 可视化分析概览</h2>
            <div id="main-chart"></div>
            <script type="text/javascript">
                var myChart = echarts.init(document.getElementById('main-chart'));
                var option = {echarts_json};
                myChart.setOption(option);
                window.addEventListener('resize', function() {{ myChart.resize(); }});
            </script>
            <h2>2. 全局退款原因分布表</h2>
            <table><tr><th style="width:60%">退款原因 (Original / CN)</th><th>频次</th><th>占比</th></tr>{reason_rows}</table>
            <h2>3. 重点 SKU 详细分析 (TOP 10)</h2>
            <p style="color:#666; font-size:14px; margin-bottom:20px;">* 下表已自动聚合每个SKU在特定退款原因下的具体客户评论，并附带AI中文翻译。</p>
            {sku_tables}
            <h2>4. 客户评论高频词云</h2><div style="line-height:1.8;">{kw_html}</div>
        </div>
    </body>
    </html>
    """

# ================== UI 主界面 ==================
st.markdown("<h1 style='text-align:center; color:#0f172a; margin: 40px 0;'>🛡️ Amazon 退款智能分析终端 (Pro)</h1>", unsafe_allow_html=True)

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
            
            if not st.session_state.admin_access:
                pwd = st.text_input("管理权证 (Password)", type="password", placeholder="Admin Key", key="admin_pwd_input")
                
                if st.button("🔓 验证身份", use_container_width=True):
                    if pwd == ADMIN_PASSWORD:
                        st.session_state.admin_access = True
                        st.rerun() 
                    else:
                        st.error("🚫 权限拒绝：密码错误")
            else:
                st.markdown("<style>.terminal-shield{display:none !important;}</style>", unsafe_allow_html=True)
                st.success("✅ 管理员身份已验证")
                
                if os.path.exists(LOG_FILE):
                    df_log = pd.read_csv(LOG_FILE)
                    csv_data = df_log.to_csv(index=False).encode('utf-8-sig')
                    
                    st.download_button(
                        label="📥 导出全量访问日志",
                        data=csv_data,
                        file_name="access_log.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.warning("暂无日志文件")
                
                st.write("")
                if st.button("🔒 退出管理", type="secondary", use_container_width=True):
                    st.session_state.admin_access = False
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
else:
    with st.container():
        st.markdown("<div class='main-card'>", unsafe_allow_html=True)
        c_status1, c_status2 = st.columns([3, 1])
        with c_status1: st.info(f"🟢 **当前节点已授权：** {st.session_state.user_dept} | {st.session_state.user_name}")
        with c_status2:
            if st.button("🔄 退出/切换用户"):
                st.session_state.confirmed = False
                st.rerun()
        st.markdown("---")
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
                except Exception: st.error("文件编码识别失败")
            except pd.errors.EmptyDataError: st.error("❌ 上传的文件内容为空！")
            except Exception as e: st.error(f"❌ 文件读取发生未知错误: {e}")
            
            if df is not None:
                st.success(f"数据已载入：`{up_file.name}` (共 {len(df)} 条记录)")
                
                if st.button("📊 执行深度 AI 分析"):
                    with st.status("正在建立安全加密连接...", expanded=True) as status:
                        st.write("正在识别数据维度...")
                        st.write(f"正在调用 {MODEL_NAME} 进行双语翻译建模（包含原因与评论）...")
                        r_counts, sku_counts, keywords, trans_map = process_data(df)
                        st.write("正在构建 ECharts 动态可视化...")
                        echarts_option = generate_echarts_option(r_counts)
                        
                        file_signature = f"{up_file.name}_{up_file.size}"
                        if file_signature not in st.session_state.analyzed_history:
                            log_action(st.session_state.user_name, st.session_state.user_dept, "执行分析任务", up_file.name)
                            st.session_state.analyzed_history.add(file_signature)
                        
                        status.update(label="✅ 分析引擎处理完成", state="complete", expanded=False)
                    
                    st.markdown("### 📈 退款原因动态分布 (ECharts)")
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
                    html_report = generate_html_report(df, r_counts, sku_counts, keywords, trans_map, echarts_option)
                    
                    st.divider()
                    col_down1, col_down2 = st.columns([2, 1])
                    with col_down1:
                        st.markdown("##### 📥 报告已就绪")
                        st.caption("点击右侧按钮下载包含 ECharts 动态图表和 TOP 10 SKU 详情的完整 HTML 报告。")
                    with col_down2:
                         st.download_button(
                            label="📥 下载完整 HTML 分析报告",
                            data=html_report,
                            file_name="Amazon_Refund_AI_Report.html",
                            mime="text/html",
                            type="primary",
                            use_container_width=True
                        )
        
        st.markdown("</div>", unsafe_allow_html=True)
st.write(""); st.write("")
