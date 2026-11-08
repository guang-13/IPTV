# 安全策略与加固说明

本项目基于 [Guovin/iptv-api](https://github.com/Guovin/iptv-api) v3.1.0（AGPL-3.0）做安全加固与功能扩展。
本文件说明本分支的安全默认值、行为变更与漏洞报告方式。

## 报告安全问题

请通过 GitHub Issue（标注 `security`）或仓库维护者邮箱私下联系，不要在公开 Issue 中附带可直接利用的细节。
我们会在确认后修复并在 CHANGELOG 的「安全更新」中说明，必要时申请 CVE。

## 本分支的安全默认值

| 配置项 | 默认值 | 作用 | 迁移提示 |
|:--|:--|:--|:--|
| `public_log_access` | `False` | 是否允许非本机客户端读取 `/log/*` | 以前日志随结果页公开；如需继续公开请显式设为 `True` |
| `allow_private_network` | `False` | 是否允许抓取/测速内网与保留地址 | **局域网自建源必须设为 `True`**，否则相关源会被跳过 |
| `allow_local_media` | `True` | 是否允许 `file://` / 本地路径作为推流源 | 仅在使用本地 HLS/录像时开启；公网部署建议 `False` |

新增的可选通知配置：`notify_webhook`、`notify_telegram_bot_token`、`notify_telegram_chat_id`、
`notify_on_success`（默认 `False`）、`notify_on_failure`（默认 `True`）。

## 接口与部署加固

- `/log/*`、`/stat`、`/api/*` 在 nginx 层仅允许 `127.0.0.1` 访问；Flask 侧对日志与控制 API 再做一次 loopback + `Host`/`Origin` 校验。
- `/hls_proxy/<id>` 先校验频道是否存在（不存在立即 404），起流失败立即 503，首帧等待上限 8 秒；gunicorn 改为单 worker + 多线程，避免单个观看请求阻塞全站。
- RTMP 仅允许本机发布：`allow publish 127.0.0.1; deny publish all;`。Docker 默认不映射 1935。
- 出站请求经过 `utils/net_guard.py`：仅允许 http/https，默认拒绝私有/回环/链路本地/保留地址与云元数据端点，`file://` 需显式开启。
- 订阅列表中的 `file:`、`javascript:`、`data:`、`vbscript:` URL 在入库阶段即被丢弃。
- `/logo/*` 只提供常见位图 MIME，SVG/HTML 一律拒绝；响应统一带 `X-Content-Type-Options: nosniff`。
- 容器：`docker-compose.yml` 默认绑定 `127.0.0.1`（用 `BIND_ADDR=0.0.0.0` 显式放开），并启用 `no-new-privileges`；镜像带 `/healthz` HEALTHCHECK。

## 命令行

```bash
python main.py --check-config   # 校验 config.ini 后退出（错误会逐条列出）
python main.py --version        # 显示版本
python main.py --once           # 只跑一次，忽略定时任务
```

健康检查端点：`GET /healthz`（不含路径/URL 等敏感信息）。

## 依赖与发布

- 依赖在 `Pipfile` 中全部 `==` 固定，CI 使用 `pipenv sync --dev` 与 `pipenv verify`。
- 发布工作流限制为 `master` 分支、构建 job 只读、checkout 不持久化凭据。
- 桌面自动更新支持基于 Release `digest` / `SHA256SUMS.txt` 的完整性校验，并做了 Zip Slip/符号链接防护与启动健康检查回滚。
  **注意**：当前仍未引入独立代码签名（见 CHANGELOG「已知限制」），发布账号安全仍是信任根。

## 已知限制

- 出站校验在发起请求前完成，未防御 TOCTOU/DNS rebinding；高安全场景请配合容器出口策略。
- 测速阶段对部分源关闭了 TLS 校验（兼容自签与不规范源站），如需严格校验请改用白名单源。
- 容器仍以 root 运行（nginx 需要写 `/tmp/hls` 与日志）；后续版本将切换到非 root 运行。
