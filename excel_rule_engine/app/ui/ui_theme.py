"""Local, presentation-only theme helpers for the Streamlit workspace.

Only this module's static stylesheet and escaped markup are rendered as HTML.
The helpers do not change application state, navigation, or data processing.
"""
from html import escape

import streamlit as st


THEME_CSS = """
<style>
:root {
  color-scheme: dark;
  --xl-bg: #090f1c;
  --xl-panel: #111c2f;
  --xl-panel-soft: #152238;
  --xl-border: #33445f;
  --xl-text: #eff5ff;
  --xl-muted: #b1c1d8;
  --xl-cyan: #67e8f9;
  --xl-indigo: #a5b4fc;
}
[data-testid="stAppViewContainer"] {
  color: var(--xl-text);
  background: radial-gradient(ellipse at 90% 0%, #1c284b 0%, transparent 48%), var(--xl-bg);
  font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
}
[data-testid="stHeader"] { background: #090f1cf2; }
[data-testid="stSidebar"] {
  background: #0d1627;
  border-right: 1px solid var(--xl-border);
}
[data-testid="stMainBlockContainer"] {
  max-width: 1280px;
  padding-top: 2.5rem;
  padding-bottom: 3rem;
}
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] { color: var(--xl-text); }
[data-testid="stCaptionContainer"] { color: var(--xl-muted); }
h1, h2, h3 { color: var(--xl-text); letter-spacing: -.035em; }
a { color: var(--xl-cyan); text-underline-offset: .2em; }
button, input, textarea, select { font: inherit; }
button:focus-visible, a:focus-visible, input:focus-visible,
textarea:focus-visible, select:focus-visible, [tabindex]:focus-visible {
  outline: 3px solid var(--xl-cyan) !important;
  outline-offset: 4px !important;
}
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button,
[data-testid="stFileUploader"] button {
  border: 1px solid #52698a;
  border-radius: .75rem;
  color: var(--xl-text);
  background: #192940;
  min-height: 2.75rem;
  transition: background-color .15s ease, border-color .15s ease;
}
[data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover,
[data-testid="stFileUploader"] button:hover {
  background: #243b58;
  border-color: var(--xl-cyan);
  color: #fff;
}
[data-testid="stButton"] button[kind="primary"],
[data-testid="stBaseButton-primary"] {
  color: #07131f;
  background: linear-gradient(110deg, #67e8f9, #a5b4fc);
  border-color: #a5b4fc;
  font-weight: 700;
}
[data-testid="stButton"] button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover { background: #a5f3fc; color: #07131f; }
button:disabled { opacity: .55; cursor: not-allowed; }
[data-testid="stFileUploaderDropzone"] {
  background: #111e32;
  border: 1px dashed #6283aa;
  border-radius: 1rem;
  color: var(--xl-text);
}
[data-testid="stFileUploaderDropzone"] small { color: var(--xl-muted); }
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input, [data-baseweb="select"] > div {
  color: var(--xl-text);
  background: #142238;
  border-color: #52698a;
  border-radius: .65rem;
}
input::placeholder, textarea::placeholder { color: #afbed3; opacity: 1; }
[data-testid="stTabs"] [role="tablist"] {
  gap: .5rem;
  border-bottom: 1px solid var(--xl-border);
}
[data-testid="stTabs"] [role="tab"] {
  padding: .7rem 1rem;
  color: var(--xl-muted);
  border-radius: .6rem .6rem 0 0;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: var(--xl-cyan);
  background: #172b43;
}
[data-testid="stRadio"] [role="radiogroup"] { gap: .65rem; }
[data-testid="stRadio"] label {
  color: var(--xl-text);
  padding: .65rem .8rem;
  background: #142238;
  border: 1px solid var(--xl-border);
  border-radius: .7rem;
}
[data-testid="stRadio"] label:has(input:checked) {
  background: #203450;
  border-color: var(--xl-cyan);
}
[data-testid="stChatMessage"] {
  background: #122036;
  border: 1px solid var(--xl-border);
  border-radius: 1rem;
  padding: 1.15rem;
}
[data-testid="stChatInput"] {
  border: 1px solid #6283aa;
  border-radius: 1rem;
  background: #15243b;
}
[data-testid="stChatInput"] textarea { color: var(--xl-text); }
[data-testid="stBottom"] > div { background: #090f1c; }
[data-testid="stExpander"] {
  background: #111c2f;
  border: 1px solid var(--xl-border);
  border-radius: .85rem;
}
[data-testid="stExpander"] summary { color: var(--xl-text); }
[data-testid="stDataFrame"] { border: 1px solid var(--xl-border); border-radius: .8rem; }
.xl-hero {
  position: relative;
  overflow: hidden;
  padding: clamp(1.5rem, 4vw, 3rem);
  margin-bottom: 1.5rem;
  border: 1px solid #3e5275;
  border-radius: 1.5rem;
  background: radial-gradient(ellipse at top right, #284365 0%, transparent 65%),
              linear-gradient(125deg, #142139, #161d36);
  box-shadow: 0 18px 60px #00000026;
}
.xl-hero-top { display: flex; flex-wrap: wrap; align-items: center; gap: .75rem; }
.xl-eyebrow {
  color: var(--xl-cyan);
  font-size: .74rem;
  font-weight: 700;
  letter-spacing: .16em;
  text-transform: uppercase;
}
.xl-badge {
  display: inline-flex;
  align-items: center;
  gap: .45rem;
  padding: .3rem .65rem;
  border: 1px solid #57748d;
  border-radius: 999px;
  background: #11283a;
  color: #b5f5df;
  font-size: .7rem;
  font-weight: 700;
  letter-spacing: .07em;
}
.xl-badge-local { color: #e3dcff; background: #292642; border-color: #73658f; }
.xl-status-dot { height: .4rem; width: .4rem; background: currentColor; border-radius: 50%; }
.xl-hero h1 { margin: 1rem 0 .75rem; font-size: clamp(2rem, 5vw, 3.55rem); line-height: 1.08; font-weight: 750; }
.xl-hero h1 span { color: var(--xl-cyan); }
.xl-hero p { max-width: 43rem; color: #c5d3e7; line-height: 1.75; margin-bottom: 1.35rem; }
.xl-hero-meta { display: flex; flex-wrap: wrap; gap: .65rem; }
.xl-meta { font-size: .76rem; color: #d4def1; padding: .35rem .65rem; border: 1px solid #3f5676; border-radius: .45rem; background: #101c3099; }
.xl-brand { display: flex; align-items: center; gap: .8rem; margin: .5rem 0 1.75rem; }
.xl-brand-mark { display: grid; place-items: center; width: 2.8rem; height: 2.8rem; border-radius: .85rem; background: linear-gradient(135deg, #67e8f9, #a5b4fc); color: #091727; font-weight: 850; font-size: 1.3rem; }
.xl-brand strong { color: #f1f6ff; font-size: 1.12rem; letter-spacing: -.025em; }
.xl-brand small { display: block; color: var(--xl-muted); font-size: .7rem; letter-spacing: .07em; margin-top: .15rem; }
.xl-section { margin: .5rem 0 1.5rem; }
.xl-section h2 { font-size: 1.5rem; margin: 0 0 .5rem; }
.xl-section p { color: var(--xl-muted); line-height: 1.7; margin: 0; }
.xl-empty { padding: 1.25rem 0 1rem; }
.xl-empty > h2 { font-size: 1.35rem; margin-bottom: .5rem; }
.xl-empty > p { color: var(--xl-muted); line-height: 1.7; }
.xl-card-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .85rem; margin-top: 1.3rem; }
.xl-info-card { padding: 1.25rem; border: 1px solid var(--xl-border); border-radius: 1rem; background: linear-gradient(145deg, #17253c, #111c2f); }
.xl-card-number { color: var(--xl-cyan); font-size: .75rem; letter-spacing: .08em; font-weight: 700; }
.xl-info-card h3 { color: #f0f5ff; font-size: 1rem; letter-spacing: -.015em; margin: .75rem 0 .5rem; }
.xl-info-card p { color: var(--xl-muted); font-size: .88rem; line-height: 1.7; margin: 0; }
@media (max-width: 700px) {
  [data-testid="stMainBlockContainer"] { padding: 1.5rem 1rem 2rem; }
  .xl-hero { border-radius: 1rem; }
  .xl-card-grid { grid-template-columns: 1fr; }
  .xl-hero-meta { gap: .4rem; }
  [data-testid="stTabs"] [role="tab"] { padding: .6rem; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
}
</style>
"""


