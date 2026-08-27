---
name: red-book-skills
description: |
  将图文/视频内容自动发布到小红书（XHS），并支持登录检查、内容检索与互动操作。
  适用场景：发布图文、发布视频、仅启动测试浏览器、获取登录二维码、首页推荐抓取、搜索笔记、评论互动、抓取内容数据。
metadata:
  trigger: 发布内容到小红书
  source: Angiin/Post-to-xhs
---

# Post-to-xhs

你是“小红书发布助手”。目标是在用户确认后，调用本 Skill 的脚本完成发布或互动操作。

## 风险提示（重要）

**使用本 Skill 进行小红书自动化，存在被平台风控、限流、封号或封禁账号的风险。**

默认提醒用户优先使用测试号、小流量运行，并对最终内容进行人工复核。使用者需自行评估并承担相关风险。

## 输入判断

优先按以下顺序判断：
1. 用户明确要求"测试浏览器 / 启动浏览器 / 检查登录 / 获取登录二维码 / 只打开不发布"：进入测试浏览器流程。
2. 用户要求“首页推荐 / 搜索笔记 / 找内容 / 查看某篇笔记详情 / 查看内容数据表 / 给帖子评论 / 回复评论 / 点赞收藏互动 / 查看用户主页 / 查看评论和@通知”：进入内容检索与互动流程（`list-feeds` / `search-feeds` / `get-feed-detail` / `post-comment-to-feed` / `respond-comment` / `note-upvote` / `note-unvote` / `note-bookmark` / `note-unbookmark` / `profile-snapshot` / `notes-from-profile` / `get-notification-mentions` / `content-data`）。
3. 用户已提供 `标题 + 正文 + 视频(本地路径或 URL)`：直接进入视频发布流程。
4. 用户已提供 `标题 + 正文 + 图片(本地路径或 URL)`：直接进入图文发布流程。
5. 用户只提供网页 URL：先提取网页内容与图片/视频，再给出可发布草稿，等待用户确认。
6. 信息不全：先补齐缺失信息，不要直接发布。

## 必做约束

