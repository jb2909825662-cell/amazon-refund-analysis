import streamlit as st
import pandas as pd
import json
from openai import OpenAI
import os
import datetime
import csv
import re
import time  # 新增 time 模块用于重试延迟
from collections import Counter
import streamlit.components.v1 as components

# ================== 🛠️ 配置区域 ==================
SILICONFLOW_API_KEY = "sk-wmbipxzixpvwddjoisctfpsdwneznyliwoxgxbbzcdrvaiye" 
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
ADMIN_PASSWORD = "dhzjb" 
BASE_URL = "https://api.siliconflow.cn/v1"
LOG_FILE = "access_log.csv"
# 🔥 修复：使用国内极速 CDN (Staticfile)
ECHARTS_CDN = "https://cdn.staticfile.net/echarts/5.4.3/echarts.min.js"

# 页面配置
st.set_page_config(page_title="Amazon 智能分析终端", layout="wide", page_icon="🛡️")

# ================== 🛡️ 【极速封印：UI 优化】 ==================
def apply_ultra_mask():
    st.markdown("""
        <style>
            header[data-testid="stHeader"], [data-testid="stDecoration"], footer, [data-testid="stStatusWidget"] {
                display: none !important; visibility: hidden !important;
            }
            .stApp { background: #f8fafc; }
            .main-card {
                background: white; padding: 40px; border-radius: 24px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.06); border: 1px solid #f1f5f9;
                margin-bottom: 20px;
            }
            .stButton>button {
                border-radius: 12px !important; height: 48px;
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
                color: white !important; font-weight: bold !important; border: none !important;
            }
            .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.25); }
        </style>
    """, unsafe_allow_html=True)
    
    # JS 隐藏逻辑
    st.html("""
        <script>
            const hideTarget = () => {
                const els = window.parent.document.querySelectorAll('.stAppToolbar, [data-testid="stAppToolbar"]');
                els.forEach(el => { el.style.display = 'none'; });
            };
            setInterval(hideTarget, 100);
        </script>
    """)

apply_ultra_mask()

# ================== 初始化状态管理 ==================
if 'confirmed' not in st.session_state: st.session_state.confirmed = False
if 'analyzed_history' not in st.session_state: st.session_state.analyzed_history = set()
if 'admin_access' not in st.session_state: st.session_state.admin_access = False 

# ================== 📝 日志系统 ==================
def log_action(name, dept, action, note=""):
    try:
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, mode='w', newline='', encoding='utf-8-sig') as f:
                csv.writer(f).writerow(["时间", "姓名", "部门", "操作", "备注"])
        
        cst_timezone = datetime.timezone(datetime.timedelta(hours=8))
        current_time = datetime.datetime.now(cst_timezone).strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
            csv.writer(f).writerow([current_time, name, dept, action, note])
    except: pass

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

