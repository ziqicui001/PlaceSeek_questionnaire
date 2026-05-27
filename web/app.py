# streamlit run app.py

import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st


# =========================
# 配置区
# 重要：BASE_DIR 自动取当前 app.py 所在目录
# 这样本地、别的电脑、云端部署都更稳
# =========================
BASE_DIR = Path(__file__).resolve().parent
ITEMS_CSV = BASE_DIR / "annotation_items.csv"
QUERIES_CSV = BASE_DIR / "queries.csv"
QUESTIONS_CSV = BASE_DIR / "question.csv"
RESULTS_DIR = BASE_DIR / "results"

RESULTS_DIR.mkdir(exist_ok=True)


# =========================
# 页面基础设置
# =========================
st.set_page_config(
    page_title="Street View Annotation",
    page_icon="📝",
    layout="wide"
)


# =========================
# 数据读取
# =========================
@st.cache_data
def load_items(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "display_order" in df.columns:
        df = df.sort_values("display_order").reset_index(drop=True)
    return df


@st.cache_data
def load_queries(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path)


@st.cache_data
def load_questions(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    if "display_order" in df.columns:
        df = df.sort_values("display_order").reset_index(drop=True)
    return df


def safe_parse_options(options_json):
    if pd.isna(options_json):
        return {}
    if isinstance(options_json, dict):
        return options_json
    try:
        return json.loads(options_json)
    except Exception:
        return {}


# =========================
# 数据加载
# =========================
items_df = load_items(ITEMS_CSV)
queries_df = load_queries(QUERIES_CSV)
questions_df = load_questions(QUESTIONS_CSV)


# =========================
# 基本检查
# =========================
required_item_cols = ["record_id", "query_id", "query_text"]
missing_item_cols = [c for c in required_item_cols if c not in items_df.columns]
if missing_item_cols:
    st.error(f"annotation items CSV 缺少必要列: {missing_item_cols}")
    st.stop()

if "web_path" not in items_df.columns and "image_path" not in items_df.columns:
    st.error("annotation items CSV 至少需要包含 'web_path' 或 'image_path' 其中之一。")
    st.stop()

required_question_cols = ["question_id", "question_text", "question_type"]
missing_q_cols = [c for c in required_question_cols if c not in questions_df.columns]
if missing_q_cols:
    st.error(f"question.csv 缺少必要列: {missing_q_cols}")
    st.stop()


# =========================
# Session State 初始化
# =========================
if "annotator_id" not in st.session_state:
    st.session_state.annotator_id = ""

if "started" not in st.session_state:
    st.session_state.started = False

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if "responses" not in st.session_state:
    st.session_state.responses = []

if "show_instruction" not in st.session_state:
    st.session_state.show_instruction = True


# =========================
# 工具函数
# =========================
def sanitize_annotator_id(s: str) -> str:
    """
    清洗 annotator_id，避免结果文件名出现非法字符。
    只保留字母、数字、下划线、短横线。
    """
    s = str(s).strip()
    allowed = []
    for ch in s:
        if ch.isalnum() or ch in ["_", "-"]:
            allowed.append(ch)
    return "".join(allowed)


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def first_nonempty(*values) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def get_query_instruction(query_id: str, fallback_query_text: str, current_row=None):
    item_query_text = current_row.get("query_text", "") if current_row is not None else ""
    item_query_type = current_row.get("query_type", "") if current_row is not None else ""
    item_physical_target = current_row.get("physical_target_text", "") if current_row is not None else ""
    item_affective_target = current_row.get("affective_target_text", "") if current_row is not None else ""
    item_instruction = current_row.get("instruction_text", "") if current_row is not None else ""

    row = queries_df[queries_df["query_id"] == query_id]
    if len(row) > 0:
        qrow = row.iloc[0]
        query_text = first_nonempty(item_query_text, qrow.get("query_text", ""), fallback_query_text)
        query_type = first_nonempty(item_query_type, qrow.get("query_type", ""))
        physical_target_text = first_nonempty(item_physical_target, qrow.get("physical_target_text", ""))
        affective_target_text = first_nonempty(item_affective_target, qrow.get("affective_target_text", ""))
        instruction_text = first_nonempty(
            item_instruction,
            qrow.get("instruction_text", ""),
            "Please judge the image only based on visible cues in the image.",
        )
    else:
        query_text = first_nonempty(item_query_text, fallback_query_text)
        query_type = clean_text(item_query_type)
        physical_target_text = clean_text(item_physical_target)
        affective_target_text = clean_text(item_affective_target)
        instruction_text = first_nonempty(item_instruction, "Please judge the image only based on visible cues in the image.")
    return query_text, query_type, physical_target_text, affective_target_text, instruction_text


def render_query_context(query_text: str, query_type: str, physical_target_text: str, affective_target_text: str):
    st.markdown("**Query:**")
    st.info(query_text)

    if str(query_type).strip():
        st.caption(f"Query type: {query_type}")

    if str(physical_target_text).strip():
        st.markdown("**Physical requirement:**")
        st.write(physical_target_text)

    if str(affective_target_text).strip():
        st.markdown("**Affective / perceptual requirement:**")
        st.write(affective_target_text)


def save_results_to_csv():
    """
    本地/会话内自动保存。
    注意：云端部署时这只能当临时保存，不适合作为长期数据库。
    """
    annotator_id = st.session_state.annotator_id.strip()
    if not annotator_id:
        return None

    if len(st.session_state.responses) == 0:
        return None

    df = pd.DataFrame(st.session_state.responses)
    out_path = RESULTS_DIR / f"responses_{annotator_id}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path


def reset_study():
    st.session_state.current_index = 0
    st.session_state.responses = []
    st.session_state.show_instruction = True
    st.session_state.started = False
    st.session_state.annotator_id = ""


def render_single_choice(question_id, question_text, options, current_row):
    """
    前端显示文字标签，后台保存数值 key。
    例如前端显示：
      Clearly not a match
      Mostly not a match
      Mostly a match
      Clearly a match
    后台保存：
      1 / 2 / 3 / 4
    """
    option_keys = list(options.keys())
    label_to_value = {str(options[k]): str(k) for k in option_keys}
    option_labels = list(label_to_value.keys())

    st.markdown(f"**{question_text}**")

    selected_label = st.radio(
        label=f"Select answer for {question_id}",
        options=[""] + option_labels,
        index=0,
        key=f"{current_row['record_id']}_{question_id}",
        label_visibility="collapsed"
    )

    if selected_label == "":
        return ""
    return label_to_value[selected_label]


def resolve_image_path(current_row, items_df_columns):
    """
    优先级：
    1. web_path
    2. image_file_name -> BASE_DIR/images/filename
    3. image_path（仅本地兼容）
    """
    # 1) 优先 web_path
    if "web_path" in items_df_columns:
        web_path = current_row.get("web_path")
        if pd.notna(web_path) and str(web_path).strip() != "":
            return BASE_DIR / str(web_path)

    # 2) 如果没有 web_path，但有 image_file_name，则去项目内 images 文件夹找
    if "image_file_name" in items_df_columns:
        image_file_name = current_row.get("image_file_name")
        if pd.notna(image_file_name) and str(image_file_name).strip() != "":
            candidate = BASE_DIR / "images" / str(image_file_name)
            if candidate.exists():
                return candidate

    # 3) 最后才回退到原始本地绝对路径
    if "image_path" in items_df_columns:
        raw_path = current_row.get("image_path")
        if pd.notna(raw_path) and str(raw_path).strip() != "":
            return Path(str(raw_path))

    return None


# =========================
# 标题
# =========================
st.title("Street View Annotation Tool")


# =========================
# 登录页
# =========================
if not st.session_state.started:
    st.subheader("Start Annotation")

    annotator_id = st.text_input(
        "Annotator ID",
        value=st.session_state.annotator_id,
        placeholder="e.g. A01"
    )

    st.markdown("""
Please enter your annotator ID before starting.

This tool will:
- show one image at a time
- present the query and annotation questions
- save your answers locally as a CSV file
""")

    if st.button("Start"):
        annotator_id = sanitize_annotator_id(annotator_id)
        if annotator_id == "":
            st.warning("Please enter a valid annotator ID.")
        else:
            st.session_state.annotator_id = annotator_id
            st.session_state.started = True
            st.rerun()

    st.stop()


# =========================
# 当前记录
# =========================
total_items = len(items_df)
current_index = st.session_state.current_index

if current_index >= total_items:
    st.success("All items completed.")

    out_path = save_results_to_csv()

    st.write(f"Annotator ID: **{st.session_state.annotator_id}**")
    st.write(f"Total responses: **{len(st.session_state.responses)}**")

    st.info(
        "For formal online use, please click the download button below and send the CSV back to the researcher."
    )

    if out_path is not None and out_path.exists():
        st.write(f"Results saved to: `{out_path.name}`")
        with open(out_path, "rb") as f:
            st.download_button(
                label="Download results CSV",
                data=f,
                file_name=out_path.name,
                mime="text/csv"
            )

    if st.button("Start Over"):
        reset_study()
        st.rerun()

    st.stop()


current_row = items_df.iloc[current_index]
query_id = current_row["query_id"]
query_text = current_row["query_text"]
query_text, query_type, physical_target_text, affective_target_text, instruction_text = get_query_instruction(query_id, query_text, current_row)

image_path = resolve_image_path(current_row, items_df.columns)


# =========================
# 说明页
# =========================
if st.session_state.show_instruction:
    st.subheader("Instructions")

    st.markdown("### Query")
    render_query_context(query_text, query_type, physical_target_text, affective_target_text)

    st.markdown("### Instruction")
    st.write(instruction_text)

    st.markdown("""
Please judge each image **only based on visible cues in the image**.

For the 4-point scales:
- **1** = clearly negative / clearly low
- **2** = probably negative / somewhat low
- **3** = probably positive / somewhat high
- **4** = clearly positive / clearly high

Answer all required questions before moving to the next image.
""")

    st.write(f"Total images in this session: **{total_items}**")

    if st.button("Begin Annotation"):
        st.session_state.show_instruction = False
        st.rerun()

    st.stop()


# =========================
# 标注页面
# =========================
left, right = st.columns([1.2, 1])

with left:
    st.markdown(f"### Image {current_index + 1} / {total_items}")
    render_query_context(query_text, query_type, physical_target_text, affective_target_text)

    if image_path is not None and image_path.exists():
        st.image(str(image_path), use_container_width=True)
    else:
        st.error(f"Image not found: {image_path}")


with right:
    st.markdown("### Questions")

    with st.form(key=f"form_{current_row['record_id']}"):
        answers = {}
        validation_failed = False

        for _, qrow in questions_df.iterrows():
            question_id = qrow["question_id"]
            question_text = qrow["question_text"]
            question_type = qrow["question_type"]
            required = int(qrow["required"]) if "required" in qrow and not pd.isna(qrow["required"]) else 0
            options = safe_parse_options(qrow["options_json"]) if "options_json" in qrow else {}

            if question_type == "single_choice":
                answer_value = render_single_choice(
                    question_id=question_id,
                    question_text=question_text,
                    options=options,
                    current_row=current_row
                )
                answers[question_id] = answer_value

                if required == 1 and answer_value == "":
                    validation_failed = True

            elif question_type == "text":
                st.markdown(f"**{question_text}**")
                answer_value = st.text_area(
                    label=f"Enter response for {question_id}",
                    key=f"{current_row['record_id']}_{question_id}",
                    label_visibility="collapsed"
                )
                answers[question_id] = answer_value

                if required == 1 and str(answer_value).strip() == "":
                    validation_failed = True

            else:
                st.warning(f"Unsupported question type: {question_type}")
                answers[question_id] = ""

            st.markdown("---")

        submitted = st.form_submit_button("Next")

        if submitted:
            if validation_failed:
                st.warning("Please answer all required questions before continuing.")
            else:
                response_row = {
                    "annotator_id": st.session_state.annotator_id,
                    "submit_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                for col in current_row.index:
                    response_row[col] = current_row[col]

                for qid, ans in answers.items():
                    response_row[qid] = ans

                st.session_state.responses.append(response_row)

                # 每答一题就自动保存一次，防止意外中断
                save_results_to_csv()

                st.session_state.current_index += 1
                st.rerun()