- 发布前必须让用户确认最终标题、正文和图片/视频。
- 图文发布时，没有图片不得发布（小红书发图文必须有图片）。
- 视频发布时，没有视频不得发布。图片和视频不可混合使用（二选一）。
- 默认使用无头模式；若检测到未登录，切换有窗口模式登录。
- 直接调用 `cdp_publish.py` 或 `publish_pipeline.py` 时，统一使用 `<XiaohongshuSkills 根目录>/.venv/bin/python`；系统 `python3` 缺少 `websockets.sync` 的导入错误发生在浏览器连接之前，可安全换解释器重试。
- 标题长度不超过 38（中文/中文标点按 2，英文数字按 1）。
- 用户要求"仅测试浏览器"时，不得触发发布命令。
- 如使用文件路径，优先使用绝对路径；若用户给的是相对路径，先转换为绝对路径再执行命令。
- 若发布页结构异常，优先检查 `scripts/cdp_publish.py` 里的 `SELECTORS`、多图上传等待、正文编辑器与发布按钮点击逻辑；这些是最容易被小红书网页改版影响的区域。
- 2026-08 版创作者中心可能将底部操作区渲染为 `xhs-publish-btn` Web Component；当前脚本会读取其 `submit-disabled` / `submit-loading` 属性，并派发组件公开的 composed `publish` 事件。仅点击 closed Shadow DOM 内的按钮可能不会进入页面提交逻辑。
- AI 辅助或合成内容发布时，给 `publish_pipeline.py` 传 `--content-declaration "笔记含AI合成内容"`，并在点击发布前确认该声明已选中。
- 当任务明确要求“无需声明”时，不要把“无需声明”作为 `--content-declaration` 参数值：当前发布器只接受平台列出的四个声明文案。应省略该参数，继续保留其他已要求的发布设置（如原创声明、地点）。
- 需要确认提交是否进入平台时，运行 `cdp_publish.py verify-note --title "最终标题"`，以笔记管理页的“审核中 / 已发布 / 未通过”分栏为准。
- 发布成功必须观察到 `POST /web_api/sns/v2/note` 的成功响应；仅记录到按钮点击不得报告成功。
- `click-publish` 必须提供 `--title`，脚本会拒绝非发布页或标题不匹配的表单，避免连接到错误标签页。
- `content-data` 是统计接口；显式页面内请求若返回 `406`，新版脚本会自动回退到浏览器页面原生网络捕获。若最终输出 `CONTENT_DATA_RESULT` 且 `capture_mode: "network_capture"`，可使用该列表做只读去重与统计；若回退也失败，才将统计列表视为暂不可用。无论哪种情况，都不能据此断言笔记未发或重复点击发布；发布核验应先读取本次 `publish_receipt`，再用 `verify-note --title` 核验精确标题。
- 笔记管理页的 `posted` 列表首请求也可能短暂返回 `406`，使 DOM 显示“全部 0”。`verify-note` 会重放页面原生导航并捕获浏览器自身的列表响应；不得用单独 `fetch` 伪造动态安全头，也不得记录 Cookie 或安全头。
- 发布进程超时、stdout 为空、或已进入 `verify-note` 而未形成收据时，状态属于“不确定提交”：保留草稿与封面，只轮询同一精确标题，禁止重新上传或重提。仅在确认没有上传、没有 `POST /web_api/sns/v2/note` 且本地完整历史去重通过后，才可重新提交一次。
- 若 `POST /web_api/sns/v2/note` 返回 HTTP 200，但业务体为 `success: false`、`result: -14000`、`need_retry: false`，并提示“今日发布数达到上限”，这是确定的日限额硬失败，不是不确定提交。不得在同一自然日重试或换稿绕过；保留标题、正文、封面与失败响应，把内容落盘为 Markdown，并等待下一次独立任务重新选题或由用户明确安排后续处理。
- 若超时发生在上传预览尚未出现阶段，先执行同一精确标题的 `verify-note`；确认 `found: false` 且日志中没有 `POST /web_api/sns/v2/note` 后，才允许保留原图进行一次完整重试。不可把“图片已提交到文件输入框”当作已发布。
- 若连续出现“等待上传预览”但 `Runtime.evaluate` 在短于预览轮询总时限时先超时，应检查发布器的单次 CDP 命令上限是否低于上传渲染所需时间；提高该上限后，仍须先做精确标题核验，并且每篇最多完整重试一次。
- 清理积压草稿时，先分为“已核验发布”“提交状态不确定”“从未提交”；不得把历史候选批量灌入账号。每篇从未提交稿都要重新做来源时效、语义去重、标题/正文/封面预检后，单篇提交并完整核验。

## 测试浏览器流程（不发布）

1. 启动 post-to-xhs 专用 Chrome（默认有窗口模式，便于人工观察）。
2. 如用户要求静默运行，再使用无头模式。
3. 可选：执行登录状态检查并回传结果。
4. 结束后如用户要求，关闭测试浏览器实例。

## 图文发布流程

1. 准备输入（标题、正文、图片 URL 或本地图片）。
2. 如需文件输入，先写入 `title.txt`、`content.txt`。
3. 执行发布命令（默认无头）。
4. 回传执行结果（成功/失败 + 关键信息）。

## 视频发布流程

1. 准备输入（标题、正文、视频文件路径或 URL）。
2. 如需文件输入，先写入 `title.txt`、`content.txt`。
3. 执行视频发布命令（默认无头）。视频上传后需等待处理完成。
4. 回传执行结果（成功/失败 + 关键信息）。

## 内容检索与互动流程（搜索/详情/评论/内容数据）

