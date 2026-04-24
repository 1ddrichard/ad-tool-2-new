import streamlit as st
import pandas as pd
import io
import zipfile
import json
import os
from datetime import datetime
import xlwt

# =========================================================================
# 1. 初始化配置与数据加载
# =========================================================================

def load_configurations():
    """读取配置文件并加载CSV模版数据"""
    config_path = 'config.json'
    
    # 检查配置文件是否存在
    if not os.path.exists(config_path):
        st.error(f"❌ 配置文件丢失: {config_path}")
        return {}

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = json.load(f)
        
        # 遍历配置，加载对应的 CSV 文件
        for channel, data in raw_config.items():
            csv_file = data.get("file_path")
            if os.path.exists(csv_file):
                # 读取 CSV，无表头模式
                df = pd.read_csv(csv_file, header=None)
                # 为 DataFrame 赋予列名（用于后续处理或调试，虽然后续逻辑主要是按行处理）
                if "columns" in data and len(data["columns"]) == len(df.columns):
                    df.columns = data["columns"]
                
                # 将数据转为字典列表存储在 rows 字段中，保持原有逻辑兼容
                data["rows"] = df.to_dict(orient="records")
            else:
                st.warning(f"⚠️ 渠道 [{channel}] 的模版文件未找到: {csv_file}")
                data["rows"] = []
                
        return raw_config
    except Exception as e:
        st.error(f"加载配置失败: {e}")
        return {}

# 加载数据 (使用 st.cache_data 避免每次刷新都重读 IO)
@st.cache_data
def get_raw_data():
    return load_configurations()

RAW_DATA = get_raw_data()

# =========================================================================
# 2. 核心处理逻辑
# =========================================================================

def clean_val(val):
    if pd.isna(val) or val == "":
        return ""
    s_val = str(val)
    # 清理零宽字符 (Zero-Width Space, Zero-Width Non-Joiner 等)
    s_val = s_val.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
    if s_val.endswith(".0"):
        return s_val[:-2]
    return s_val

# Appid 管理导入模板：广告ID开头 → 变现平台/账号ID 映射
PLATFORM_MAP = {
    "5": {"platform": "headline", "account_id": "61887"},
    "1": {"platform": "GDT", "account_id": "1846680534"},
    "2": {"platform": "kuaishou", "account_id": "25458"},
}

def get_platform_info(ad_id):
    """根据广告ID开头数字判断变现平台"""
    ad_id_str = str(ad_id).strip()
    if ad_id_str:
        first_char = ad_id_str[0]
        if first_char in PLATFORM_MAP:
            return PLATFORM_MAP[first_char]
    return None

def get_channel_platform_prefix(channel_name):
    """根据渠道名称返回对应的广告ID开头数字"""
    ch_lower = channel_name.lower()
    if "穿山甲" in ch_lower:
        return "5"
    elif "优量汇" in ch_lower:
        return "1"
    elif "快手" in ch_lower:
        return "2"
    return None

def create_appid_xls(rows_data):
    """生成 Appid 管理导入模板 xls"""
    output = io.BytesIO()
    workbook = xlwt.Workbook(encoding='utf-8')
    worksheet = workbook.add_sheet('Sheet1')
    
    headers = ["应用", "变现平台", "子渠道", "账号id", "tappid", "备注"]
    for col_idx, header in enumerate(headers):
        worksheet.write(0, col_idx, header)
    
    for row_idx, row in enumerate(rows_data):
        for col_idx, val in enumerate(row):
            # 数字列转为整数写入
            if isinstance(val, str) and val.isdigit():
                worksheet.write(row_idx + 1, col_idx, int(val))
            else:
                worksheet.write(row_idx + 1, col_idx, val)
    
    workbook.save(output)
    output.seek(0)
    return output

def process_rows(channel, p_name, p_id, t_id):
    """根据用户输入，深度复制模板行并替换关键字段"""
    template_conf = RAW_DATA.get(channel)
    if not template_conf or not template_conf.get("rows"):
        return pd.DataFrame()

    rows = template_conf["rows"]
    sample_name = template_conf["sample_name"]
    sample_pid = template_conf["sample_pid"]
    sample_adid = template_conf["sample_adid"]
    columns = template_conf["columns"]
    
    new_rows = []
    for r in rows:
        new_row = r.copy()
        
        # 遍历该行的所有列进行替换
        for k, v in new_row.items():
            val_str = clean_val(v)
            
            # 替换逻辑
            if sample_pid in val_str:
                val_str = val_str.replace(sample_pid, str(p_id))
            if sample_adid in val_str:
                val_str = val_str.replace(sample_adid, str(t_id))
            if sample_name in val_str:
                val_str = val_str.replace(sample_name, p_name)
                
            new_row[k] = val_str
            
        new_rows.append(new_row)
        
    # 确保列顺序一致
    return pd.DataFrame(new_rows, columns=columns)