# ================== 🧠 AI 核心逻辑 (带重试机制) ==================
def call_llm_translate(text_list, system_prompt, max_retries=3):
    """
    通用 LLM 翻译函数，包含重试机制
    """
    client = OpenAI(api_key=SILICONFLOW_API_KEY, base_url=BASE_URL)
    
    # 限制单次请求量，防止Token溢出
    if len(text_list) > 80: text_list = text_list[:80]
    list_str = json.dumps(text_list, ensure_ascii=False)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt}, 
                    {"role": "user", "content": f"请直接返回标准JSON格式，不要包含Markdown标记。将以下内容翻译为中文(Key为原文, Value为中文): {list_str}"}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            
            # 清洗 Markdown 标记
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[0].strip()

            result = json.loads(content)
            
            if isinstance(result, dict) and len(result) > 0:
                return result # 成功返回
            
        except Exception as e:
            print(f"尝试 {attempt+1}/{max_retries} 失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(1.5) # 失败后冷却1.5秒
            else:
                return {} # 所有重试失败，返回空字典
    return {}

def get_translation_fuzzy(text, trans_map):
    """
    模糊匹配翻译，提高命中率
    """
    text_clean = str(text).strip()
    # 1. 直接匹配
    if text_clean in trans_map:
        return trans_map[text_clean]
    
    # 2. 忽略大小写匹配
    text_lower = text_clean.lower()
    for k, v in trans_map.items():
        if str(k).strip().lower() == text_lower:
            return v
            
    return text_clean # 没找到则返回原文

def format_bilingual(text, trans_map, mode='text'):
    """
    格式化双语输出，保证字体一致性
    """
    text = str(text).strip()
    cn = get_translation_fuzzy(text, trans_map)
    
    # 如果原文和翻译一样（或者没翻译出来），为了格式整齐，显示两次或显示提示
    if cn == text:
        # 如果是英文句子，但没翻译出来，我们就不显示中文括号了，避免重复
        # 但用户要求"保证显示"，这里可以做一个策略：
        # 如果看起来像英文，就强行显示。但最稳妥是如果没翻译，就不显示括号
        display_cn = ""
    else:
        display_cn = cn

    if mode == 'html':
        # 🔥 核心修改：统一字体大小，使用 span 保证行内元素
        if display_cn:
            return f"""
            <span style="font-family:sans-serif; font-size:14px; color:#2c3e50; font-weight:600;">{text}</span>
            <br>
            <span style="font-family:sans-serif; font-size:14px; color:#d35400; font-weight:normal;">({display_cn})</span>
            """
        else:
            return f'<span style="font-family:sans-serif; font-size:14px; color:#2c3e50; font-weight:600;">{text}</span>'
            
    else:
        return f"{text} ({display_cn})" if display_cn else text

@st.cache_data(show_spinner=False)
def process_data(df):
    df.columns = [c.strip() for c in df.columns]
    
    # 1. 提取所有需要翻译的退款原因
    unique_reasons = [str(r).strip() for r in df['reason'].dropna().unique()]
    
    # 2. 提取 TOP SKU 的评论（减少 Token 消耗，只翻译重要的）
    sku_counts_raw = df['sku'].value_counts().reset_index().head(12)
    sku_counts_raw.columns = ['SKU', '退款数量']
    top_skus = sku_counts_raw['SKU'].tolist()
    
    relevant_comments = []
    if 'customer-comments' in df.columns:
        mask = df['sku'].isin(top_skus)
        raw_comments = df[mask]['customer-comments'].dropna().unique().tolist()
        # 过滤掉太短的无意义评论
        relevant_comments = [str(c).strip() for c in raw_comments if len(str(c)) > 3]

    with st.spinner("AI 正在重试连接并解析原因与评论..."):
        # 调用带重试机制的翻译
        reason_map = call_llm_translate(unique_reasons, "你是一个亚马逊后台专家。将退款原因翻译成中文JSON格式。Key是英文原文，Value是中文翻译。")
        
        comment_map = {}
        if relevant_comments:
            comment_map = call_llm_translate(relevant_comments, "你是一个客服专家。将客户抱怨翻译成简练的中文JSON格式，Key是原文，Value是中文。")
        
        full_trans_map = {**reason_map, **comment_map}

    # 处理统计数据
    r_counts = df['reason'].value_counts().reset_index()
    r_counts.columns = ['原因_en', '数量']
    r_counts['原因_clean'] = r_counts['原因_en'].apply(lambda x: str(x).strip())
    
    # 生成 HTML 显示列
    r_counts['原因_html'] = r_counts['原因_clean'].apply(lambda x: format_bilingual(x, full_trans_map, 'html'))
    # 生成图表显示列 (纯文本)
    r_counts['原因_display'] = r_counts['原因_clean'].apply(lambda x: format_bilingual(x, full_trans_map, 'text'))
    
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
            "itemStyle": {"color": color, "borderRadius": [0, 4, 4, 0]}
        })

    option = {
        "backgroundColor": "#ffffff",
        "animationDuration": 1500,
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {"type": "value", "boundaryGap": [0, 0.01]},
        "yAxis": {
            "type": "category", "data": categories,
            "axisLabel": {"fontSize": 12, "fontWeight": "bold", "color": "#333", "interval": 0}
        },
        "series": [{
            "type": "bar", "data": data_with_style, "barWidth": "60%",
            "label": {
                "show": True, "position": "insideRight", "formatter": "{c}",
                "color": "#ffffff", "fontSize": 14, "fontWeight": "bold", "padding": [0, 5, 0, 0]
            }
        }]
    }
    return option