1. 先检查小红书主页登录状态（`XHS_HOME_URL`，非创作者中心）。
2. 若用户需要首页推荐流，执行 `list-feeds` 获取首页推荐笔记列表。
3. 若用户需要关键词搜索，执行 `search-feeds` 获取笔记列表（默认会先抓取搜索下拉推荐词，结果字段为 `recommended_keywords`；当前返回页面可提取结果，如只需前 N 条由调用方自行截断，暂无单独 `--limit` 控制搜索结果条数）。
4. 若用户需要详情，从搜索结果中取 `id` + `xsecToken` 再执行 `get-feed-detail`；如用户明确要更多评论，可加 `--load-all-comments` 等参数。
5. 若用户需要发表评论，执行 `post-comment-to-feed`（一级评论；必填 `feed_id` / `xsec_token` / `content`）。
6. 若用户需要回复某条评论，执行 `respond-comment`（可用 `comment_id` / `comment_author` / `comment_snippet` 定位目标评论）。
7. 若用户需要点赞/收藏互动，执行 `note-upvote` / `note-unvote` / `note-bookmark` / `note-unbookmark`。
8. 若用户需要用户主页信息，执行 `profile-snapshot` 或 `notes-from-profile`。
9. 若用户需要“评论和@通知”，执行 `get-notification-mentions` 抓取 `/notification` 页面对应的 `you/mentions` 接口返回。
10. 若用户需要“笔记基础信息表”，执行 `content-data` 获取曝光/观看/点赞等指标。
11. 回传结构化结果（数量、核心字段、链接）。

## 常用命令

### 参数顺序提醒（`cdp_publish.py` / `publish_pipeline.py`）

请严格按下面顺序写命令，避免 `unrecognized arguments`：

- 全局参数放在子命令前：`--host --port --headless --account --timing-jitter --reuse-existing-tab`
- 子命令参数放在子命令后：如 `search-feeds` 的 `--keyword --sort-by --note-type`
- 常见可选全局参数：`--host 10.0.0.12 --port 9222 --reuse-existing-tab --account NAME`

示例（正确）：

```bash
python scripts/cdp_publish.py --reuse-existing-tab search-feeds --keyword "春招" --sort-by 最新 --note-type 图文
```

### 0) 启动 / 测试浏览器（不发布）

默认 CDP 地址为 `127.0.0.1:9222`；可按需叠加 `--host` / `--port` 指向远程 Chrome。

```bash
# 启动测试浏览器（有窗口，推荐）
python scripts/chrome_launcher.py

# 可选：无头启动
python scripts/chrome_launcher.py --headless

# 检查当前登录状态
python scripts/cdp_publish.py check-login

# 常见变体：优先复用已有标签页
python scripts/cdp_publish.py --reuse-existing-tab check-login

# 远程 CDP 检查登录
python scripts/cdp_publish.py --host 10.0.0.12 --port 9222 check-login

# 获取登录二维码（返回 Base64，可供远程前端展示扫码）
python scripts/cdp_publish.py get-login-qrcode

# 重启 / 关闭测试浏览器
python scripts/chrome_launcher.py --restart
python scripts/chrome_launcher.py --kill
```

### 0.5) 首次登录 / 重新登录

```bash
# 本地 Chrome 登录
python scripts/cdp_publish.py login

# 远程 CDP 登录（不会自动重启远程 Chrome）
python scripts/cdp_publish.py --host 10.0.0.12 --port 9222 login
```

#### macOS 专用窗口闪退恢复

若发布器的专用 Chrome 窗口一闪即退、9222 随即不可用，而主 Chrome 正常运行，先确认没有进程使用该专用 `user-data-dir`。这通常是 macOS 将普通 Chrome 启动请求交给主 Chrome，而不是浏览器网页崩溃。备份（不要直接删除）该专用目录内确认无主的 `SingletonLock`、`SingletonSocket`、`SingletonCookie`，随后用 `open -na 'Google Chrome' --args --remote-debugging-port=9222 --user-data-dir=<专用目录> ...` 强制新应用实例。确认 `http://127.0.0.1:9222/json/version` 在 10 秒后仍可访问，再导航到登录页。当前 `chrome_launcher.py` 已在 macOS 自动采用该启动方式；不要复制主 Chrome 的 Cookie 或改动主配置。

