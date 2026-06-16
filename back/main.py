from datetime import datetime
import json
import os
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
from pydantic import BaseModel, Field
import uvicorn


app = FastAPI(title="Cafe Menu Recommendation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "recuser"),
    "password": os.getenv("DB_PASSWORD", "recpass"),
    "database": os.getenv("DB_NAME", "travel_rec"),
    "connection_timeout": 5,
}


class RecommendRequest(BaseModel):
    weather: str
    mood: str
    sweetness: int = Field(ge=1, le=5)
    caffeine_sensitivity: int = Field(ge=1, le=5)
    time_of_day: str


class MenuResult(BaseModel):
    rank: int
    name: str
    dessert: str
    score: int
    description: str
    reason: str
    tags: List[str]


class RecommendResponse(BaseModel):
    recommendations: List[MenuResult]
    top_menu: MenuResult
    summary: str


MENU_CANDIDATES = [
    {
        "name": "바닐라 라떼",
        "dessert": "버터 크루아상",
        "base": 55,
        "caffeine": 3,
        "sweetness": 4,
        "tags": ["달콤함", "부드러움", "따뜻한 라떼"],
        "description": "바닐라 향과 우유의 부드러움이 잘 어울리는 편안한 메뉴입니다.",
    },
    {
        "name": "카라멜 마끼아또",
        "dessert": "치즈케이크",
        "base": 52,
        "caffeine": 3,
        "sweetness": 5,
        "tags": ["진한 단맛", "기분 전환", "디저트 조합"],
        "description": "카라멜의 달콤함이 확실해서 당 충전이 필요할 때 좋습니다.",
    },
    {
        "name": "자몽 에이드",
        "dessert": "마카롱",
        "base": 50,
        "caffeine": 0,
        "sweetness": 3,
        "tags": ["무카페인", "상큼함", "가벼움"],
        "description": "카페인이 부담스러운 날에도 마시기 좋은 상큼한 음료입니다.",
    },
    {
        "name": "아이스 아메리카노",
        "dessert": "초코 쿠키",
        "base": 48,
        "caffeine": 5,
        "sweetness": 1,
        "tags": ["깔끔함", "집중", "저당"],
        "description": "단맛이 적고 카페인이 강해 집중이 필요한 시간에 잘 맞습니다.",
    },
    {
        "name": "말차 라떼",
        "dessert": "말차 파운드케이크",
        "base": 51,
        "caffeine": 2,
        "sweetness": 3,
        "tags": ["은은함", "차분함", "고소함"],
        "description": "쌉싸름한 말차와 우유가 섞여 차분한 맛을 냅니다.",
    },
    {
        "name": "핫초코",
        "dessert": "초코 브라우니",
        "base": 49,
        "caffeine": 1,
        "sweetness": 5,
        "tags": ["무드 회복", "달콤함", "따뜻함"],
        "description": "카페인은 낮고 단맛은 높아 피곤하거나 우울한 날에 잘 어울립니다.",
    },
]


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def ensure_history_table(cursor):
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS cafe_recommendation_history (
            id                     INT AUTO_INCREMENT PRIMARY KEY,
            weather                VARCHAR(20) NOT NULL,
            mood                   VARCHAR(20) NOT NULL,
            sweetness              INT NOT NULL,
            caffeine_sensitivity   INT NOT NULL,
            time_of_day            VARCHAR(20) NOT NULL,
            results_json           JSON,
            created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )


