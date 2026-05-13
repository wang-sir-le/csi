# MySQL 后端说明

当前项目已加入 MySQL 数据库后端基础层，数据表结构见 `mysql_schema.sql`，数据库访问模块见 `wifi_sleep_db.py`。

## 1. 安装依赖

```powershell
pip install pymysql
```

## 2. 配置 MySQL 连接

按你的 MySQL 实际密码设置环境变量：

```powershell
$env:WIFI_SLEEP_DB_HOST="127.0.0.1"
$env:WIFI_SLEEP_DB_PORT="3306"
$env:WIFI_SLEEP_DB_USER="root"
$env:WIFI_SLEEP_DB_PASSWORD="你的MySQL密码"
$env:WIFI_SLEEP_DB_NAME="wifi_sleep_monitor"
```

## 3. 初始化数据库

启动看板服务后，在浏览器或接口工具中请求：

```text
POST http://127.0.0.1:8000/api/db/init
```

也可以在 HeidiSQL 中直接执行：

```sql
SOURCE mysql_schema.sql;
```

## 4. 已提供的后端接口

```text
GET  /api/db/status
POST /api/db/init

POST /api/auth/register
POST /api/auth/login

GET   /api/users/{username}
PATCH /api/users/{username}

GET  /api/posts
POST /api/posts
POST /api/posts/{post_id}/like
POST /api/posts/{post_id}/favorite

GET  /api/messages
POST /api/messages
```

## 5. 后续迁移方向

当前前端仍保留 `localStorage` 演示逻辑。下一步应逐步把登录注册、个人资料、作品、点赞、收藏和私信切换到这些 API。
