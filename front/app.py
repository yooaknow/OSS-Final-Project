import base64
import html
import os
from pathlib import Path
from urllib.parse import quote

import requests
import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://back:8000")
ASSETS_DIR = Path(__file__).parent / "assets"
ONBOARDING_IMAGE = ASSETS_DIR / "onboarding.png"
RESULT_BACKGROUND_IMAGE = ASSETS_DIR / "result-bg.png"

MENU_IMAGE_BY_NAME = {
    "바닐라 라떼": ASSETS_DIR / "vanilla-latte-croissant.png",
    "카라멜 마끼아또": ASSETS_DIR / "caramel-macchiato-cheesecake.png",
    "자몽 에이드": ASSETS_DIR / "grapefruit-ade-macaron.png",
    "아이스 아메리카노": ASSETS_DIR / "iced-americano-cookie.png",
    "말차 라떼": ASSETS_DIR / "matcha-latte-pound-cake.png",
    "핫초코": ASSETS_DIR / "hot-chocolate-brownie.png",
}

QUESTIONS = [
    {
        "id": "q1",
        "image": ASSETS_DIR / "q1.png",
        "background_color": "#FFFFFF",
        "state_key": "weather",
        "choices": [
            ("맑음", "맑음"),
            ("비", "비"),
            ("눈", "눈"),
        ],
    },
    {
        "id": "q2",
        "image": ASSETS_DIR / "q2.png",
        "background_color": "#FFEAAB",
        "state_key": "mood",
        "choices": [
            ("기분 좋음", "기분 좋음"),
            ("피곤함", "피곤함"),
            ("스트레스", "스트레스"),
        ],
    },
    {
        "id": "q3",
        "image": ASSETS_DIR / "q3.png",
        "background_color": "#4CB28A",
        "state_key": "time_of_day",
        "choices": [
            ("오전", "오전"),
            ("오후", "오후"),
            ("밤", "밤"),
        ],
    },
    {
        "id": "q4",
        "image": ASSETS_DIR / "q4.png",
        "background_color": "#FFFFFF",
        "state_key": "sweetness",
        "choices": [
            (1, "담백하게"),
            (2, "살짝 달게"),
            (3, "적당히 달게"),
            (4, "달콤하게"),
            (5, "아주 달콤하게"),
        ],
    },
    {
        "id": "q5",
        "image": ASSETS_DIR / "q5.png",
        "background_color": "#FFEAAB",
        "state_key": "caffeine_sensitivity",
        "choices": [
            (1, "진한 커피도 좋아요"),
            (2, "적당한 카페인"),
            (3, "보통이에요"),
            (4, "조금 민감해요"),
            (5, "카페인 거의 없이"),
        ],
    },
]


st.set_page_config(
    page_title="Mood Brew",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)