def create_xls_file(df):
    output = io.BytesIO()
    workbook = xlwt.Workbook(encoding='utf-8')
    worksheet = workbook.add_sheet('Sheet1')
    
    # 写入表头
    for col_idx, header in enumerate(df.columns):
        worksheet.write(0, col_idx, header)
    
    # 写入数据行
    for row_idx, row_data in df.iterrows():
        for col_idx, value in enumerate(row_data):
            val = value
            if isinstance(val, str):
                val_stripped = val.strip()
                try:
                    f_val = float(val_stripped)
                    if f_val.is_integer():
                        val = int(f_val)
                    else:
                        val = f_val
                except (ValueError, TypeError):
                    pass
            worksheet.write(row_idx + 1, col_idx, val)
            
    workbook.save(output)
    output.seek(0)
    return output

# =========================================================================
# 3. Streamlit 界面
# =========================================================================
st.set_page_config(page_title="广告配置生成器", layout="wide")
# =========================================================================
# 👇👇👇 在这里添加隐藏代码 👇👇👇
# =========================================================================
hide_streamlit_style = """
    <style>
    .stDeployButton {
        visibility: hidden;
    }
    footer {
        visibility: hidden;
    }
    header {
        visibility: hidden;
    }
    /* 隐藏右下角 Streamlit Community Cloud 悬浮图标 */
    ._profileContainer_gzau3_53 {
        visibility: hidden;
    }
    [data-testid="manage-app-button"] {
        visibility: hidden;
    }
    .viewerBadge_container__r5tak {
        visibility: hidden;
    }
    div[class*="StatusWidget"] {
        visibility: hidden;
    }
    iframe[title="chat"] {
        display: none;
    }
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
# =========================================================================
st.title("广告配置自动化工具")

# 侧边栏说明
# 侧边栏说明
with st.sidebar:
    # 版本信息
    st.markdown("### 📋 工具信息")
    st.markdown("**版本:** v1.3.0 · 2026-04-21")
    with st.expander("📝 更新日志"):
        st.markdown("""
**v1.3.0** (2026-04-21)
- 广告ID智能匹配渠道（5开头=穿山甲、1开头=优量汇、2开头=快手）
- 自动生成 Appid 管理导入模板，随配置文件一起打包下载
- 选择多渠道时校验是否都有对应广告ID

**v1.2.1** (2026-03-11)
- 恢复 .xls 格式输出，兼容公司后台上传

**v1.2.0** (2026-03-10)
- 新增穿山甲new50/优量汇new50渠道模板
- 移除旧版穿山甲new1/优量汇new2
- 隐藏右下角 Streamlit 悬浮图标

**v1.1.0** (2026-03-06)
- 修复穿山甲new1/优量汇new2配置替换失效
- 输出格式从 .xls 升级为 .xlsx
- 新增输入校验（非空/纯数字检查）
- 修复 CSV 模板零宽字符问题

**v1.0.0** (初始版本)
- 支持穿山甲/优量汇/快手渠道
- 批量生成广告配置文件
        """)
    
    st.markdown("---")
    
    # 使用说明
    with st.expander("📖 使用说明"):
        st.markdown("""
1. **选择渠道** — 勾选需要生成配置的广告平台
2. **填写产品信息** — 在表格中输入产品ID、名称、广告ID（均为纯数字）
3. **批量生成** — 点击生成按钮，下载包含所有配置的 zip 包
4. 支持多行输入，一次生成多个产品的配置

