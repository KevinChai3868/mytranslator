import json
import os

import requests
from dotenv import load_dotenv
from google import genai


GEMINI_MODEL_NAME = "gemini-3.5-flash"
DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_OPENAI_VISION_MODEL = "gpt-4.1-mini"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "alloy"
SYSTEM_INSTRUCTION = "只輸出翻譯後文字，不要解釋"
IMAGE_TRANSLATION_INSTRUCTION = (
    "你是照片文字翻譯助手。請先辨識圖片中的可讀文字與重要上下文，再摘要重點，"
    "並翻譯成指定語言。只輸出 JSON，不要 Markdown，不要解釋。"
    '格式必須是 {"summary":"...","translation":"..."}。'
    "如果圖片中沒有可讀文字，summary 說明看見的內容，translation 留空字串。"
)
TRAVEL_ASSISTANT_INSTRUCTION = (
    "你是給台灣旅客使用的日本旅行助手。請用繁體中文回答，語氣簡潔、實用、"
    "像正在幫朋友安排行程。優先提供可執行建議、交通方式、注意事項、備案。"
    "若有即時搜尋資料，優先依搜尋資料回答；若沒有搜尋資料，請避免假裝知道"
    "即時營業時間、票價或班次，並提醒使用者出發前再確認。"
)
SUPPORTED_CURRENCIES = {"TWD", "JPY", "USD", "KRW", "EUR", "CNY"}
CITY_ALIASES = {
    "東京": "Tokyo",
    "东京": "Tokyo",
    "大阪": "Osaka",
    "京都": "Kyoto",
    "那霸": "Naha",
    "那霸市": "Naha",
    "那霸機場": "Naha",
    "那霸机场": "Naha",
    "沖繩": "Naha",
    "冲绳": "Naha",
    "札幌": "Sapporo",
    "福岡": "Fukuoka",
    "福冈": "Fukuoka",
    "名古屋": "Nagoya",
    "橫濱": "Yokohama",
    "横滨": "Yokohama",
    "神戶": "Kobe",
    "神户": "Kobe",
    "奈良": "Nara",
    "廣島": "Hiroshima",
    "广岛": "Hiroshima",
}
COMMON_WEATHER_PLACES = {
    "東京": (35.6895, 139.6917, "東京", "日本", "東京都"),
    "东京": (35.6895, 139.6917, "東京", "日本", "東京都"),
    "大阪": (34.6937, 135.5023, "大阪", "日本", "大阪府"),
    "京都": (35.0116, 135.7681, "京都", "日本", "京都府"),
    "那霸": (26.2130, 127.6785, "那霸市", "日本", "沖繩縣"),
    "那霸市": (26.2130, 127.6785, "那霸市", "日本", "沖繩縣"),
    "那霸機場": (26.2067, 127.6469, "那霸機場", "日本", "沖繩縣"),
    "那霸机场": (26.2067, 127.6469, "那霸機場", "日本", "沖繩縣"),
    "沖繩": (26.2130, 127.6785, "那霸市", "日本", "沖繩縣"),
    "冲绳": (26.2130, 127.6785, "那霸市", "日本", "沖繩縣"),
    "札幌": (43.0618, 141.3545, "札幌", "日本", "北海道"),
    "福岡": (33.5902, 130.4017, "福岡", "日本", "福岡縣"),
    "福冈": (33.5902, 130.4017, "福岡", "日本", "福岡縣"),
    "名古屋": (35.1815, 136.9066, "名古屋", "日本", "愛知縣"),
    "橫濱": (35.4437, 139.6380, "橫濱", "日本", "神奈川縣"),
    "横滨": (35.4437, 139.6380, "橫濱", "日本", "神奈川縣"),
    "神戶": (34.6901, 135.1955, "神戶", "日本", "兵庫縣"),
    "神户": (34.6901, 135.1955, "神戶", "日本", "兵庫縣"),
    "奈良": (34.6851, 135.8048, "奈良", "日本", "奈良縣"),
    "廣島": (34.3853, 132.4553, "廣島", "日本", "廣島縣"),
    "广岛": (34.3853, 132.4553, "廣島", "日本", "廣島縣"),
}
WEATHER_CODE_LABELS = {
    0: "晴朗",
    1: "大致晴朗",
    2: "局部多雲",
    3: "陰天",
    45: "有霧",
    48: "霧凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "大毛毛雨",
    56: "凍毛毛雨",
    57: "強凍毛毛雨",
    61: "小雨",
    63: "雨",
    65: "大雨",
    66: "凍雨",
    67: "強凍雨",
    71: "小雪",
    73: "雪",
    75: "大雪",
    77: "雪粒",
    80: "短暫小雨",
    81: "短暫陣雨",
    82: "強陣雨",
    85: "短暫小雪",
    86: "強短暫降雪",
    95: "雷雨",
    96: "雷雨伴隨小冰雹",
    99: "雷雨伴隨大冰雹",
}


