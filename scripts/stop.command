#!/bin/bash
# 医疗平台一键停止：停止后端、患者端、医生端和本项目的本地数据库，数据会保留。
#
# macOS：双击项目根目录的“停止医疗平台”，它会在 Ghostty 新窗口中运行本脚本。
# Linux 或终端中：bash scripts/stop.command

set -u
cd "$(dirname "$0")/.." || exit 1

for dir in /opt/homebrew/bin /usr/local/bin \
           /opt/homebrew/opt/postgresql@16/bin /usr/local/opt/postgresql@16/bin \
           /Applications/Postgres.app/Contents/Versions/16/bin \
           /Applications/Postgres.app/Contents/Versions/latest/bin \
           /usr/lib/postgresql/16/bin; do
  if [ -d "${dir}" ] && [[ ":${PATH}:" != *":${dir}:"* ]]; then PATH="${PATH}:${dir}"; fi
done
export PATH

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()  { printf '  \033[32m✓\033[0m %s\n' "$*"; }

say "停止应用服务"
if [ -x .venv/bin/python ] && [ -f .local/services.json ]; then
  .venv/bin/python scripts/dev.py stop >/dev/null
fi
ok "后端、患者端、医生端已停止"

say "停止数据库"
if [ -f .local/postgres/postmaster.pid ] && command -v pg_ctl >/dev/null 2>&1; then
  pg_ctl -D .local/postgres stop -m fast >/dev/null && ok "本地 PostgreSQL 已停止，数据保存在 .local/postgres"
elif command -v docker >/dev/null 2>&1 && docker compose ps -q postgres 2>/dev/null | grep -q .; then
  docker compose stop postgres >/dev/null && ok "Docker 中的 PostgreSQL 已停止，数据保存在 Docker 数据卷中"
else
  ok "本项目的数据库没有在运行"
fi

if [ -t 0 ] && [ -t 1 ]; then printf '\n按回车键关闭此窗口…'; read -r _; fi
