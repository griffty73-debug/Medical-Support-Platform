#!/bin/bash
# 医疗平台一键启动
#
# macOS：双击项目根目录的“启动医疗平台”，它会在 Ghostty 新窗口中运行本脚本。
# Linux 或终端中：bash scripts/start.command
# 首次运行会安装依赖、生成 .env、创建本地数据库和表结构，并引导创建医生账号；
# 之后每次运行只做检查，然后启动后端、患者端、医生端并打开浏览器。
# 停止服务：双击“停止医疗平台”，或执行 bash scripts/stop.command。

set -u
cd "$(dirname "$0")/.." || exit 1

# 从“访达”启动时，PATH 里常常没有 Homebrew、PostgreSQL 和 nvm 安装的 Node.js
for dir in /opt/homebrew/bin /usr/local/bin \
           /opt/homebrew/opt/postgresql@16/bin /usr/local/opt/postgresql@16/bin \
           /Applications/Postgres.app/Contents/Versions/16/bin \
           /Applications/Postgres.app/Contents/Versions/latest/bin \
           /usr/lib/postgresql/16/bin; do
  if [ -d "${dir}" ] && [[ ":${PATH}:" != *":${dir}:"* ]]; then PATH="${PATH}:${dir}"; fi
done
if ! command -v npm >/dev/null 2>&1 && [ -s "${HOME}/.nvm/nvm.sh" ]; then
  set +u; . "${HOME}/.nvm/nvm.sh" >/dev/null 2>&1; set -u
fi
export PATH

PY=.venv/bin/python
INTERACTIVE=0
if [ -t 0 ] && [ -t 1 ]; then INTERACTIVE=1; fi

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
close_window() {
  if [ "${INTERACTIVE}" = 1 ]; then printf '\n%s' "$1"; read -r _; fi
}
die() {
  printf '\n  \033[31m✗ %s\033[0m\n' "$*"
  close_window '按回车键关闭此窗口…'
  exit 1
}
checksum() { { shasum -a 256 "$1" 2>/dev/null || sha256sum "$1"; } | cut -d' ' -f1; }
wait_url() {
  for _ in $(seq 1 "$2"); do
    curl -fsS -o /dev/null "$1" 2>/dev/null && return 0
    sleep 1
  done
  return 1
}

# 数据库探测：ping / schema / doctors
db_probe() {
  "${PY}" - "$1" <<'PY'
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv('.env')
mode = sys.argv[1]
url = os.environ['DATABASE_URL']
try:
    engine = create_engine(url, connect_args={'connect_timeout': 3} if url.startswith('postgresql') else {})
    with engine.connect() as conn:
        if mode == 'ping':
            print('up')
        elif mode == 'schema':
            from alembic.config import Config
            from alembic.script import ScriptDirectory
            config = Config()
            config.set_main_option('script_location', 'backend/migrations')
            head = ScriptDirectory.from_config(config).get_current_head()
            tables = set(inspect(conn).get_table_names())
            if not tables - {'alembic_version'}:
                print('empty')
            elif 'alembic_version' not in tables:
                print('legacy')
            else:
                current = conn.execute(text('SELECT version_num FROM alembic_version')).scalar()
                print('current' if current == head else 'behind')
        elif mode == 'doctors':
            print(conn.execute(text("SELECT count(*) FROM \"user\" WHERE role = 'doctor'")).scalar())
except Exception as exc:
    print('down' if mode == 'ping' else str(exc).splitlines()[0])
    sys.exit(1)
PY
}

# 从 .env 读取端口等设置，输出 shell 变量赋值
read_settings() {
  "${PY}" - <<'PY'
import shlex
from urllib.parse import urlsplit

from dotenv import dotenv_values

values = dotenv_values('.env')
for key, default in (('FLASK_PORT', '5001'), ('PATIENT_PORT', '5173'), ('DOCTOR_PORT', '5174')):
    print(f'{key}={shlex.quote(values.get(key) or default)}')
host = urlsplit(values.get('DATABASE_URL') or '').hostname or ''
print('DB_LOCAL=' + ('1' if host in ('127.0.0.1', 'localhost') else '0'))
print('HAS_AI_KEY=' + ('1' if (values.get('SILICONFLOW_API_KEY') or '').strip() else '0'))
print('EXAMPLE_SECRET=' + ('1' if (values.get('SECRET_KEY') or '') in ('', 'replace-with-a-long-random-secret') else '0'))
PY
}