def image_to_data_uri(image_path: Path) -> str:
    encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def init_state():
    defaults = {
        "started": False,
        "question_index": 0,
        "weather": "맑음",
        "mood": "기분 좋음",
        "time_of_day": "오후",
        "sweetness": 3,
        "caffeine_sensitivity": 3,
        "result": None,
        "result_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_app():
    st.session_state.started = False
    st.session_state.question_index = 0
    st.session_state.weather = "맑음"
    st.session_state.mood = "기분 좋음"
    st.session_state.time_of_day = "오후"
    st.session_state.sweetness = 3
    st.session_state.caffeine_sensitivity = 3
    st.session_state.result = None
    st.session_state.result_error = None


def build_payload() -> dict:
    return {
        "weather": st.session_state.weather,
        "mood": st.session_state.mood,
        "sweetness": st.session_state.sweetness,
        "caffeine_sensitivity": st.session_state.caffeine_sensitivity,
        "time_of_day": st.session_state.time_of_day,
    }


def request_recommendation():
    st.session_state.result = None
    st.session_state.result_error = None
    try:
        resp = requests.post(f"{BACKEND_URL}/recommend", json=build_payload(), timeout=10)
        if resp.status_code == 200:
            st.session_state.result = resp.json()
        else:
            st.session_state.result_error = f"추천 오류: {resp.status_code} / {resp.text}"
    except requests.exceptions.ConnectionError:
        st.session_state.result_error = (
            f"FastAPI 서버({BACKEND_URL})에 연결할 수 없습니다. "
            "백엔드 컨테이너가 실행 중인지 확인해주세요."
        )
    except Exception as e:
        st.session_state.result_error = f"오류 발생: {e}"


def render_sidebar():
    total_pages = len(QUESTIONS) + 2
    current_page = 1
    if st.session_state.started:
        current_page = min(st.session_state.question_index + 2, total_pages)

    st.sidebar.title("Mood Brew")
    st.sidebar.caption(f"{current_page} / {total_pages}")
    st.sidebar.progress(current_page / total_pages)

    st.sidebar.divider()
    st.sidebar.subheader("현재 선택")
    st.sidebar.write(f"날씨: {st.session_state.weather}")
    st.sidebar.write(f"무드: {st.session_state.mood}")
    st.sidebar.write(f"시간: {st.session_state.time_of_day}")
    st.sidebar.write(f"달콤함: {st.session_state.sweetness}/5")
    st.sidebar.write(f"카페인 민감도: {st.session_state.caffeine_sensitivity}/5")

    st.sidebar.divider()
    if st.sidebar.button("처음부터 다시", use_container_width=True):
        reset_app()
        st.rerun()


def handle_query_actions():
    action = st.query_params.get("action")
    question_id = st.query_params.get("q")
    answer = st.query_params.get("answer")

    if action == "start":
        reset_app()
        st.session_state.started = True
        st.query_params.clear()
        st.rerun()

    if action == "reset":
        reset_app()
        st.query_params.clear()
        st.rerun()

    if question_id and answer:
        question = next((item for item in QUESTIONS if item["id"] == question_id), None)
        if question:
            value = int(answer) if question["state_key"] in {"sweetness", "caffeine_sensitivity"} else answer
            st.session_state[question["state_key"]] = value
            current_index = QUESTIONS.index(question)
            if current_index == len(QUESTIONS) - 1:
                request_recommendation()
                st.session_state.question_index = len(QUESTIONS)
            else:
                st.session_state.question_index = current_index + 1
            st.session_state.started = True
            st.query_params.clear()
            st.rerun()


def inject_base_style():
    st.markdown(
        """
        <style>
            [data-testid="stHeader"],
            [data-testid="stToolbar"],
            #MainMenu,
            footer {
                display: none !important;
            }
            [data-testid="stSidebar"] {
                background: #FFF9EC;
            }
            [data-testid="stSidebar"] * {
                color: #35211A;
            }
            [data-testid="stAppViewContainer"] {
                background: #35211A;
            }
            .block-container {
                max-width: 1080px;
                padding: 0 0 2rem;
            }
            .mood-screen {
                position: relative;
                width: 100%;
                margin: 0 auto;
            }
            .mood-screen > img {
                display: block;
                width: 100%;
                height: auto;
            }
            .choice-layer {
                position: absolute;
                left: 50%;
                top: 33%;
                transform: translateX(-50%);
                width: min(78%, 820px);
                display: flex;
                flex-direction: column;
                align-items: stretch;
                justify-content: center;
                gap: 16px;
            }
            .choice-layer.five {
                top: 31%;
                width: min(78%, 820px);
            }
            .choice-link {
                display: flex;
                align-items: center;
                justify-content: space-between;
                min-height: 74px;
                padding: 0 28px 0 34px;
                border-radius: 18px;
                background: #FFFFFF;
                color: #35211A !important;
                text-decoration: none !important;
                font-size: 1.3rem;
                font-weight: 800;
                box-shadow: 0 10px 28px rgba(53, 33, 26, 0.08);
                border: 2px solid rgba(53, 33, 26, 0.09);
            }
            .choice-link::after {
                content: "✓";
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 38px;
                height: 38px;
                flex: 0 0 38px;
                margin-left: 20px;
                border-radius: 999px;
                color: #D8D8D8;
                border: 2px solid #E2E2E2;
                font-size: 1.22rem;
                font-weight: 900;
            }
            .choice-link:hover {
                transform: translateY(-2px);
                border-color: #5BD582;
                background: #FAFFFB;
                box-shadow: 0 14px 34px rgba(53, 33, 26, 0.14);
            }
            .choice-link:hover::after {
                color: #FFFFFF;
                background: #5BD582;
                border-color: #5BD582;
            }
            .back-link,
            .reset-link {
                position: absolute;
                left: 32px;
                bottom: 32px;
                color: rgba(53, 33, 26, 0.62) !important;
                text-decoration: none !important;
                font-size: 0.95rem;
                font-weight: 700;
            }
            .reset-link {
                color: #FFFFFF !important;
                background: rgba(53, 33, 26, 0.45);
                border-radius: 999px;
                padding: 12px 18px;
            }
            .result-layer {
                position: absolute;
                left: 9%;
                right: 9%;
                top: 4%;
                bottom: 7%;
                color: #35211A;
                text-align: center;
            }
            .result-title {
                margin: 0 0 14px;
                font-size: 3.3rem;
                line-height: 1.08;
                font-weight: 900;
            }
            .result-summary {
                margin: 0 auto 20px;
                max-width: 760px;
                font-size: 1.35rem;
                line-height: 1.55;
                font-weight: 700;
            }
            .result-card {
                display: grid;
                grid-template-columns: minmax(180px, 280px) 1fr;
                gap: 34px;
                align-items: center;
                max-width: 840px;
                margin: 0 auto;
                padding: 32px;
                border-radius: 28px;
                background: rgba(255, 255, 255, 0.82);
                box-shadow: 0 18px 50px rgba(53, 33, 26, 0.15);
                text-align: left;
            }
            .result-card img {
                width: 100%;
                border-radius: 22px;
            }
            .menu-name {
                margin: 0 0 10px;
                font-size: 2.1rem;
                font-weight: 900;
            }
            .dessert-name,
            .reason {
                margin: 0 0 12px;
                font-size: 1.12rem;
                line-height: 1.55;
            }
            .tags {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-top: 18px;
            }
            .tag {
                padding: 8px 12px;
                border-radius: 999px;
                background: #FFEAAB;
                font-weight: 800;
                font-size: 0.92rem;
            }
            .result-actions {
                margin-top: 26px;
            }
            .primary-link {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 160px;
                min-height: 48px;
                padding: 0 22px;
                border-radius: 999px;
                background: #35211A;
                color: #FFFFFF !important;
                text-decoration: none !important;
                font-weight: 900;
            }
            @media (max-width: 760px) {
                .choice-layer,
                .choice-layer.five {
                    top: 31%;
                    width: 86%;
                    gap: 9px;
                }
                .choice-link {
                    min-height: 46px;
                    padding: 0 14px 0 18px;
                    border-radius: 12px;
                    font-size: 0.86rem;
                }
                .choice-link::after {
                    width: 26px;
                    height: 26px;
                    flex-basis: 26px;
                    margin-left: 10px;
                    font-size: 0.82rem;
                }
                .result-title {
                    font-size: 1.9rem;
                }
                .result-layer {
                    top: 5%;
                }
                .result-summary {
                    font-size: 0.9rem;
                    margin-bottom: 12px;
                }
                .result-card {
                    grid-template-columns: 1fr;
                    gap: 14px;
                    padding: 18px;
                }
                .menu-name {
                    font-size: 1.45rem;
                }
                .dessert-name,
                .reason {
                    font-size: 0.9rem;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_onboarding():
    if not ONBOARDING_IMAGE.exists():
        st.warning("온보딩 이미지를 찾을 수 없습니다.")
        return

    st.markdown(
        f"""
        <div class="mood-screen">
            <img src="{image_to_data_uri(ONBOARDING_IMAGE)}" alt="Mood Brew onboarding">
            <a class="primary-link" style="position:absolute;left:50%;top:84%;transform:translateX(-50%);" href="?action=start" target="_self">시작하기</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_question(question: dict):
    if not question["image"].exists():
        st.warning(f"{question['image'].name} 이미지를 찾을 수 없습니다.")
        return

    background_color = question["background_color"]
    st.markdown(
        f"""
        <style>
            [data-testid="stAppViewContainer"],
            [data-testid="stMain"],
            .stApp {{
                background: {background_color} !important;
            }}
            .mood-screen {{
                background: {background_color};
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    choice_links = []
    for value, label in question["choices"]:
        choice_links.append(
            '<a class="choice-link" href="'
            f'?q={question["id"]}&answer={quote(str(value))}'
            f'" target="_self">{html.escape(label)}</a>'
        )
    layer_class = "choice-layer five" if len(question["choices"]) >= 5 else "choice-layer"
    back_link = '<a class="back-link" href="?action=reset" target="_self">처음으로</a>'

    st.markdown(
        f"""
        <div class="mood-screen">
            <img src="{image_to_data_uri(question["image"])}" alt="{question["id"]}">
            <div class="{layer_class}">
                {"".join(choice_links)}
            </div>
            {back_link}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_result():
    background = RESULT_BACKGROUND_IMAGE if RESULT_BACKGROUND_IMAGE.exists() else ONBOARDING_IMAGE

    if not st.session_state.result:
        request_recommendation()

    if st.session_state.result_error:
        st.markdown(
            f"""
            <div class="mood-screen">
                <img src="{image_to_data_uri(background)}" alt="Mood Brew result">
                <div class="result-layer">
                    <h1 class="result-title">추천을 불러오지 못했어요</h1>
                    <p class="result-summary">{html.escape(st.session_state.result_error)}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    data = st.session_state.result
    top = data["top_menu"]
    menu_image = MENU_IMAGE_BY_NAME.get(top["name"])
    menu_image_html = ""
    if menu_image and menu_image.exists():
        menu_image_html = f'<img src="{image_to_data_uri(menu_image)}" alt="{html.escape(top["name"])}">'

    tags = "".join(f'<span class="tag">{html.escape(tag)}</span>' for tag in top["tags"])

    st.markdown(
        f"""
        <div class="mood-screen">
            <img src="{image_to_data_uri(background)}" alt="Mood Brew result">
            <div class="result-layer">
                <p class="result-summary">{html.escape(data["summary"])}</p>
                <div class="result-card">
                    <div>{menu_image_html}</div>
                    <div>
                        <p class="menu-name">{html.escape(top["name"])}</p>
                        <p class="dessert-name">추천 디저트: <strong>{html.escape(top["dessert"])}</strong></p>
                        <p class="reason">{html.escape(top["reason"])}</p>
                        <div class="tags">{tags}</div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


init_state()
handle_query_actions()
inject_base_style()
render_sidebar()

if not st.session_state.started:
    render_onboarding()
elif st.session_state.question_index >= len(QUESTIONS):
    render_result()
else:
    render_question(QUESTIONS[st.session_state.question_index])
