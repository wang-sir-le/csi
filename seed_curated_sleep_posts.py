from __future__ import annotations

import hashlib
import json
import uuid

import pymysql


VIDEO_SLEEP_HYGIENE = (
    "https://commons.wikimedia.org/wiki/Special:FilePath/"
    "Simpleshow%20%28EN%29%20Foundation%20Sleep%20Hygiene%20160308%201920x1080.webm"
)

IMG_BED_NIGHT = (
    "https://commons.wikimedia.org/wiki/Special:FilePath/"
    "A%20bed%20for%20the%20night%20%28Unsplash%29.jpg"
)
IMG_BEDROOM_NIGHT = (
    "https://commons.wikimedia.org/wiki/Special:FilePath/"
    "Bedroom%20%40%20night%20%283119861751%29.jpg"
)
IMG_COSY_BED = (
    "https://commons.wikimedia.org/wiki/Special:FilePath/"
    "Cozy%20bed%20by%20a%20windowsill%20%28Unsplash%29.jpg"
)
IMG_SLEEPLESS = (
    "https://commons.wikimedia.org/wiki/Special:FilePath/"
    "Sleepless%20nights%20%28Unsplash%29.jpg"
)
IMG_SLEEP_POWER = (
    "https://commons.wikimedia.org/wiki/Special:FilePath/"
    "The%20Power%20of%20Sleep%20Hygiene-%20Why%20a%20Good%20Night%27s%20Rest%20Matters%20%289259797%29.jpg"
)
IMG_SLEEP_POWER_2 = (
    "https://commons.wikimedia.org/wiki/Special:FilePath/"
    "The%20Power%20of%20Sleep%20Hygiene-%20Why%20a%20Good%20Night%E2%80%99s%20Rest%20Matters%20%289259799%29.jpg"
)
IMG_WANDERING_NIGHT = (
    "https://commons.wikimedia.org/wiki/Special:FilePath/"
    "The%20Wandering%20Night%20%28Unsplash%29.jpg"
)
IMG_SLEEP_DEBT = "https://commons.wikimedia.org/wiki/Special:FilePath/Sleep%20debt%20and%20immunity.jpg"


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


def article_sleep_rhythm() -> str:
    return """一、为什么睡眠监测首先要关注“节律”

睡眠质量并不只由某一晚睡了多久决定，更重要的是睡眠节律是否稳定。对于成年人而言，多数公共卫生建议都把每晚至少 7 小时睡眠作为基本参考，但在真实生活中，很多人真正的问题不是某一天少睡，而是入睡时间、起床时间和夜间环境长期不稳定。节律不稳定会让身体难以形成可预测的睡眠-觉醒周期，也会让非接触式监测系统更难区分正常翻身、短暂觉醒和环境扰动。

二、睡眠节律如何影响 WiFi CSI 监测

本项目使用 WiFi CSI 记录人体微动。CSI 信号受到人体姿态、呼吸微动、翻身、离床以及室内多径环境变化的共同影响。如果用户每天在不同时间段开启检测，或者白天也持续采集，数据中会混入大量非睡眠行为，例如走动、拿动设备、多人经过和房门开关。这些行为会造成信号剧烈变化，但它们并不能代表睡眠状态。因此，系统设计为睡前手动开启、醒后手动关闭，本质上是在给模型划定清晰的数据边界。

三、稳定采集的建议流程

第一，发射端和接收端的位置应尽量固定，避免每天移动设备。第二，睡前开启检测后，尽量减少手机、电脑和人员走动造成的额外干扰。第三，连续多晚记录数据，不要只依赖一两次实验结果。第四，将无人、静止、翻身、离床等状态分开采集和标注，避免模型把环境噪声学成动作特征。第五，训练后应查看混淆矩阵，而不仅仅看准确率。如果“无人”和“静止”混淆严重，通常说明静止样本的人体微动较弱，或者无人基线采得不够充分。

四、对本项目落地的意义

睡眠监测不是一个单纯的网页功能，而是硬件、数据、算法和交互流程共同作用的系统。前端的开启按钮、数据库中的检测会话、后端的实时状态接口、社区里的经验记录，都是为了让用户在真实场景中逐步积累可解释的数据。只有数据边界清晰，模型判断出的“静止”“翻身”“无人”才更接近实际睡眠状态。"""