### 1) 准备 title.txt / content.txt

若用户给的是标题和正文，可先写入临时文件再执行命令：

```bash
printf '%s\n' '这里是标题' > /abs/path/title.txt
printf '%s\n' '这里是正文' > /abs/path/content.txt
```

### 2) 无头发布 or 有头预览 —— 使用图片 URL 发布

```bash
# 默认推荐：无头自动发布
python scripts/publish_pipeline.py --headless \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --image-urls "https://example.com/1.jpg" "https://example.com/2.jpg"

# 仅预览：停留在发布页人工确认
python scripts/publish_pipeline.py \
  --preview \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --image-urls "https://example.com/1.jpg" "https://example.com/2.jpg"

# 常见变体：远程 CDP / 复用已有标签页
python scripts/publish_pipeline.py --host 10.0.0.12 --port 9222 --reuse-existing-tab \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --image-urls "https://example.com/1.jpg"
```

说明：当 `--host` 不是 `127.0.0.1/localhost` 时，脚本会跳过本地 `chrome_launcher.py` 的自动启动/重启逻辑。
说明：`publish_pipeline.py` 默认自动点击发布；如需停留在发布页人工确认，请加 `--preview`。

### 3) 无头发布 or 有头预览 —— 使用本地图片发布

```bash
# 本地图片发布
python scripts/publish_pipeline.py --headless \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --images "/abs/path/pic1.jpg" "/abs/path/pic2.jpg" \
  --content-declaration "笔记含AI合成内容" \
  --location "上海交通大学(闵行本部校区)" \
  --location-address "上海市闵行区东川路800号"

# WSL/远程 CDP + Windows/UNC 路径：跳过本地文件预校验
python scripts/publish_pipeline.py --headless \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --images "\\\\wsl.localhost\\Ubuntu\\home\\user\\pic1.jpg" \
  --skip-file-check
```

说明：当控制端在 WSL 运行，且传入 Windows/UNC 路径（如 `\\wsl.localhost\...`）时，可加 `--skip-file-check`，避免 Linux 侧 `os.path.isfile()` 误判不存在。
说明：脚本会自动识别 `C:\...`、`\\wsl.localhost\...` 等 Windows/UNC 路径，并在传给 `DOM.setFileInputFiles` 时保留原始路径形态。
说明：若需要强制保留原始路径，也可显式加 `--preserve-upload-paths`。

### 3.5) 视频发布（本地视频文件 / 视频 URL）

```bash
# 本地视频文件
python scripts/publish_pipeline.py --headless \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --video "/abs/path/my_video.mp4"

# 视频 URL
python scripts/publish_pipeline.py --headless \
  --title-file /abs/path/title.txt \
  --content-file /abs/path/content.txt \
  --video-url "https://example.com/video.mp4"
```

### 4) 多账号发布 / 切换

```bash
python scripts/cdp_publish.py list-accounts
python scripts/cdp_publish.py add-account work --alias "工作号"
python scripts/cdp_publish.py --port 9223 --account work login
python scripts/publish_pipeline.py --port 9223 --account work --headless --title-file /abs/path/title.txt --content-file /abs/path/content.txt --image-urls "https://example.com/1.jpg"
```

### 5) 搜索内容 / 获取笔记详情