# Neutral chat-first overrides retain native Streamlit keyboard/accessibility controls.
CHAT_CSS = """
<style>
:root { --xl-bg:#212121; --xl-panel:#292929; --xl-panel-soft:#303030;
--xl-border:#424242; --xl-text:#ececec; --xl-muted:#b4b4b4; --xl-cyan:#a8dfc7; }
[data-testid="stAppViewContainer"] { background:#212121; }
[data-testid="stHeader"] { background:#212121e8; }
[data-testid="stSidebar"] { background:#171717; border-right:1px solid #282828; }
[data-testid="stMainBlockContainer"] { max-width:920px; padding-top:1.4rem; padding-bottom:5rem; }
[data-testid="stChatMessage"] { background:transparent; border:0; border-radius:0; padding:1.2rem .25rem; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
background:#303030; border-radius:1.5rem; margin-left:auto; width:fit-content; max-width:88%; padding:.9rem 1.2rem;
}
[data-testid="stChatMessageContent"] { line-height:1.75; }
[data-testid="stChatInput"] { background:#303030; border:1px solid #494949; border-radius:1.65rem; padding:.35rem .6rem; }
[data-testid="stChatInput"] textarea { background:transparent; }
[data-testid="stBottom"] > div { background:#212121; }
[data-testid="stButton"] button, [data-testid="stDownloadButton"] button {
background:#292929; border:1px solid #454545; color:#ececec; border-radius:.8rem;
}
[data-testid="stButton"] button:hover { background:#373737; border-color:#777; }
[data-testid="stButton"] button[kind="primary"] { background:#ececec; color:#171717; border-color:#ececec; }
[data-testid="stRadio"] label { background:transparent; border:0; border-radius:.6rem; }
[data-testid="stRadio"] label:has(input:checked) { background:#303030; border:0; }
[data-testid="stExpander"] { background:transparent; border-color:#3d3d3d; }
[data-testid="stFileUploaderDropzone"], [data-baseweb="select"] > div,
[data-testid="stTextInput"] input { background:#292929; border-color:#454545; }
.xl-brand { margin:.25rem 0 1rem; }
.xl-brand-mark { background:#ececec; color:#202020; border-radius:.7rem; width:2.2rem; height:2.2rem; }
.xl-brand small { letter-spacing:.02em; }
.xl-chat-top { display:flex; justify-content:space-between; align-items:center; padding:.4rem 0 1rem; margin-bottom:.5rem; }
.xl-chat-top strong { font-size:1.15rem; font-weight:600; }
.xl-chat-status { font-size:.75rem; color:#b4b4b4; }
.xl-welcome { text-align:center; padding:clamp(2rem,10vh,7rem) 0 1.5rem; }
.xl-welcome h1 { font-size:clamp(1.8rem,4vw,2.4rem); font-weight:600; letter-spacing:-.045em; }
.xl-welcome p { color:#b4b4b4; line-height:1.7; max-width:34rem; margin:1rem auto; }
@media(max-width:700px) {
[data-testid="stMainBlockContainer"] { padding:1rem .8rem 4rem; }
.xl-welcome { padding:2.5rem 0 1rem; }
[data-testid="stChatMessage"] { padding:.9rem 0; }
}
</style>
"""