def article_sleep_environment() -> str:
    return """一、卧室环境为什么会影响睡眠与监测结果

睡眠环境会同时影响人的睡眠质量和 WiFi CSI 监测信号。对人而言，过强的光线、过高或过低的温度、突发噪声和睡前屏幕刺激，都可能延迟入睡或增加夜间觉醒。对 CSI 监测而言，房间内物体移动、人员经过、设备位置变化和门窗开合，都会改变无线信号的传播路径。因此，一个稳定的卧室环境不仅有助于睡眠，也能提高本项目状态识别的稳定性。

二、睡前 30 分钟的准备

建议在睡前 30 分钟逐步降低刺激：减少手机和电脑屏幕使用，避免剧烈运动，保持房间光线较暗，并把检测设备放在固定位置。对于本系统，用户可以在准备入睡时点击“开启检测”，系统开始记录 CSI 数据；入睡后不需要额外操作；醒来后点击关闭即可。这样采集到的数据更接近真实睡眠过程，而不是白天活动和夜间睡眠混杂在一起。

三、如何布置设备

如果使用两个 ESP32 接口进行 CSI 采集，建议让信号路径覆盖床铺区域，但不要频繁改变两端距离和角度。发射端和接收端不必贴近人体，重点是保持相对稳定。若模型经常把人体静止误判为无人，可以补充同一房间、同一摆放位置下的无人样本和静止样本，让模型更清楚地学习“环境基线”和“人体微动”的区别。

四、如何解释监测结果

看板中的结果应被理解为状态反馈，而不是医学诊断。系统可以帮助用户观察夜间是否频繁翻身、是否存在较长时间离床、静止状态是否连续等现象。若长期出现明显异常，仍应结合主观感受、作息记录和专业建议综合判断。本项目的价值在于提供一种低成本、非接触、可持续采集的睡眠状态记录方式。"""


def article_data_quality() -> str:
    return """一、为什么数据质量比模型名称更重要

在人体活动识别和睡眠监测任务中，模型名称并不能直接决定项目效果。Random Forest、SVM、KNN 或神经网络都可能得到不错的结果，但前提是训练数据具有清晰标签、稳定采集条件和足够样本量。如果无人样本采得太少，模型就可能把低幅度人体微动误认为无人；如果翻身样本过少，模型就会把较大的环境扰动误认为翻身。数据质量不足时，换更复杂的模型通常不能真正解决问题。

二、本项目应优先补充哪些数据

第一类是无人数据，用于建立房间环境基线。第二类是静止数据，用于学习人体呼吸和微动造成的小幅波动。第三类是翻身或体动数据，用于学习较明显的短时变化。第四类是干扰数据，例如有人经过床边、设备轻微移动、房门开关等，用于帮助模型识别非睡眠动作。若时间有限，至少要保证无人、静止、翻身三类样本在同一设备摆放条件下都能覆盖。

三、评价模型时应看什么

准确率只能说明总体判断比例，不能说明哪一类错得多。睡眠监测更应该看混淆矩阵、Precision、Recall 和 F1-score。比如“翻身”的召回率低，说明真实翻身没有被及时识别；“无人”的精确率低，说明系统经常把其他状态误报为无人。针对这些问题，应回到数据采集阶段补样本，而不是只调整前端显示。

四、形成可落地系统的路线

本项目当前已经具备硬件采集、特征构建、模型训练、实时看板、MySQL 存储和社区展示功能。下一步应继续围绕真实使用场景积累夜间数据，并把每次检测会话保存到数据库中。随着样本增加，可以逐步引入个体化模型，使同一用户的长期监测结果更稳定、更有解释性。"""