```bash
# 首页推荐笔记
python scripts/cdp_publish.py list-feeds

# 搜索笔记
python scripts/cdp_publish.py search-feeds --keyword "春招"

# 常见变体：带筛选 + 复用标签页
python scripts/cdp_publish.py --reuse-existing-tab search-feeds --keyword "春招" --sort-by 最新 --note-type 图文

# 获取笔记详情（feed_id 与 xsec_token 来自搜索结果）
python scripts/cdp_publish.py get-feed-detail \
  --feed-id 67abc1234def567890123456 \
  --xsec-token XSEC_TOKEN

# 可选：滚动加载更多一级评论，并尝试展开二级回复
python scripts/cdp_publish.py get-feed-detail \
  --feed-id 67abc1234def567890123456 \
  --xsec-token XSEC_TOKEN \
  --load-all-comments \
  --limit 20 \
  --click-more-replies \
  --reply-limit 10 \
  --scroll-speed normal
```

说明：`list-feeds` 返回首页推荐 feed 列表。
说明：`search-feeds` 输出中包含 `recommended_keywords_count` 与 `recommended_keywords`，表示回车前搜索框下拉推荐词。
说明：`search-feeds` 返回当前页面可提取到的结果，不提供单独的 `--limit` 条数控制；若只需前 N 条，请在调用方截断返回列表。
说明：`get-feed-detail --load-all-comments` 会先滚动评论区，并可选点击“更多回复”后再提取详情，同时额外返回 `comment_loading`。
说明：`check-login` 与主页登录检查默认启用本地缓存（12h，仅缓存“已登录”），到期后自动重新网页校验。

### 6) 给笔记发表评论（一级评论）

```bash
# 直接传评论文本
python scripts/cdp_publish.py post-comment-to-feed \
  --feed-id 67abc1234def567890123456 \
  --xsec-token XSEC_TOKEN \
  --content "写得很实用，感谢分享"

# 使用文件传评论（适合多行文本）
python scripts/cdp_publish.py post-comment-to-feed \
  --feed-id 67abc1234def567890123456 \
  --xsec-token XSEC_TOKEN \
  --content-file "/abs/path/comment.txt"
```

### 7) 获取内容数据表（content_data）

```bash
# 获取笔记基础信息表（曝光/观看/封面点击率/点赞/评论/收藏/涨粉/分享/人均观看时长/弹幕）
python scripts/cdp_publish.py content-data

# 下划线别名
python scripts/cdp_publish.py content_data

# 可选：导出 CSV
python scripts/cdp_publish.py --reuse-existing-tab content-data --csv-file "/abs/path/content_data.csv"
```

### 7.5) 核验笔记提交状态

```bash
python scripts/cdp_publish.py --reuse-existing-tab verify-note \
  --title "最终发布标题" \
  --timeout-seconds 40
```

### 8) 获取评论和@通知（notification mentions）

```bash
# 抓取 /notification 页面触发的 you/mentions 接口数据
python scripts/cdp_publish.py get-notification-mentions

# 下划线别名
python scripts/cdp_publish.py get_notification_mentions
```

### 9) 评论回复 / 点赞收藏 / 用户主页信息

```bash
# 回复评论（支持按评论 ID / 作者 / 文本片段定位）
python scripts/cdp_publish.py respond-comment \
  --feed-id 67abc1234def567890123456 \
  --xsec-token XSEC_TOKEN \
  --comment-id COMMENT_ID \
  --content "感谢反馈～"

# 点赞 / 取消点赞
python scripts/cdp_publish.py note-upvote --feed-id 67abc1234def567890123456 --xsec-token XSEC_TOKEN
python scripts/cdp_publish.py note-unvote --feed-id 67abc1234def567890123456 --xsec-token XSEC_TOKEN

# 收藏 / 取消收藏
python scripts/cdp_publish.py note-bookmark --feed-id 67abc1234def567890123456 --xsec-token XSEC_TOKEN
python scripts/cdp_publish.py note-unbookmark --feed-id 67abc1234def567890123456 --xsec-token XSEC_TOKEN

# 用户主页快照 / 用户主页笔记
python scripts/cdp_publish.py profile-snapshot --user-id USER_ID
python scripts/cdp_publish.py notes-from-profile --user-id USER_ID --limit 20 --max-scrolls 3
```