def _open_meteo_get_json(url, params):
    last_error = None
    headers = {"User-Agent": "my-translator/1.0 travel-weather"}

    for _ in range(2):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc

    raise last_error


def _format_request_error(exc):
    response = getattr(exc, "response", None)
    if response is None:
        return type(exc).__name__

    detail = ""
    try:
        detail = response.text[:160].replace("\n", " ").strip()
    except Exception:
        detail = ""

    if detail:
        return f"HTTP {response.status_code}: {detail}"

    return f"HTTP {response.status_code}"


def _weather_from_wttr(location):
    response = requests.get(
        f"https://wttr.in/{location}",
        params={"format": "j1", "lang": "zh-tw"},
        headers={"User-Agent": "my-translator/1.0 travel-weather"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    current = (payload.get("current_condition") or [{}])[0]

    temperature = float(current.get("temp_C"))
    apparent_temperature = float(current.get("FeelsLikeC"))
    humidity = int(current.get("humidity"))
    rain_probability = int(current.get("chanceofrain") or 0)
    weather = ((current.get("lang_zh-tw") or [{}])[0].get("value") or "").strip()
    if not weather:
        weather = ((current.get("weatherDesc") or [{}])[0].get("value") or "未知天氣").strip()

    return {
        "ok": True,
        "location": location,
        "country": "",
        "admin1": "",
        "temperature": temperature,
        "apparent_temperature": apparent_temperature,
        "humidity": humidity,
        "weather": weather,
        "weather_code": -1,
        "precipitation": 0,
        "rain_probability": rain_probability,
        "advice": _weather_advice(
            temperature,
            apparent_temperature,
            rain_probability,
            -1,
        ),
        "updated_at": current.get("localObsDateTime", ""),
        "timezone": "",
        "source": "wttr.in fallback",
    }


def _build_prompt(text, source, target):
    source_label = source or "自動偵測"
    return (
        f"請將以下文字從「{source_label}」翻譯成「{target}」。\n\n"
        f"文字：\n{text}"
    )


def _parse_json_object(text):
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return {}


def _translate_with_openai(prompt):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "error": "找不到 OPENAI_API_KEY，請先在 .env 設定金鑰。",
        }

    model_name = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model_name,
            instructions=SYSTEM_INSTRUCTION,
            input=prompt,
        )

        translation = (response.output_text or "").strip()
        if not translation:
            return {"ok": False, "error": "OpenAI 沒有回傳翻譯結果。"}

        return {"ok": True, "translation": translation}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def synthesize_speech(data):
    load_dotenv()

    text = str(data.get("text", "")).strip()
    if not text:
        return {"ok": False, "error": "缺少 text，請提供要朗讀的文字。"}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "error": "找不到 OPENAI_API_KEY，請先在 .env 設定金鑰。",
        }

    model_name = os.getenv("OPENAI_TTS_MODEL", DEFAULT_TTS_MODEL)
    voice = os.getenv("OPENAI_TTS_VOICE", DEFAULT_TTS_VOICE)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.audio.speech.create(
            model=model_name,
            voice=voice,
            input=text,
            response_format="mp3",
        )

        return {
            "ok": True,
            "audio": response.content,
            "mime_type": "audio/mpeg",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def translate_image(data):
    load_dotenv()

    image_data_url = str(data.get("image", "")).strip()
    target = str(data.get("target", "")).strip()

    if not image_data_url:
        return {"ok": False, "error": "缺少 image，請先拍照或選擇圖片。"}

    if not target:
        return {"ok": False, "error": "缺少 target，請指定目標語言。"}

    if not image_data_url.startswith("data:image/"):
        return {"ok": False, "error": "圖片格式不正確，請使用 JPG、PNG 或 WebP 圖片。"}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "error": "找不到 OPENAI_API_KEY，請先在 .env 設定金鑰。",
        }

    model_name = os.getenv(
        "OPENAI_VISION_MODEL",
        os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_VISION_MODEL),
    )
    prompt = (
        f"請辨識這張照片中的文字，並翻譯成「{target}」。"
        "摘要請簡短指出照片或文件重點；翻譯請保留換行與清單結構。"
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model_name,
            instructions=IMAGE_TRANSLATION_INSTRUCTION,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_data_url},
                    ],
                }
            ],
        )

        output_text = (response.output_text or "").strip()
        parsed = _parse_json_object(output_text)
        summary = str(parsed.get("summary", "")).strip()
        translation = str(parsed.get("translation", "")).strip()

        if not parsed and output_text:
            translation = output_text

        if not translation:
            if summary:
                translation = "照片中沒有可辨識的文字。"
            else:
                return {"ok": False, "error": "OpenAI 沒有回傳照片翻譯結果。"}

        return {"ok": True, "summary": summary, "translation": translation}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _search_tavily(query):
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        return "", [], False

    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": tavily_key,
            "query": query,
            "search_depth": "basic",
            "max_results": 5,
            "include_answer": True,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()

    context_parts = []
    sources = []

    if payload.get("answer"):
        context_parts.append(f"搜尋摘要：{payload['answer']}")

    for item in payload.get("results", []):
        title = item.get("title", "")
        url = item.get("url", "")
        content = item.get("content", "")
        context_parts.append(f"- {title}: {content}")
        if url:
            sources.append({"title": title or url, "url": url})

    return "\n".join(context_parts), sources, bool(context_parts)