⚠️ 产品ID和广告ID请从对应平台后台获取
        """)
    
    st.markdown("---")
    
    # 模板下载
    with st.expander("📁 模板 CSV 下载"):
        if RAW_DATA:
            for ch, data in RAW_DATA.items():
                csv_path = data.get("file_path", "")
                if os.path.exists(csv_path):
                    with open(csv_path, 'rb') as f:
                        st.download_button(
                            label=f"⬇️ {ch}",
                            data=f.read(),
                            file_name=os.path.basename(csv_path),
                            mime="text/csv",
                            key=f"dl_{ch}"
                        )
                else:
                    st.caption(f"{ch}: 文件不存在")
    
    st.markdown("---")
    
    # 配置加载状态
    st.info("配置加载状态：")
    if RAW_DATA:
        for ch in RAW_DATA.keys():
            row_count = len(RAW_DATA[ch].get('rows', []))
            note = RAW_DATA[ch].get('note', '')
            label = f"{ch} ({note})" if note else ch
            st.success(f"✅ {label}: {row_count} 条模版")
    else:
        st.error("❌ 未加载到任何配置，请检查 json 文件。")

# 1. 选择渠道 (按钮式多选)
st.subheader("1. 选择广告渠道")
available_channels = list(RAW_DATA.keys()) if RAW_DATA else []

# 初始化选中状态
if 'selected_channels' not in st.session_state:
    st.session_state.selected_channels = set()

# 按钮点击切换选中状态
cols = st.columns(min(len(available_channels), 4)) if available_channels else []
for i, ch in enumerate(available_channels):
    col = cols[i % min(len(available_channels), 4)]
    note = RAW_DATA[ch].get('note', '')
    label = f"{ch}\n({note})" if note else ch
    is_selected = ch in st.session_state.selected_channels
    
    with col:
        if is_selected:
            if st.button(f"✅ {label}", key=f"ch_{ch}", use_container_width=True):
                st.session_state.selected_channels.discard(ch)
                st.rerun()
        else:
            if st.button(f"⬜ {label}", key=f"ch_{ch}", use_container_width=True):
                st.session_state.selected_channels.add(ch)
                st.rerun()

selected_channels = list(st.session_state.selected_channels)

if selected_channels:
    st.caption(f"已选择: {', '.join(selected_channels)}")
else:
    st.caption("请点击上方按钮选择渠道")

# 2. 输入表格
st.subheader("2. 批量输入产品信息")
st.caption("直接从管理表复制粘贴即可，对应平台的广告ID留空则不生成该平台配置")

if 'input_df' not in st.session_state:
    st.session_state.input_df = pd.DataFrame([{
        "应用ID": "", 
        "应用名称": "", 
        "穿山甲appid": "",
        "优量汇appid": "",
        "快手appid": "",
    }])

edited_df = st.data_editor(
    st.session_state.input_df,
    num_rows="dynamic",
    column_config={
        "应用ID": st.column_config.TextColumn("应用ID", help="产品的应用ID"),
        "应用名称": st.column_config.TextColumn("应用名称", help="产品的中文名称"),
        "穿山甲appid": st.column_config.TextColumn("穿山甲appid", help="穿山甲广告位ID（5开头）"),
        "优量汇appid": st.column_config.TextColumn("优量汇appid", help="优量汇广告位ID（1开头）"),
        "快手appid": st.column_config.TextColumn("快手appid", help="快手广告位ID（2开头）"),
    }
)

# 平台列 → 渠道名前缀 + 广告ID前缀 映射
COLUMN_PLATFORM = {
    "穿山甲appid": {"prefix": "5", "keyword": "穿山甲"},
    "优量汇appid": {"prefix": "1", "keyword": "优量汇"},
    "快手appid":   {"prefix": "2", "keyword": "快手"},
}

# 3. 生成
st.markdown("---")
if st.button("🚀 立即生成配置文档", type="primary"):
    if not selected_channels:
        st.error("请至少选择一个渠道！")
    elif edited_df.empty:
        st.error("请填写产品信息！")
    else:
        # 输入校验
        has_error = False
        seen_ids = {}  # 用于重复检测: {id_value: [(行号, 列名), ...]}
        
        for idx, row in edited_df.iterrows():
            app_name = str(row.get("应用名称", "")).strip()
            app_id = str(row.get("应用ID", "")).strip()
            
            if not app_id or app_id == "nan":
                st.error(f"第 {idx+1} 行：应用ID不能为空")
                has_error = True
            elif not app_id.isdigit():
                st.error(f"第 {idx+1} 行：应用ID必须为纯数字，当前值: {app_id}")
                has_error = True
            else:
                # 检查应用ID重复
                key = f"应用ID:{app_id}"
                if key in seen_ids:
                    seen_ids[key].append((idx+1, "应用ID"))
                else:
                    seen_ids[key] = [(idx+1, "应用ID")]
            
            if not app_name or app_name == "nan":
                st.error(f"第 {idx+1} 行：应用名称不能为空")
                has_error = True
            
            # 校验每个平台的 appid
            has_any_adid = False
            for col_name, info in COLUMN_PLATFORM.items():
                ad_id = str(row.get(col_name, "")).strip()
                if ad_id and ad_id != "nan":
                    has_any_adid = True
                    if not ad_id.isdigit():
                        st.error(f"第 {idx+1} 行 [{col_name}]：必须为纯数字，当前值: {ad_id}")
                        has_error = True
                    elif ad_id[0] != info["prefix"]:
                        st.error(f"第 {idx+1} 行 [{col_name}]：应以 {info['prefix']} 开头，当前值: {ad_id}")
                        has_error = True
                    else:
                        # 检查广告ID重复
                        key = f"{col_name}:{ad_id}"
                        if key in seen_ids:
                            seen_ids[key].append((idx+1, col_name))
                        else:
                            seen_ids[key] = [(idx+1, col_name)]
            
            if not has_any_adid:
                st.error(f"第 {idx+1} 行：至少需要填写一个平台的广告ID")
                has_error = True
        
        # 报告重复ID
        for key, locations in seen_ids.items():
            if len(locations) > 1:
                col_label = key.split(":")[0]
                id_val = key.split(":")[1]
                rows_str = "、".join([f"第{loc[0]}行" for loc in locations])
                st.error(f"⚠️ 重复ID: [{col_label}] 值 {id_val} 在 {rows_str} 重复出现")
                has_error = True
        
        # 校验：选中的渠道是否有对应的广告ID
        if not has_error:
            for ch in selected_channels:
                ch_keyword = None
                for col_name, info in COLUMN_PLATFORM.items():
                    if info["keyword"] in ch:
                        ch_keyword = col_name
                        break
                if ch_keyword:
                    has_match = False
                    for idx, row in edited_df.iterrows():
                        ad_id = str(row.get(ch_keyword, "")).strip()
                        if ad_id and ad_id != "nan":
                            has_match = True
                            break
                    if not has_match:
                        st.error(f"选择了渠道 [{ch}]，但没有任何行填写了 [{ch_keyword}]")
                        has_error = True
        
        if has_error:
            st.warning("请修正以上错误后再生成。")
        else:
            zip_buffer = io.BytesIO()
            file_count = 0
            appid_rows = []  # 收集 Appid 导入数据
            
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for idx, row in edited_df.iterrows():
                    app_name = str(row.get("应用名称", "")).strip()
                    app_id = str(row.get("应用ID", "")).strip()
                    
                    if not app_name or not app_id:
                        continue
                    
                    for ch in selected_channels:
                        # 找到该渠道对应的列
                        target_col = None
                        for col_name, info in COLUMN_PLATFORM.items():
                            if info["keyword"] in ch:
                                target_col = col_name
                                break
                        
                        if not target_col:
                            continue
                        
                        ad_id = str(row.get(target_col, "")).strip()
                        if not ad_id or ad_id == "nan":
                            continue
                        
                        # 生成广告配置文件
                        final_df = process_rows(ch, app_name, app_id, ad_id)
                        
                        if not final_df.empty:
                            xls_data = create_xls_file(final_df)
                            fname = f"{ch}_{app_name}.xls"
                            zf.writestr(fname, xls_data.getvalue())
                            file_count += 1
                        
                        # 收集 Appid 导入数据
                        platform_info = get_platform_info(ad_id)
                        if platform_info:
                            appid_row = [app_id, platform_info["platform"], "", platform_info["account_id"], ad_id, ""]
                            if appid_row not in appid_rows:
                                appid_rows.append(appid_row)
                
                # 生成 Appid 管理导入模板
                if appid_rows:
                    appid_xls = create_appid_xls(appid_rows)
                    first_name = str(edited_df.iloc[0].get("应用名称", "产品")).strip()
                    zf.writestr(f"Appid导入_{first_name}.xls", appid_xls.getvalue())
            
            if file_count > 0:
                st.success(f"✅ 成功生成 {file_count} 个配置文件 + {len(appid_rows)} 条Appid导入记录！")
                st.download_button(
                    label="📥 下载所有文件 (.zip)",
                    data=zip_buffer.getvalue(),
                    file_name=f"广告配置_{datetime.now().strftime('%H%M%S')}.zip",
                    mime="application/zip"
                )
            else:
                st.warning("未生成任何文件，请检查输入数据或模版配置。")