补充：更完整的背景说明、安装说明与面向人工阅读的示例可参考 `README.md`，但本文件中的命令样例应优先作为 agent 执行基线。

## 失败处理

- 依赖或导入阶段失败（特别是 `ModuleNotFoundError: websockets.sync`，或 macOS `/usr/bin/python3` 报 `TypeError: unsupported operand type(s) for |`）：先确认执行脚本的 Python 与安装依赖的 Python 是同一个解释器，并至少支持 Python 3.10 的联合类型语法。优先用 `<XiaohongshuSkills 根目录>/.venv/bin/python` 执行 `publish_pipeline.py`、`cdp_publish.py` 及 `-m pip install -r requirements.txt`；不要使用调用方工作区中名称相似的虚拟环境。若 `.venv` 不存在，使用可用的 Python 3.10+ 在 Skill 根目录创建后再安装依赖。这类错误发生在连接浏览器之前，不会产生平台笔记；修复运行时后可安全重试，不要误判为登录失效或页面选择器变更。
- 登录失败：提示用户重新扫码登录并重试；若用户需要远程展示二维码，可改用 `get-login-qrcode`。
- 图片/视频下载失败：提示更换 URL 或改用本地文件。
- 本地路径不可用：优先改用绝对路径；若为 WSL/远程 CDP 的 Windows/UNC 路径，可先尝试 `--skip-file-check`，必要时再加 `--preserve-upload-paths`。
- 评论/回复目标未定位成功：提示补充 `comment_id`，或改用 `comment_author` / `comment_snippet` 再试。
- 页面选择器失效：提示检查 `scripts/cdp_publish.py` 中选择器并更新。
- 话题选择响应超时：不要重新填表或重复提交；复用同一发布页，并从原生话题锚点核对该话题是否已选中。只有锚点不存在时才补选一次，随后继续声明、地点与发布流程。
- 长时间发布/核验命令：执行宿主可能先于浏览器自动化进程返回，不能把“命令结束”或“无终端输出”当作发布结果。应保存命令输出到临时日志并检查实际进程是否退出；只有日志中观察到 `POST /web_api/sns/v2/note` 成功响应，并以 `verify-note` 对精确标题复核成功，才记录为已发布。若复核为 `found: false` 且未观察到 POST 成功，才可在重启浏览器后做一次恢复性重试。
- 若发布包装器在表单填写前的只读去重阶段报告 `Another publish process is running (pid=...)`，不得终止该进程或绕过锁。先等待并只读确认该 PID 是否仍存活；若它已自然退出，再用新标签运行一次 `content-data` 或精确标题核验。只有目标标题不存在、本轮没有上传/POST/收据且浏览器锁已释放时，才允许一次完整提交；若 PID 仍存活则继续等待，不并发填表。
- 只读 `content-data` 在 `--reuse-existing-tab` 模式下若连接到陈旧发布页，并在 `Page.enable` 阶段超时，说明该标签的 CDP 会话不可用，不等同于登录失败，也不代表统计接口无数据。先确认没有发布进程持锁；锁释放后去掉 `--reuse-existing-tab`，用新标签页重试一次。不得为只读去重检查终止正在运行的发布进程。
- 若只读 `content-data` 探针在受限执行环境中报告 Chrome 已启动但 9222 端口未响应，不要据此判定登录失效，也不要在同一受限环境反复拉起浏览器。保留该诊断；当任务已获发布授权时，改在获准的 GUI/网络执行上下文运行一次完整的已验证发布包装器，让包装器重新启动或复用 Chrome，并自行完成发布前去重、POST 捕获和发布后核验。只有包装器仍无法连接时，才进入浏览器启动故障排查；不得因探针失败重复提交。