def score_menu(menu: dict, req: RecommendRequest) -> tuple[int, list[str]]:
    score = menu["base"]
    reasons: list[str] = []

    if req.weather == "비":
        if "라떼" in menu["name"] or menu["name"] == "핫초코":
            score += 16
            reasons.append("비 오는 날에는 따뜻하고 부드러운 메뉴가 잘 어울립니다")
    elif req.weather == "맑음":
        if menu["name"] in ["자몽 에이드", "아이스 아메리카노"]:
            score += 13
            reasons.append("맑은 날에는 가볍고 산뜻한 메뉴가 잘 맞습니다")
    elif req.weather == "눈":
        if menu["name"] in ["핫초코", "바닐라 라떼", "말차 라떼"]:
            score += 15
            reasons.append("눈 오는 날에는 따뜻한 음료가 분위기와 잘 맞습니다")

    if req.mood == "기분 좋음":
        if menu["sweetness"] >= 3:
            score += 8
            reasons.append("좋은 기분을 이어가기 좋은 달콤한 조합입니다")
    elif req.mood == "피곤함":
        if menu["caffeine"] >= 3 and req.caffeine_sensitivity <= 3:
            score += 15
            reasons.append("피곤할 때 도움이 되는 카페인 메뉴입니다")
        if menu["name"] == "핫초코":
            score += 6
    elif req.mood == "스트레스":
        if menu["sweetness"] >= 4:
            score += 14
            reasons.append("스트레스가 있을 때 단맛으로 기분 전환하기 좋습니다")

    sweetness_gap = abs(menu["sweetness"] - req.sweetness)
    score += max(0, 12 - sweetness_gap * 4)
    if sweetness_gap <= 1:
        reasons.append("선택한 단맛 선호도와 잘 맞습니다")

    if req.caffeine_sensitivity >= 4:
        score += (5 - menu["caffeine"]) * 4
        if menu["caffeine"] <= 1:
            reasons.append("카페인 민감도가 높아 저카페인 메뉴를 우선 추천했습니다")
    else:
        score += menu["caffeine"] * 2
        if menu["caffeine"] >= 3:
            reasons.append("카페인 민감도가 낮아 커피 메뉴도 부담이 적습니다")

    if req.time_of_day == "오전":
        if menu["name"] in ["아이스 아메리카노", "바닐라 라떼", "말차 라떼"]:
            score += 8
            reasons.append("오전에 마시기 좋은 깔끔한 메뉴입니다")
    elif req.time_of_day == "오후":
        if menu["name"] in ["카라멜 마끼아또", "자몽 에이드", "말차 라떼"]:
            score += 8
            reasons.append("오후 간식 시간에 디저트와 함께 즐기기 좋습니다")
    elif req.time_of_day == "밤":
        if menu["caffeine"] <= 1:
            score += 14
            reasons.append("밤에는 카페인이 낮은 메뉴가 더 편안합니다")

    if not reasons:
        reasons.append("입력 조건을 종합했을 때 가장 균형 잡힌 선택입니다")

    return score, reasons


def build_recommendations(req: RecommendRequest) -> List[MenuResult]:
    scored = []
    for menu in MENU_CANDIDATES:
        score, reasons = score_menu(menu, req)
        scored.append((score, menu, reasons))

    scored.sort(key=lambda item: item[0], reverse=True)

    results: List[MenuResult] = []
    for rank, (score, menu, reasons) in enumerate(scored[:3], start=1):
        results.append(
            MenuResult(
                rank=rank,
                name=menu["name"],
                dessert=menu["dessert"],
                score=min(score, 99),
                description=menu["description"],
                reason=" ".join(reasons[:3]) + ".",
                tags=menu["tags"],
            )
        )
    return results


def save_history(req: RecommendRequest, results: List[MenuResult]):
    try:
        conn = get_db()
        cursor = conn.cursor()
        ensure_history_table(cursor)
        cursor.execute(
            """INSERT INTO cafe_recommendation_history
               (weather, mood, sweetness, caffeine_sensitivity, time_of_day, results_json)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                req.weather,
                req.mood,
                req.sweetness,
                req.caffeine_sensitivity,
                req.time_of_day,
                json.dumps([r.model_dump() for r in results], ensure_ascii=False),
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception:
        pass


@app.get("/health")
def health():
    db_ok = False
    try:
        conn = get_db()
        conn.close()
        db_ok = True
    except Exception:
        pass
    return {"status": "ok", "db_connected": db_ok, "timestamp": datetime.now().isoformat()}


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    results = build_recommendations(req)
    top = results[0]
    summary = (
        f"{req.weather} 날씨, {req.mood} 기분, 단맛 {req.sweetness}/5, "
        f"카페인 민감도 {req.caffeine_sensitivity}/5 조건에 맞춰 "
        f"{top.name} + {top.dessert} 세트를 추천합니다."
    )
    save_history(req, results)
    return RecommendResponse(recommendations=results, top_menu=top, summary=summary)


@app.get("/history")
def get_history(limit: int = 10):
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        ensure_history_table(cursor)
        cursor.execute(
            "SELECT id, weather, mood, sweetness, caffeine_sensitivity, time_of_day, created_at "
            "FROM cafe_recommendation_history ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        for row in rows:
            row["created_at"] = str(row["created_at"])
        return {"history": rows}
    except Exception as e:
        return {"history": [], "error": str(e)}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
