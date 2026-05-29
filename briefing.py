from __future__ import annotations

from datetime import datetime
import re
from typing import Awaitable, Callable

from .config import LifePluginConfig


AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
CITY_DISPLAY_NAMES = {
    "370200": "青岛",
    "440300": "深圳",
    "qingdao": "青岛",
    "shenzhen": "深圳",
}


async def fetch_amap_weather(config: LifePluginConfig) -> str | None:
    if not config.amap_weather_key or not config.amap_weather_city:
        return None

    import aiohttp

    params = {
        "key": config.amap_weather_key,
        "city": config.amap_weather_city,
        "extensions": "base",
        "output": "JSON",
    }
    timeout = aiohttp.ClientTimeout(total=8)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(AMAP_WEATHER_URL, params=params) as response:
            if response.status != 200:
                return None
            data = await response.json(content_type=None)
            if data.get("status") != "1":
                return None
            lives = data.get("lives") or []
            if not lives:
                return None
            item = lives[0]
            weather = item.get("weather", "")
            temperature = item.get("temperature", "?")
            humidity = item.get("humidity", "?")
            winddirection = item.get("winddirection", "")
            windpower = item.get("windpower", "")
            return f"{weather} {temperature}°C，湿度 {humidity}%，{winddirection}风 {windpower} 级"


async def generate_briefing_text(
    *,
    config: LifePluginConfig,
    llm_call: Callable[[str], Awaitable[str | None]],
    plan_context: str = "",
) -> str:
    now = datetime.now()
    date_text = now.strftime("%Y-%m-%d")
    weekday = WEEKDAY_NAMES[now.weekday()]

    weather = await fetch_amap_weather(config)
    weather_line = weather or "天气数据暂不可用"
    return _build_structured_briefing(
        date_text=date_text,
        weekday=weekday,
        city=_display_city(config.weather_city_name, config.amap_weather_city),
        weather_line=weather_line,
        context=plan_context,
    )


def _build_structured_briefing(
    *,
    date_text: str,
    weekday: str,
    city: str,
    weather_line: str,
    context: str,
) -> str:
    context_block = context.strip() or "| 内容 | 时间 |\n|---|---|\n| 暂无今日备忘 | |"
    return (
        f"# 🗓️ {date_text} {weekday}\n\n"
        f"## 📍{city}\n\n"
        f"{_weather_icon(weather_line)} {_weather_sentence(weather_line)}\n\n"
        "## ✅ 待办\n\n"
        f"{context_block}"
    )


def _display_city(city_name: str, adcode: str) -> str:
    raw = (city_name or "").strip()
    mapped = CITY_DISPLAY_NAMES.get(raw.lower()) if raw else None
    if mapped:
        return mapped
    if raw:
        return raw
    return CITY_DISPLAY_NAMES.get(str(adcode).strip(), str(adcode).strip())


def _weather_icon(weather_line: str) -> str:
    if "晴" in weather_line:
        return "☀️"
    if "云" in weather_line or "阴" in weather_line:
        return "🌥️"
    if "雨" in weather_line:
        return "🌧️"
    if "雪" in weather_line:
        return "❄️"
    if "雾" in weather_line or "霾" in weather_line:
        return "🌫️"
    return "🌤️"


def _weather_sentence(weather_line: str) -> str:
    if weather_line == "天气数据暂不可用":
        return "天气数据暂不可用。建议出发前查看实时天气。"

    notes: list[str] = []
    temp_match = re.search(r"(-?\d+(?:\.\d+)?)°C", weather_line)
    humidity_match = re.search(r"湿度\s*(\d+)%", weather_line)
    wind_match = re.search(r"风\s*([0-9]+)", weather_line)
    if temp_match:
        temp = float(temp_match.group(1))
        if temp >= 28:
            notes.append("体感偏热，注意防晒补水")
        elif temp <= 5:
            notes.append("气温偏低，注意保暖")
    if humidity_match:
        humidity = int(humidity_match.group(1))
        if humidity >= 70:
            notes.append("湿度较高")
        elif humidity <= 40:
            notes.append("空气偏干")
    if wind_match and int(wind_match.group(1)) >= 4:
        notes.append("风力略大，注意防风")
    suffix = "，".join(notes) if notes else "留意体感变化"
    return f"{weather_line}。{suffix}。"