_SECTION_DESCRIPTIONS = {
    "Chatbot": "Xử lý file trong dự án bằng lệnh tiếng Việt: lọc, gộp và đối chiếu. Với file upload riêng, hãy chọn công cụ báo cáo ở thanh bên.",
    "Tạo báo cáo": "Từ dữ liệu thô đến báo cáo rõ ràng. Chọn tệp, thiết lập nội dung và xuất kết quả theo nhu cầu của bạn.",
    "Báo cáo nâng cao": "Thiết kế báo cáo chuyên sâu với tổng hợp, pivot và so sánh kỳ. Kiểm soát cấu hình và xem trước trước khi xuất tệp.",
}


def inject_theme() -> None:
    """Inject a static, local stylesheet without hiding Streamlit controls."""
    st.markdown(THEME_CSS + CHAT_CSS, unsafe_allow_html=True)


def render_sidebar_brand() -> None:
    """Render the compact workspace identity in the current container."""
    st.markdown(
        '<div class="xl-brand"><div class="xl-brand-mark" aria-hidden="true">E</div>'
        '<div><strong>Excel Studio</strong><small>DATA WORKSPACE</small></div></div>',
        unsafe_allow_html=True,
    )


def render_hero(api_online: bool, section: str) -> None:
    """Render a section-aware hero with an honest API connectivity badge."""
    if section == "Chatbot":
        status = "Connected" if api_online else "Offline"
        st.markdown('<div class="xl-chat-top"><strong>Excel Assistant</strong>'
                    f'<span class="xl-chat-status">{status}</span></div>', unsafe_allow_html=True)
        return
    badge = "ONLINE" if api_online else "LOCAL MODE"
    badge_class = "xl-badge" if api_online else "xl-badge xl-badge-local"
    status = "API đã kết nối" if api_online else "API chưa kết nối · Công cụ báo cáo cục bộ vẫn khả dụng"
    description = _SECTION_DESCRIPTIONS.get(section, "Không gian làm việc dành cho dữ liệu Excel và CSV của bạn.")
    st.markdown(
        '<section class="xl-hero" aria-label="Excel intelligence">'
        '<div class="xl-hero-top"><span class="xl-eyebrow">EXCEL STUDIO / '
        f'{escape(section)}</span><span class="{badge_class}" title="{escape(status, quote=True)}">'
        f'<span class="xl-status-dot" aria-hidden="true"></span>{badge}</span></div>'
        '<h1>Excel <span>intelligence.</span></h1>'
        f'<p>{escape(description)}</p>'
        '<div class="xl-hero-meta"><span class="xl-meta">Excel &amp; CSV</span>'
        '<span class="xl-meta">Phân tích dữ liệu</span><span class="xl-meta">Xuất báo cáo</span></div>'
        '</section>',
        unsafe_allow_html=True,
    )


def render_section_intro(title: str, description: str) -> None:
    """Render a safely escaped title and descriptive paragraph."""
    st.markdown(
        f'<section class="xl-section"><h2>{escape(title)}</h2><p>{escape(description)}</p></section>',
        unsafe_allow_html=True,
    )


def render_empty_chat() -> None:
    """Show informational getting-started cards, not simulated controls."""
    st.markdown(
        '<section class="xl-welcome"><h1>Bạn muốn khám phá điều gì hôm nay?</h1>'
        '<p>Hỏi về dữ liệu của bạn, tra cứu thông tin có dẫn nguồn, '
        'hoặc yêu cầu tạo báo cáo. Mọi thay đổi dữ liệu đều cần xác nhận.</p></section>',
        unsafe_allow_html=True,
    )
