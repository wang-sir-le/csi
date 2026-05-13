from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import hashlib
import json
import uuid

import pymysql


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "web_assets"


def font(size: int):
    for path in [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def make_demo_gif() -> None:
    output = ASSETS / "sleep_monitor_demo.gif"
    if output.exists():
        return
    title_font = font(36)
    text_font = font(24)
    frames = []
    states = [
        ("无人", "环境基线稳定", (116, 195, 232)),
        ("静止", "人体微动感知", (158, 231, 197)),
        ("翻滚", "体动状态识别", (255, 207, 122)),
        ("离床", "夜间异常提醒", (255, 151, 151)),
    ]
    for idx in range(24):
        state, desc, color = states[(idx // 6) % len(states)]
        img = Image.new("RGB", (960, 540), (11, 18, 28))
        draw = ImageDraw.Draw(img)
        for y in range(0, 540, 18):
            shade = 16 + y // 20
            draw.line((0, y, 960, y), fill=(shade, shade + 5, shade + 10))
        draw.text((52, 50), "WiFiSleep CSI 实时检测演示", fill=(235, 248, 255), font=title_font)
        draw.text((52, 104), f"当前状态：{state}", fill=color, font=title_font)
        draw.text((52, 156), desc, fill=(190, 205, 216), font=text_font)
        base_y = 355
        for x in range(52, 908, 18):
            t = (x + idx * 20) / 52
            y = base_y + int(42 * __import__("math").sin(t))
            draw.ellipse((x, y, x + 7, y + 7), fill=color)
        draw.rectangle((52, 428, 908, 462), outline=(88, 108, 124), width=2)
        draw.rectangle((56, 432, 56 + idx * 35, 458), fill=(116, 232, 200))
        draw.text((52, 482), "睡前开启检测，醒后关闭，减少白天数据混入。", fill=(220, 230, 238), font=text_font)
        frames.append(img)
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=120, loop=0)


def connect():
    return pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="henu",
        database="wifi_sleep_monitor",
        charset="utf8mb4",
        autocommit=False,
    )


def main() -> None:
    make_demo_gif()
    pwd = hashlib.sha256("official123".encode()).hexdigest()
    users = [
        ("sleep_health_center", pwd, "睡眠健康中心", "健", "发布睡眠卫生、夜间监测和非接触式感知相关内容。"),
        ("wifi_sleep_video", pwd, "WiFiSleep视频号", "影", "用于发布项目动态演示、检测流程和操作说明。"),
    ]
    posts = [
        {
            "username": "sleep_health_center",
            "title": "长文本：如何让 CSI 睡眠监测数据更稳定？",
            "content": (
                "要让无源 WiFi 睡眠监测结果更稳定，核心不是单纯增加模型复杂度，而是保证采集条件一致。"
                "第一，路由器或发射端、接收端与床的位置应尽量固定，避免每天移动设备导致信道基线变化。"
                "第二，睡前开启检测，醒后关闭检测，减少白天走动、多人经过、拿动设备等非睡眠行为混入。"
                "第三，建议连续采集多晚数据，把无人、静止、翻滚、离床等状态分开标注，避免模型把环境扰动误认为人体动作。"
                "第四，训练模型时不仅看准确率，也要关注混淆矩阵，尤其要观察“无人”和“静止”是否容易混淆。"
                "如果这两类混淆严重，通常说明环境基线样本不足，或者静止样本中人体微动幅度较小，需要补充同一场景下的无人数据和安静卧床数据。"
                "因此，本项目更适合采用夜间手动开启的方式，在真实睡眠场景中逐步积累个人化数据。"
            ),
            "media_url": "/assets/forest.jpeg",
            "media_type": "image/jpeg",
            "media_name": "forest.jpeg",
        },
        {
            "username": "wifi_sleep_video",
            "title": "动态演示：睡前开启检测到状态识别",
            "content": (
                "这是一段项目动态演示素材，用于展示从开启检测、串口采集、CSI 波动到状态输出的基本流程。"
                "实际落地时，用户只需要在睡前点击开启检测，系统会持续读取 ESP32 CSI 数据，并在看板中更新当前状态、有效包数和运行时长。"
            ),
            "media_url": "/assets/sleep_monitor_demo.gif",
            "media_type": "image/gif",
            "media_name": "sleep_monitor_demo.gif",
        },
        {
            "username": "sleep_health_center",
            "title": "多图：睡眠监测部署场景参考",
            "content": (
                "多图内容用于展示项目的三个关键场景：睡眠环境、WiFi 感知链路和夜间状态记录。"
                "社区外层只展示摘要，点击帖子后可以进入详情页查看完整图集和说明。"
            ),
            "media_url": json.dumps(
                [
                    {"url": "/assets/forest.jpeg", "name": "安静睡眠环境"},
                    {"url": "/assets/living_wifi.jpeg", "name": "WiFi 感知链路"},
                    {"url": "/assets/sleep_wifi.jpeg", "name": "非接触式监测"},
                    {"url": "/assets/stars.jpeg", "name": "夜间记录"},
                ],
                ensure_ascii=False,
            ),
            "media_type": "application/json+multi-image",
            "media_name": "sleep-gallery",
        },
        {
            "username": "wifi_sleep_official",
            "title": "长文本带图：为什么本项目要设计手动开启检测？",
            "content": (
                "睡眠监测系统如果全天候无差别采集，会把大量白天活动数据混入夜间睡眠数据中。"
                "例如白天经过床边、移动设备、多人同时在房间内活动，都可能改变 WiFi 多径传播环境。"
                "这些变化虽然会让 CSI 信号产生明显波动，但它们并不代表睡眠中的翻身、静止或离床行为。"
                "因此，本项目把“开启检测”按钮放在主界面显眼位置，让用户在真正准备睡觉时主动开启，醒来后关闭。"
                "这种设计能减少无关数据，提高训练样本质量，也更符合睡眠监测的实际使用流程。"
                "从建模角度看，数据边界越清晰，模型越容易学习到稳定可解释的状态差异。"
            ),
            "media_url": "/assets/sleep_wifi.jpeg",
            "media_type": "image/jpeg",
            "media_name": "sleep_wifi.jpeg",
        },
    ]
    conn = connect()
    try:
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT INTO users(username, password_hash, nickname, avatar_text, bio)
            VALUES(%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              nickname=VALUES(nickname),
              avatar_text=VALUES(avatar_text),
              bio=VALUES(bio)
            """,
            users,
        )
        titles = [post["title"] for post in posts]
        cur.execute(
            "DELETE FROM posts WHERE title IN (" + ",".join(["%s"] * len(titles)) + ")",
            titles,
        )
        cur.executemany(
            """
            INSERT INTO posts(id, username, title, content, media_url, media_type, media_name)
            VALUES(%s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    "post_" + uuid.uuid4().hex,
                    post["username"],
                    post["title"],
                    post["content"],
                    post["media_url"],
                    post["media_type"],
                    post["media_name"],
                )
                for post in posts
            ],
        )
        conn.commit()
    finally:
        conn.close()
    print(json.dumps({"seeded_posts": len(posts), "gif": "/assets/sleep_monitor_demo.gif"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