def ask_travel_assistant(data):
    load_dotenv()

    question = str(data.get("question", "")).strip()
    if not question:
        return {"ok": False, "error": "請先輸入旅遊問題。"}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "error": "找不到 OPENAI_API_KEY，請先在 .env 設定金鑰。",
        }

    model_name = os.getenv("OPENAI_ASSISTANT_MODEL", os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL))
    search_note = ""
    search_context = ""
    sources = []
    searched = False

    try:
        search_context, sources, searched = _search_tavily(question)
    except Exception:
        search_note = "即時搜尋暫時無法使用，以下先用 AI 既有知識回答。"

    prompt = f"使用者問題：{question}"
    if search_context:
        prompt += f"\n\n即時搜尋資料：\n{search_context}"

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model_name,
            instructions=TRAVEL_ASSISTANT_INSTRUCTION,
            input=prompt,
        )

        answer = (response.output_text or "").strip()
        if not answer:
            return {"ok": False, "error": "OpenAI 沒有回傳旅遊助手回答。"}

        if search_note:
            answer = f"{answer}\n\n{search_note}"

        return {
            "ok": True,
            "answer": answer,
            "sources": sources,
            "searched": searched,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def convert_currency(data):
    amount_text = str(data.get("amount", "")).strip()
    source = str(data.get("source", "TWD")).strip().upper()
    target = str(data.get("target", "JPY")).strip().upper()

    if not amount_text:
        return {"ok": False, "error": "缺少 amount，請輸入要換算的金額。"}

    try:
        amount = float(amount_text)
    except ValueError:
        return {"ok": False, "error": "金額格式不正確，請輸入數字。"}

    if amount < 0:
        return {"ok": False, "error": "金額不能小於 0。"}

    if source not in SUPPORTED_CURRENCIES or target not in SUPPORTED_CURRENCIES:
        return {"ok": False, "error": "目前只支援 TWD、JPY、USD、KRW、EUR、CNY。"}

    if source == target:
        return {
            "ok": True,
            "amount": amount,
            "converted": amount,
            "rate": 1,
            "source": source,
            "target": target,
            "updated_at": "",
        }

    try:
        response = requests.get(
            f"https://open.er-api.com/v6/latest/{source}",
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()

        if payload.get("result") != "success":
            return {"ok": False, "error": "匯率服務暫時無法使用，請稍後再試。"}

        rate = payload.get("rates", {}).get(target)
        if not rate:
            return {"ok": False, "error": f"找不到 {source} 到 {target} 的匯率。"}

        converted = amount * float(rate)
        return {
            "ok": True,
            "amount": amount,
            "converted": converted,
            "rate": float(rate),
            "source": source,
            "target": target,
            "updated_at": payload.get("time_last_update_utc", ""),
        }
    except requests.RequestException:
        return {"ok": False, "error": "無法連線到匯率服務，請確認網路後再試。"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _resolve_city_name(location):
    return CITY_ALIASES.get(location, location)


def _weather_advice(temperature, apparent_temperature, precipitation_probability, weather_code):
    advice = []
    rainy_codes = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}

    if precipitation_probability >= 50 or weather_code in rainy_codes:
        advice.append("帶傘")

    if weather_code in {0, 1, 2} and temperature >= 24 and precipitation_probability < 40:
        advice.append("防曬")

    if apparent_temperature <= 12 or temperature <= 12:
        advice.append("保暖")

    if not advice:
        advice.append("輕便出門")

    return "、".join(advice)


def get_weather(data):
    location = str(data.get("location", "")).strip()
    if not location:
        return {"ok": False, "error": "缺少 location，請輸入城市名稱，例如：那霸、東京。"}

    try:
        common_place = COMMON_WEATHER_PLACES.get(location)
        if common_place:
            latitude, longitude, city_name, country, admin1 = common_place
        else:
            search_name = _resolve_city_name(location)
            geo_payload = _open_meteo_get_json(
                "https://geocoding-api.open-meteo.com/v1/search",
                {
                    "name": search_name,
                    "count": 1,
                    "language": "zh",
                    "format": "json",
                },
            )
            results = geo_payload.get("results") or []

            if not results:
                return {"ok": False, "error": f"找不到「{location}」的天氣位置。"}

            place = results[0]
            latitude = place.get("latitude")
            longitude = place.get("longitude")
            city_name = place.get("name") or location
            country = place.get("country") or ""
            admin1 = place.get("admin1") or ""

        forecast = _open_meteo_get_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": latitude,
                "longitude": longitude,
                "current": ",".join(
                    [
                        "temperature_2m",
                        "relative_humidity_2m",
                        "apparent_temperature",
                        "precipitation",
                        "weather_code",
                    ]
                ),
                "hourly": "precipitation_probability",
                "forecast_days": 1,
                "timezone": "auto",
            },
        )
        current = forecast.get("current") or {}
        hourly = forecast.get("hourly") or {}

        temperature = float(current.get("temperature_2m"))
        apparent_temperature = float(current.get("apparent_temperature"))
        humidity = int(current.get("relative_humidity_2m"))
        weather_code = int(current.get("weather_code"))
        precipitation = float(current.get("precipitation", 0))
        precipitation_values = hourly.get("precipitation_probability") or []
        rain_probability = max(precipitation_values[:6] or [0])

        return {
            "ok": True,
            "location": city_name,
            "country": country,
            "admin1": admin1,
            "temperature": temperature,
            "apparent_temperature": apparent_temperature,
            "humidity": humidity,
            "weather": WEATHER_CODE_LABELS.get(weather_code, "未知天氣"),
            "weather_code": weather_code,
            "precipitation": precipitation,
            "rain_probability": rain_probability,
            "advice": _weather_advice(
                temperature,
                apparent_temperature,
                rain_probability,
                weather_code,
            ),
            "updated_at": current.get("time", ""),
            "timezone": forecast.get("timezone", ""),
        }
    except requests.RequestException as exc:
        try:
            fallback = _weather_from_wttr(location)
            fallback["note"] = f"Open-Meteo 暫時無法使用，已改用免金鑰備援。Open-Meteo 詳細：{_format_request_error(exc)}"
            return fallback
        except requests.RequestException as fallback_exc:
            return {
                "ok": False,
                "error": (
                    "無法連線到 Open-Meteo，也無法使用備援天氣服務。"
                    f"Open-Meteo 詳細：{_format_request_error(exc)}；"
                    f"備援詳細：{_format_request_error(fallback_exc)}"
                ),
            }
    except (TypeError, ValueError):
        return {"ok": False, "error": "Open-Meteo 回傳資料不完整，請稍後再試。"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _translate_with_gemini(prompt):
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "error": "找不到 GEMINI_API_KEY 或 GOOGLE_API_KEY，請先在 .env 設定金鑰。",
        }

    try:
        client = genai.Client(api_key=api_key)
        response = client.interactions.create(
            model=GEMINI_MODEL_NAME,
            system_instruction=SYSTEM_INSTRUCTION,
            input=prompt,
        )

        translation = (response.output_text or "").strip()
        if not translation:
            return {"ok": False, "error": "Gemini 沒有回傳翻譯結果。"}

        return {"ok": True, "translation": translation}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def translate(data):
    load_dotenv()

    text = str(data.get("text", "")).strip()
    source = str(data.get("source", "")).strip()
    target = str(data.get("target", "")).strip()

    if not text:
        return {"ok": False, "error": "缺少 text，請輸入要翻譯的文字。"}

    if not target:
        return {"ok": False, "error": "缺少 target，請指定目標語言。"}

    prompt = _build_prompt(text, source, target)
    provider = os.getenv("TRANSLATION_PROVIDER", "gemini").strip().lower()

    if provider == "openai":
        return _translate_with_openai(prompt)

    if provider == "gemini":
        return _translate_with_gemini(prompt)

    return {
        "ok": False,
        "error": "TRANSLATION_PROVIDER 只支援 openai 或 gemini。",
    }