say "1/6 检查运行环境"
if [ ! -x "${PY}" ]; then
  command -v python3 >/dev/null 2>&1 || die "未找到 python3。请先安装 Python 3.11 或更高版本（例如 brew install python@3.12）。"
  python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' \
    || die "Python 版本过低：需要 3.11 或更高，当前为 $(python3 -V 2>&1)。"
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  die "未找到 Node.js。请先安装 Node.js 20.19 或更高版本（例如 brew install node）。"
fi
node -e 'const [a, b] = process.versions.node.split(".").map(Number); process.exit(a > 20 || (a === 20 && b >= 19) ? 0 : 1)' \
  || die "Node.js 版本过低：需要 20.19 或更高，当前为 $(node -v)。"
ok "Node.js $(node -v | tr -d v)"

say "2/6 安装依赖"
mkdir -p .local
if [ ! -x "${PY}" ]; then
  echo "  正在创建 Python 虚拟环境 .venv …"
  python3 -m venv .venv || die "创建虚拟环境失败。"
fi
requirements=$(checksum backend/requirements.txt)
if [ "$(cat .local/requirements.sha256 2>/dev/null)" != "${requirements}" ]; then
  echo "  正在安装后端依赖（首次约需 1–2 分钟）…"
  "${PY}" -m pip install --disable-pip-version-check -q -r backend/requirements.txt \
    || die "后端依赖安装失败，请检查网络后重试。"
  echo "${requirements}" > .local/requirements.sha256
fi
ok "后端依赖已就绪（$("${PY}" -V)）"
lockfile=$(checksum frontend/package-lock.json)
if [ ! -d frontend/node_modules ] || [ "$(cat .local/package-lock.sha256 2>/dev/null)" != "${lockfile}" ]; then
  echo "  正在安装前端依赖（首次约需 1–2 分钟）…"
  npm --prefix frontend install --no-audit --no-fund --loglevel=error \
    || die "前端依赖安装失败，请检查网络后重试。"
  checksum frontend/package-lock.json > .local/package-lock.sha256
fi
ok "前端依赖已就绪"

say "3/6 检查配置"
if [ ! -f .env ]; then
  "${PY}" - <<'PY' || die "生成 .env 失败。"
import os
import re
import secrets
from pathlib import Path

text = re.sub(r'^SECRET_KEY=.*$', 'SECRET_KEY=' + secrets.token_urlsafe(48), Path('.env.example').read_text(), flags=re.M)
with os.fdopen(os.open('.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as fh:
    fh.write(text)
PY
  ok "已根据 .env.example 生成 .env，并写入随机 SECRET_KEY"
fi
settings=$(read_settings) || die ".env 无法读取，请检查文件格式。"
eval "${settings}"
ok "端口：后端 ${FLASK_PORT}，患者端 ${PATIENT_PORT}，医生端 ${DOCTOR_PORT}"
if [ "${EXAMPLE_SECRET}" = 1 ]; then
  warn ".env 中的 SECRET_KEY 仍是示例值，请换成随机字符串。已有真实数据时不要更换，否则已加密的身份证号将无法读取。"
fi
if [ "${HAS_AI_KEY}" = 0 ]; then
  warn "未填写 SILICONFLOW_API_KEY：AI 预问诊和 AI 起草不可用，其余功能正常。"
fi

say "4/6 准备数据库"
if [ "$(db_probe ping)" != up ]; then
  [ "${DB_LOCAL}" = 1 ] || die "无法连接 .env 中配置的远程数据库，请检查 DATABASE_URL 和网络。"
  if [ -d .local/postgres ] || command -v initdb >/dev/null 2>&1; then
    echo "  正在启动本项目的本地 PostgreSQL（数据目录 .local/postgres）…"
    "${PY}" scripts/init_db.py >.local/init_db.log 2>&1 \
      || { tail -n 15 .local/init_db.log; die "本地 PostgreSQL 启动失败，日志见 .local/init_db.log 和 .local/postgres.log。"; }
  elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "  正在用 Docker 启动 PostgreSQL …"
    docker compose up -d postgres || die "Docker 中的 PostgreSQL 启动失败。"
  else
    die "数据库没有运行，也没有找到 PostgreSQL 16 命令行工具或正在运行的 Docker。请安装其一：brew install postgresql@16，或安装并打开 Docker Desktop。"
  fi
  for _ in $(seq 1 30); do [ "$(db_probe ping)" = up ] && break; sleep 1; done
  [ "$(db_probe ping)" = up ] || die "数据库仍无法连接，请检查 .env 中的 DATABASE_URL。"
fi
ok "数据库已连接"
state=$(db_probe schema) || die "读取表结构失败：${state}"
case "${state}" in
  empty)
    "${PY}" -m flask --app backend/app.py init-db >>.local/init_db.log 2>&1 \
      || { tail -n 15 .local/init_db.log; die "建表失败，日志见 .local/init_db.log。"; }
    ok "已创建表结构"
    ;;
  legacy|behind)
    echo "  表结构需要升级，先备份数据库再迁移 …"
    "${PY}" scripts/upgrade.py >>.local/init_db.log 2>&1 \
      || { tail -n 15 .local/init_db.log; die "表结构升级失败，备份保存在 .local/backups/，日志见 .local/init_db.log。"; }
    ok "表结构已升级，升级前的备份：$(ls -t .local/backups/*.sql 2>/dev/null | head -n 1)"
    upgraded=1
    ;;
  *)
    ok "表结构已是最新"
    ;;
