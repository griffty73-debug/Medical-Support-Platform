# 医疗平台

线上问诊与随访平台。患者描述症状、经过预问诊后提交给指定医生；医生接诊、沟通、撰写并审核发布报告，按需安排随访。

Vue 3 + Vite 前端（患者端、医生端两个入口），Flask + SQLAlchemy 后端，PostgreSQL 16 数据库，Alembic（Flask-Migrate）管理表结构。

## 本地地址

| 服务 | 地址 |
| --- | --- |
| 患者端 | http://127.0.0.1:5173 |
| 医生端 | http://127.0.0.1:5174 |
| Flask API | http://127.0.0.1:5001/api/health |
| PostgreSQL | 127.0.0.1:5433，数据库 `medical_treatment` |

本项目使用独立的本地数据目录 `.local/postgres`，不影响本机 5432 上已有的数据库。

## 一键启动

需要先装好 Node.js 20.19+、Python 3.11+，以及 PostgreSQL 16 命令行工具或 Docker（macOS 上 `brew install node python@3.12 postgresql@16`）。终端使用 [Ghostty](https://ghostty.org)，建议 1.3 或更高版本。

- 启动：在“访达”中双击项目根目录的 **启动医疗平台**，它会打开一个 Ghostty 新窗口运行 `scripts/start.command`。脚本按顺序检查环境、安装或更新依赖、首次运行时生成 `.env`（自动写入随机 `SECRET_KEY`）、启动本项目的数据库、建表或升级表结构（升级前自动备份）、没有医生账号时引导创建，最后启动三个服务并打开患者端和医生端。再次运行只做检查，已在运行的服务不会重复启动。
- 停止：双击 **停止医疗平台**，在 Ghostty 中运行 `scripts/stop.command`，停止后端、两个前端和本项目的数据库，数据保留。
- Linux 或已打开的终端中：`bash scripts/start.command`、`bash scripts/stop.command`；设置 `NO_BROWSER=1` 可不打开浏览器。

第一次双击时，macOS 会询问是否允许“启动医疗平台”（或“停止医疗平台”）控制 Ghostty，选择“允许”。如果没有允许，或 Ghostty 低于 1.3，会改由 Ghostty 直接打开脚本，Ghostty 会请你确认运行；没有安装 Ghostty 时使用系统“终端”。双击后没有反应时，查看 `.local/launcher.log`。

如果 macOS 提示无法打开这两个应用，在项目目录执行一次：

```bash
xattr -dr com.apple.quarantine *.app && chmod +x *.app/Contents/MacOS/run scripts/*.command
```

AI 预问诊和 AI 起草需要在 `.env` 中填写 `SILICONFLOW_API_KEY`，未填写时其余功能照常可用。日志在 `.local/` 目录下。

## 手动安装

要求 Node.js 20.19+、Python 3.11+、PostgreSQL 16 命令行工具（或 Docker）。

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend install
cp .env.example .env            # 填写 SECRET_KEY 与 AI 密钥
.venv/bin/python scripts/init_db.py                 # 创建本地 PostgreSQL（使用 Docker 时改为 docker compose up -d）
.venv/bin/flask --app backend/app.py init-db        # 建表
.venv/bin/flask --app backend/app.py create-doctor  # 创建医生账号
.venv/bin/python scripts/dev.py start
```

`SECRET_KEY` 用于签发登录令牌和加密身份证号，更换后已加密的身份证号将无法读取。

## 从旧版本升级

旧版本没有迁移记录。升级命令会先用 `pg_dump` 备份到 `.local/backups/`，再把已有数据库标记为基线版本并执行迁移，原有用户、病例、报告和附件都会保留：

```bash
.venv/bin/pip install -r backend/requirements.txt   # 新增 Flask-Migrate
.venv/bin/python scripts/upgrade.py
.venv/bin/python scripts/dev.py stop && .venv/bin/python scripts/dev.py start
```

迁移时，旧版本中未发布病例的报告内容会转为医生草稿，已完成病例记为第 1 版报告，等待接诊的病例补上响应时限。回滚方法写在 `scripts/upgrade.py` 的说明里。以后调整表结构时执行 `flask db migrate -m "说明"` 生成迁移，检查后再 `flask db upgrade`。

## 病例流程

```
            ┌── 退回 ──► 已退回 ──► 患者改投其他医生 ──┐
            │                                         ▼
提交 ──► 待接诊 ──► 接诊 ──► 评估中 ──► 发布报告 ──► 已完成 ──► 更正报告（第 2、3… 版）
            ▲    │             │  ▲                    │
            │    └─ 转诊 ──────┤  └─ 患者补充 ◄─ 待补充资料
            └──────────────────┘                       └──► 随访到期 ──► 患者发起复诊（关联原病例）
患者可在完成前随时撤回。
```

- 所有状态变化由后端 `workflow.py` 中的状态机统一校验，接口返回当前用户可执行的操作，前端只显示这些按钮。
- 医生可以退回（需写原因，患者可改投）、转诊（交给其他医生，原医生失去访问权限，草稿不随之转移）、请患者补充资料。
- 报告分为草稿（仅医生可见）和已发布内容。草稿保存使用版本号防止并发覆盖；发布必须选择线下就诊建议和随访安排，并确认已逐项审核。
- 已发布的报告只能通过“更正”修改：必须填写原因，生成新版本并通知患者，所有版本保留在修改记录中。
- 报告设置随访天数后，患者在到期前两天看到提醒，可基于原病例发起复诊，医生在复诊中能看到上次报告。
- 医患沟通在病例进行中开放；报告发布后继续开放 7 天，设有随访的开放到随访日后 7 天。之后需要发起复诊。
- 医生可以暂停接诊，暂停期间患者不能选择该医生，已接收的病例照常处理。

## 预问诊与紧急程度

1. 规则检查始终运行，不调用第三方服务：识别胸痛、呼吸困难、意识障碍、卒中表现、出血、严重过敏、孕期出血腹痛、心理危机等危险信号，能识别“无胸痛”“既往骨折”这类否定和既往史表述。命中紧急信号时，患者需确认已了解就医提示才能继续；心理危机提示心理援助热线 12356 与 110 / 120。
2. AI 预问诊需要患者主动开启：给出建议科室、2–5 个补充问题和给医生的病情摘要。AI 只能调高紧急程度，不能调低规则结果。结果与所评估的文本绑定，患者修改描述或撤回 AI 授权后失效。
3. 紧急程度决定医生队列排序和响应时限：紧急 2 小时、尽快 12 小时、常规 48 小时，超时会在队列中标出。医生可以调整分级。

## AI 与数据处理

文本默认使用 `Qwen/Qwen3-8B`，有图片附件时使用 `Qwen/Qwen3-VL-8B-Instruct`，可在 `.env` 中修改。发送给 AI 的内容包括病情描述、预问诊问答、医患沟通、附件以及年龄、性别、过敏史、既往史、用药；不包括姓名、手机号和身份证号，但附件本身可能含有这些信息。

“向医生提供资料”和“第三方 AI 处理”是两项独立授权：前者必选，后者可选。未授权 AI 的病例，医生端不提供 AI 起草。授权时间与版本随病例保存。AI 失败时显示实际原因，不生成替代内容。发布时记录医生对 AI 草稿的修改比例。

## 安全与审计

- 密码使用 scrypt 哈希，需同时包含字母和数字；连续 5 次输错锁定 15 分钟；登录、注册、AI 调用和消息发送均有频率限制。
- 修改密码或“退出其他设备”会使旧登录令牌立即失效。
- 身份证号使用 Fernet 加密存储，校验位与出生日期，性别和年龄由身份证号自动得出。接口默认只返回部分号码，查看完整号码会记录审计日志。医生端看到的患者手机号同样经过遮罩。
- 医生查看病例、下载附件和报告、查看完整身份证号、使用 AI 都会写入审计日志。患者可以在病例的“处理记录”中看到谁查看过自己的资料。管理员可以执行 `flask --app backend/app.py audit-log --case 12` 查看。
- 病例提交时保存健康档案快照，之后修改档案不影响已提交的病例。

## 验证

```bash
.venv/bin/pytest backend/tests -q                                   # 默认使用内存 SQLite
TEST_DATABASE_URL=postgresql+psycopg://…/medical_test .venv/bin/pytest backend/tests -q   # 在 PostgreSQL 上运行同一套测试
npm --prefix frontend run build
node frontend/tests/e2e.mjs                                          # 只读：登录与注册页在 320–1440px 的布局
```

`e2e.mjs --full` 会注册测试账号并走完整的患者 ⇄ 医生流程，只能在服务连接一次性数据库时运行：

```bash
E2E_ALLOW_WRITES=yes E2E_DOCTOR_PHONE=… E2E_DOCTOR_PASSWORD=… node frontend/tests/e2e.mjs --full
```

`scripts/check_vision.py` 用一张合成图片验证视觉模型配置。

### 危险信号规则评测

```bash
.venv/bin/python scripts/eval_redflags.py          # 120 条合成测试语句：平台规则与“仅关键词匹配”的对比
.venv/bin/python scripts/eval_redflags.py --json   # 机器可读的结果
```

测试集 `eval/redflag_cases.csv` 由团队按平台的三级分级标准构造并标注，未经医生审定，只反映软件行为，不代表临床效果。脚本不需要数据库和 AI 凭证。

## 账号

患者自行注册。医生账号由维护者创建，防止冒充：`flask --app backend/app.py create-doctor`。医生的姓名、职称和科室由维护者维护，医生本人可以修改擅长领域和接诊状态。

## 正式使用前仍需完成

医生资质核验流程、HTTPS 部署、短信验证码登录与账号找回、多进程部署时把频率限制放到 Redis、定期备份与恢复演练、附件病毒扫描、数据保留期限与账号注销流程，以及按适用法规（如互联网诊疗相关规定、个人信息保护法）完成合规评估。
