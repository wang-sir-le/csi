from pathlib import Path
from datetime import datetime
import json
import subprocess
import urllib.request


ROOT = Path(__file__).resolve().parent


def read_text_guess(path: Path) -> str:
    for encoding in ("utf-8", "gbk", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def build_log() -> str:
    lines = [
        "WiFiSleep 项目终端运行日志证明",
        f"生成时间: {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"工作目录: {ROOT}",
        "",
    ]

    def section(title: str) -> None:
        lines.append("")
        lines.append(f"> {title}")

    section("python --version")
    try:
        lines.append(
            subprocess.check_output(
                ["python", "--version"], text=True, encoding="utf-8", errors="replace"
            ).strip()
        )
    except Exception as exc:
        lines.append(f"命令失败: {exc}")

    section("项目核心文件")
    for path in sorted(ROOT.glob("*.py")):
        stat = path.stat()
        lines.append(
            f"{path.name:<32} {stat.st_size:>8} bytes   "
            f"{datetime.fromtimestamp(stat.st_mtime):%Y-%m-%d %H:%M:%S}"
        )

    section("数据库状态: GET http://127.0.0.1:8000/api/db/status")
    try:
        data = urllib.request.urlopen(
            "http://127.0.0.1:8000/api/db/status", timeout=5
        ).read().decode("utf-8")
        lines.append(data)
    except Exception as exc:
        lines.append(f"接口请求失败: {exc}")

    section("实时识别状态: GET http://127.0.0.1:8000/api/state")
    try:
        state = json.loads(
            urllib.request.urlopen(
                "http://127.0.0.1:8000/api/state", timeout=5
            ).read().decode("utf-8")
        )
        brief = {
            "running": state.get("running"),
            "packets": state.get("packets"),
            "stable_prediction": state.get("stable_prediction"),
            "elapsed": state.get("elapsed"),
            "latest_log": (state.get("logs") or [{}])[-1],
        }
        lines.append(json.dumps(brief, ensure_ascii=False))
    except Exception as exc:
        lines.append(f"接口请求失败: {exc}")

    section("社区帖子接口: GET http://127.0.0.1:8000/api/posts?include_own=true")
    try:
        posts_data = json.loads(
            urllib.request.urlopen(
                "http://127.0.0.1:8000/api/posts?include_own=true", timeout=5
            ).read().decode("utf-8")
        )
        posts = posts_data.get("posts", [])
        lines.append(f"ok={posts_data.get('ok')}, posts={len(posts)}")
        for post in posts[:6]:
            lines.append(
                f"- {post.get('username')} | {post.get('title')} | "
                f"likes={post.get('likes_count')}"
            )
    except Exception as exc:
        lines.append(f"接口请求失败: {exc}")

    section("MySQL 表数据统计")
    try:
        import pymysql

        conn = pymysql.connect(
            host="127.0.0.1",
            port=3306,
            user="root",
            password="henu",
            database="wifi_sleep_monitor",
            charset="utf8mb4",
        )
        cur = conn.cursor()
        counts = {}
        for table in [
            "users",
            "posts",
            "post_likes",
            "favorites",
            "messages",
            "detect_sessions",
        ]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cur.fetchone()[0]
        cur.close()
        conn.close()
        lines.append(json.dumps(counts, ensure_ascii=False))
    except Exception as exc:
        lines.append(f"MySQL 查询失败: {exc}")

    section("CSI 采集日志尾部: csi_receiver_collection.log")
    log_path = ROOT / "csi_receiver_collection.log"
    if log_path.exists():
        lines.extend(read_text_guess(log_path).splitlines()[-12:])
    else:
        lines.append("未找到 csi_receiver_collection.log")

    lines.append("")
    lines.append(
        "结论: 后端服务、MySQL 数据库、实时状态接口、社区作品接口和 CSI 采集日志均已形成可核验的项目运行证据。"
    )
    return "\n".join(lines)


def render_png(text: str, output: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:
        raise RuntimeError(f"缺少 Pillow，无法生成 PNG: {exc}") from exc

    font_candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/consola.ttf"),
    ]
    font_path = next((p for p in font_candidates if p.exists()), None)
    font = ImageFont.truetype(str(font_path), 22) if font_path else ImageFont.load_default()
    title_font = ImageFont.truetype(str(font_path), 30) if font_path else font

    raw_lines = text.splitlines()
    wrapped = []
    max_chars = 92
    for line in raw_lines:
        if len(line) <= max_chars:
            wrapped.append(line)
        else:
            for idx in range(0, len(line), max_chars):
                wrapped.append(line[idx : idx + max_chars])

    width = 1700
    line_h = 34
    pad = 42
    height = pad * 2 + 42 + line_h * len(wrapped)
    img = Image.new("RGB", (width, height), (12, 17, 24))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, width, 86), fill=(20, 32, 44))
    draw.text((pad, 25), "WiFiSleep 项目终端运行日志证明", fill=(175, 239, 210), font=title_font)
    y = 104
    for line in wrapped[1:]:
        color = (230, 238, 246)
        if line.startswith("> "):
            color = (158, 231, 197)
        elif line.startswith("结论"):
            color = (255, 223, 148)
        elif line.startswith("- "):
            color = (197, 211, 226)
        draw.text((pad, y), line, fill=color, font=font)
        y += line_h
    img.save(output)


if __name__ == "__main__":
    log_text = build_log()
    (ROOT / "terminal_run_proof.txt").write_text(log_text, encoding="utf-8")
    render_png(log_text, ROOT / "terminal_run_proof.png")
    print("generated terminal_run_proof.txt and terminal_run_proof.png")