esac
doctors=$(db_probe doctors) || doctors=0
if [ "${doctors}" = 0 ]; then
  if [ "${INTERACTIVE}" = 1 ]; then
    say "还没有医生账号，现在创建一个（姓名处直接回车可跳过）"
    while :; do
      read -r -p "  医生姓名：" doctor_name
      if [ -z "${doctor_name}" ]; then
        warn "已跳过。稍后可运行：.venv/bin/flask --app backend/app.py create-doctor"
        break
      fi
      read -r -p "  手机号（作为登录账号）：" doctor_phone
      read -r -p "  科室：" doctor_department
      echo "  设置登录密码：至少 8 位，同时包含字母和数字，输入时不显示（Password 输入一次，Repeat 再输入一次）"
      if "${PY}" -m flask --app backend/app.py create-doctor \
           --name "${doctor_name}" --phone "${doctor_phone}" --department "${doctor_department}" >/dev/null; then
        ok "医生账号已创建，登录账号 ${doctor_phone}"
        break
      fi
      warn "创建失败，请按上面的提示重新填写。"
    done
  else
    warn "还没有医生账号。请运行：.venv/bin/flask --app backend/app.py create-doctor"
  fi
else
  ok "已有 ${doctors} 个医生账号"
fi

say "5/6 启动服务"
# 表结构刚升级过，说明代码已更新，先停掉仍在运行的旧版服务
if [ "${upgraded:-0}" = 1 ]; then
  "${PY}" scripts/dev.py stop >/dev/null
  for port in "${FLASK_PORT}" "${PATIENT_PORT}" "${DOCTOR_PORT}"; do
    for _ in $(seq 1 10); do curl -s -o /dev/null -m 1 "http://127.0.0.1:${port}" || break; sleep 1; done
  done
fi
"${PY}" scripts/dev.py start >/dev/null \
  || { "${PY}" scripts/dev.py stop >/dev/null; die "服务启动失败。常见原因是端口被其他程序占用，可在 .env 中修改端口。"; }
wait_url "http://127.0.0.1:${FLASK_PORT}/api/health" 30 \
  || { tail -n 20 .local/backend.log; die "后端没有在 30 秒内就绪，日志见 .local/backend.log。"; }
ok "后端      http://127.0.0.1:${FLASK_PORT}"
wait_url "http://127.0.0.1:${PATIENT_PORT}" 60 \
  || { tail -n 20 .local/patient.log; die "患者端没有在 60 秒内就绪，日志见 .local/patient.log。"; }
ok "患者端    http://127.0.0.1:${PATIENT_PORT}"
wait_url "http://127.0.0.1:${DOCTOR_PORT}" 60 \
  || { tail -n 20 .local/doctor.log; die "医生端没有在 60 秒内就绪，日志见 .local/doctor.log。"; }
ok "医生端    http://127.0.0.1:${DOCTOR_PORT}"

say "6/6 打开浏览器"
opener=$(command -v open || command -v xdg-open || true)
if [ -n "${opener}" ] && [ "${NO_BROWSER:-0}" != 1 ]; then
  "${opener}" "http://127.0.0.1:${PATIENT_PORT}" >/dev/null 2>&1
  "${opener}" "http://127.0.0.1:${DOCTOR_PORT}" >/dev/null 2>&1
  ok "已打开患者端和医生端"
else
  ok "请在浏览器中打开上面的地址"
fi

say "医疗平台已启动"
echo "  患者端  http://127.0.0.1:${PATIENT_PORT}"
echo "  医生端  http://127.0.0.1:${DOCTOR_PORT}"
echo "  日志    .local/backend.log、.local/patient.log、.local/doctor.log"
echo "  停止    双击项目目录中的“停止医疗平台”"
close_window '服务会在后台继续运行。按回车键关闭此窗口…'
