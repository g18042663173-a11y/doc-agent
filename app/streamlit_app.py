from __future__ import annotations

from pathlib import Path

import streamlit as st

from doc_agent.config import get_settings
from doc_agent.workflow import run_generate


st.set_page_config(page_title="企业文档生成 Agent MVP", layout="centered")
st.title("企业文档生成 Agent MVP")

settings = get_settings()
st.caption(f"LLM_PROVIDER: {settings.llm_provider} | PPT_RENDERER: {settings.ppt_renderer}")

uploaded = st.file_uploader("上传 md/docx/pptx/xlsx/xlsm", type=["md", "docx", "pptx", "xlsx", "xlsm"])
target = st.radio("输出类型", ["pptx", "docx"], horizontal=True)
slides = st.slider("PPT 页数", min_value=5, max_value=12, value=settings.default_target_slides)

if st.button("生成", type="primary", disabled=uploaded is None):
    if uploaded is None:
        st.warning("请先上传文件。")
    else:
        tmp_dir = settings.output_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        input_path = tmp_dir / uploaded.name
        input_path.write_bytes(uploaded.getbuffer())
        output_path = tmp_dir / f"{input_path.stem}.{target}"

        with st.spinner("正在生成文件..."):
            try:
                result = run_generate(input_path, target, output_path, target_slide_count=slides)
            except Exception as exc:
                st.error(str(exc))
            else:
                st.success(f"生成完成：{result.name}")
                st.download_button(
                    label="下载文件",
                    data=result.read_bytes(),
                    file_name=result.name,
                    mime=(
                        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                        if target == "pptx"
                        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    ),
                )