# ================== HTML 报告生成器 (UI 优化版) ==================
def generate_html_report(df, reason_counts, sku_counts, keywords, trans_map, echarts_option):
    echarts_json = json.dumps(echarts_option)
    sorted_reasons = reason_counts.sort_values('数量', ascending=False)
    
    # 表格行生成：确保每一行都应用了 format_bilingual_html 的样式
    reason_rows = "".join([f"""
    <tr>
        <td style='text-align:left; padding: 12px;'>{r['原因_html']}</td>
        <td style='font-size:14px;'>{r['数量']}</td>
        <td style='font-size:14px;'>{r['占比']}%</td>
    </tr>
    """ for _, r in sorted_reasons.iterrows()])

    sku_tables = ""
    if not sku_counts.empty:
        top_skus = sku_counts.sort_values('退款数量', ascending=False).head(10)['SKU'].tolist()
        
        for sku in top_skus:
            sku_df = df[df['sku'] == sku]
            total = len(sku_df)
            sku_df['reason_clean'] = sku_df['reason'].astype(str).str.strip()
            
            sku_reason = sku_df['reason_clean'].value_counts().reset_index()
            sku_reason.columns = ['原因_clean', '频次']
            sku_reason['原因_html'] = sku_reason['原因_clean'].apply(lambda x: format_bilingual(x, trans_map, 'html'))
            sku_reason['占比'] = (sku_reason['频次'] / total * 100).round(2)
            
            rows_html = ""
            for _, row in sku_reason.iterrows():
                r_clean = row['原因_clean']
                comments_list = sku_df[sku_df['reason_clean'] == r_clean]['customer-comments'].dropna().tolist()
                
                # 评论区域渲染
                if comments_list:
                    formatted_comments = []
                    for c in comments_list:
                        c_str = str(c).strip()
                        # 使用模糊匹配查找翻译
                        c_trans = get_translation_fuzzy(c_str, trans_map)
                        
                        # 构建一致字体大小的评论块
                        if c_trans and c_trans != c_str:
                            item_html = f"""
                            <div style="margin-bottom: 8px; border-bottom:1px dashed #eee; padding-bottom:6px;">
                                <div style="font-size:13px; color:#333; font-weight:600; line-height:1.4;">• {c_str}</div>
                                <div style="font-size:13px; color:#e67e22; margin-top:2px; line-height:1.4;">(译: {c_trans})</div>
                            </div>
                            """
                        else:
                            item_html = f"<div style='margin-bottom:6px; border-bottom:1px dashed #eee; padding-bottom:4px; font-size:13px; color:#333;'>• {c_str}</div>"
                        formatted_comments.append(item_html)
                    
                    comments_cell = f"<div style='max-height:250px; overflow-y:auto;'>{''.join(formatted_comments)}</div>"
                else:
                    comments_cell = "<span style='color:#ccc; font-size:13px;'>- 无具体评论 -</span>"

                rows_html += f"""
                <tr>
                    <td style='text-align:left; vertical-align:top; width:25%; background:#fff;'>{row['原因_html']}</td>
                    <td style='text-align:left; vertical-align:top; width:55%; background:#fafafa;'>{comments_cell}</td>
                    <td style='vertical-align:top; width:10%; font-size:14px;'>{row['频次']}</td>
                    <td style='vertical-align:top; width:10%; font-size:14px;'>{row['占比']}%</td>
                </tr>
                """
            
            sku_tables += f"""
            <div style="background:white; padding:20px; border-radius:12px; margin-bottom:30px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); border: 1px solid #eee;">
                <h3 style="margin-top:0; color:#2c3e50; border-bottom:1px solid #eee; padding-bottom:10px;">
                    📦 SKU：{sku} <span style="font-weight:normal; font-size:0.8em; color:#666; float:right">Total: {total}</span>
                </h3>
                <table>
                    <thead>
                        <tr><th>退款原因 (Reason)</th><th>客户评论 (Comments)</th><th>频次</th><th>占比</th></tr>
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
        <script src="{ECHARTS_CDN}"></script>
        <style>
            body {{ font-family: "Microsoft YaHei", "Segoe UI", sans-serif; background:#f4f7f6; padding:40px; color:#333; }}
            .container {{ max-width:1200px; margin:auto; background:white; padding:40px; border-radius:12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }}
            h1 {{ text-align:center; border-bottom: 2px solid #eee; padding-bottom: 20px; color:#2c3e50; }}
            h2 {{ margin-top:50px; color:#2980b9; border-left:5px solid #2980b9; padding-left:15px; font-size: 20px; }}
            table {{ width:100%; border-collapse:collapse; margin-top:10px; table-layout: fixed; }}
            th {{ background:#f1f2f6; color:#2c3e50; padding:12px; text-align:left; border-bottom: 2px solid #ddd; font-weight:bold; font-size:14px; }}
            td {{ padding:10px; border-bottom:1px solid #eee; word-wrap: break-word; }}
            .tag {{ display:inline-block; background:#e8f4f8; color:#2980b9; padding:6px 12px; margin:5px; border-radius:4px; font-size:13px; }}
            #main-chart {{ width: 100%; height: 650px; margin-bottom: 40px; border: 1px solid #f0f0f0; border-radius: 8px; padding: 10px; }}
            /* 滚动条美化 */
            ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
            ::-webkit-scrollbar-track {{ background: #f1f1f1; }}
            ::-webkit-scrollbar-thumb {{ background: #c1c1c1; border-radius: 3px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Amazon 退款分析报告 (Pro版)</h1>
            <h2>1. 可视化分析概览</h2>
            <div id="main-chart"></div>
            <script type="text/javascript">
                var myChart = echarts.init(document.getElementById('main-chart'));
                var option = {echarts_json};
                myChart.setOption(option);
                window.addEventListener('resize', function() {{ myChart.resize(); }});
            </script>
            
            <h2>2. 全局退款原因分布表</h2>
            <table>
                <thead><tr><th style="width:60%">退款原因 (Reason / CN)</th><th>频次</th><th>占比</th></tr></thead>
                <tbody>{reason_rows}</tbody>
            </table>
            
            <h2>3. 重点 SKU 详细分析 (TOP 10)</h2>
            {sku_tables}
            
            <h2>4. 客户评论高频词云</h2>
            <div style="line-height:1.8;">{kw_html}</div>
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
            u_name = st.text_input("您的姓名", placeholder="例如：张三")
            u_dept = st.text_input("所属部门", placeholder="例如：运营一部")
            if st.button("🚀 初始化分析终端并进入"):
                if u_name and u_dept:
                    st.session_state.user_name = u_name
                    st.session_state.user_dept = u_dept
                    st.session_state.confirmed = True
                    log_action(u_name, u_dept, "终端初始化成功")
                    st.rerun()
                else: st.warning("⚠️ 请完整填写姓名和部门以继续")
        
        with col2:
            st.markdown("#### 🔐 管理员权限")
            if not st.session_state.admin_access:
                pwd = st.text_input("管理权证 (Password)", type="password", key="admin_pwd_input")
                if st.button("🔓 验证身份", use_container_width=True):
                    if pwd == ADMIN_PASSWORD:
                        st.session_state.admin_access = True
                        st.rerun() 
                    else: st.error("🚫 密码错误")
            else:
                st.success("✅ 管理员身份已验证")
                if os.path.exists(LOG_FILE):
                    df_log = pd.read_csv(LOG_FILE)
                    st.download_button("📥 导出日志", df_log.to_csv(index=False).encode('utf-8-sig'), "log.csv", "text/csv")
                if st.button("🔒 退出管理"):
                    st.session_state.admin_access = False
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
else:
    with st.container():
        st.markdown("<div class='main-card'>", unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        with c1: st.info(f"🟢 **当前节点：** {st.session_state.user_dept} | {st.session_state.user_name}")
        with c2: 
            if st.button("🔄 切换用户"): 
                st.session_state.confirmed = False
                st.rerun()
        
        st.markdown("#### 📂 载入 Amazon 数据源")
        up_file = st.file_uploader("请拖拽或选择 CSV 文件", type="csv")
        
        if up_file:
            try:
                df = pd.read_csv(up_file)
            except:
                try: df = pd.read_csv(up_file, encoding='gbk')
                except: df = pd.DataFrame()
            
            if not df.empty:
                st.success(f"已载入 {len(df)} 条记录")
                if st.button("📊 执行 AI 深度分析 (含重试保障)"):
                    with st.status("🚀 正在启动分析引擎...", expanded=True) as status:
                        st.write("📡 连接 AI 翻译接口 (自动重试模式)...")
                        r_counts, sku_counts, keywords, trans_map = process_data(df)
                        
                        st.write("📊 构建可视化图表...")
                        echarts_option = generate_echarts_option(r_counts)
                        
                        log_action(st.session_state.user_name, st.session_state.user_dept, "分析完成", up_file.name)
                        status.update(label="✅ 分析完成！", state="complete", expanded=False)
                    
                    # 预览图表
                    echarts_html = f"""
                    <div id="chart" style="width:100%;height:500px;"></div>
                    <script src="{ECHARTS_CDN}"></script>
                    <script>echarts.init(document.getElementById('chart')).setOption({json.dumps(echarts_option)})</script>
                    """
                    components.html(echarts_html, height=520)
                    
                    # 生成报告
                    html_report = generate_html_report(df, r_counts, sku_counts, keywords, trans_map, echarts_option)
                    st.download_button("📥 下载完整 HTML 报告 (中英对照版)", html_report, "Amazon_Report_Pro.html", "text/html", type="primary")

        st.markdown("</div>", unsafe_allow_html=True)