def main() -> None:
    pwd = hashlib.sha256("official123".encode()).hexdigest()
    users = [
        ("wifi_sleep_official", pwd, "WiFiSleep官方", "官", "官方账号，发布系统功能、睡眠知识和监测建议。"),
        ("sleep_science", pwd, "睡眠科普官", "眠", "整理睡眠卫生、节律管理和卧室环境优化内容。"),
        ("csi_lab", pwd, "CSI微动实验室", "研", "关注 WiFi CSI 微动感知、睡眠体动识别和非接触式监测实验。"),
        ("sleep_health_center", pwd, "睡眠健康中心", "健", "发布睡眠卫生、夜间监测和非接触式感知相关内容。"),
    ]
    posts = [
        {
            "username": "sleep_science",
            "title": "整篇文章：稳定睡眠节律，才是监测准确的基础",
            "content": article_sleep_rhythm() + "\n\n参考方向：CDC Sleep、NIH/NHLBI Healthy Sleep Habits、Mayo Clinic Sleep Tips。",
            "media_url": IMG_COSY_BED,
            "media_type": "image/jpeg",
            "media_name": "cozy-bed-windowsill.jpg",
        },
        {
            "username": "sleep_health_center",
            "title": "整篇文章：卧室环境如何同时影响睡眠和 CSI 信号",
            "content": article_sleep_environment() + "\n\n参考方向：CDC Sleep Hygiene、Mayo Clinic 睡眠建议。",
            "media_url": IMG_BED_NIGHT,
            "media_type": "image/jpeg",
            "media_name": "bed-night-unsplash.jpg",
        },
        {
            "username": "csi_lab",
            "title": "整篇文章：数据质量比模型名称更重要",
            "content": article_data_quality() + "\n\n参考方向：本项目 CSI 采集流程、分类评估指标和睡眠监测使用场景。",
            "media_url": IMG_SLEEP_DEBT,
            "media_type": "image/jpeg",
            "media_name": "sleep-debt-immunity.jpg",
        },
        {
            "username": "sleep_science",
            "title": "视频：Sleep Hygiene 睡眠卫生科普",
            "content": (
                "这是一条真正的视频内容，不是 GIF。视频来自 Wikimedia Commons 的 Sleep Hygiene 科普视频，"
                "适合放在社区中作为睡前习惯、规律作息和睡眠卫生的科普素材。视频重点说明良好睡眠习惯对入睡和睡眠质量的意义，"
                "与本项目“睡前开启检测、醒后关闭检测”的交互逻辑一致。来源页面："
                "https://commons.wikimedia.org/wiki/File:Simpleshow_(EN)_Foundation_Sleep_Hygiene_160308_1920x1080.webm"
            ),
            "media_url": VIDEO_SLEEP_HYGIENE,
            "media_type": "video/webm",
            "media_name": "sleep-hygiene-video.webm",
        },
        {
            "username": "wifi_sleep_official",
            "title": "多图：非接触式睡眠监测内容图集",
            "content": (
                "这条帖子使用多图内容展示不同睡眠场景：夜间床铺、卧室环境、失眠场景、睡眠卫生科普图和夜间环境。"
                "每张图都来自不同文件，避免重复素材。点击帖子详情后可查看完整多图内容。"
            ),
            "media_url": json.dumps(
                [
                    {"url": IMG_BEDROOM_NIGHT, "name": "Bedroom at night"},
                    {"url": IMG_SLEEPLESS, "name": "Sleepless nights"},
                    {"url": IMG_SLEEP_POWER, "name": "Power of sleep hygiene"},
                    {"url": IMG_SLEEP_POWER_2, "name": "Sleep hygiene matters"},
                    {"url": IMG_WANDERING_NIGHT, "name": "The wandering night"},
                ],
                ensure_ascii=False,
            ),
            "media_type": "application/json+multi-image",
            "media_name": "curated-sleep-gallery",
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
        cur.execute("DELETE FROM posts")
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
    print(json.dumps({"posts": len(posts), "video": VIDEO_SLEEP_HYGIENE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
