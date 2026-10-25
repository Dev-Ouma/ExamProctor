#!/usr/bin/env bash
# Deploy, roll back and check the ExamProctor service and plugins on a single Moodle host.
#
#   deploy/deploy.sh deploy   user@host   # build images tagged with the git commit, switch to them
#   deploy/deploy.sh rollback user@host   # switch back to the previously deployed tag
#   deploy/deploy.sh status   user@host
#
# Images are tagged by commit, so a rollback is a container restart with the previous tag: no
# rebuild, no database change (schema changes are additive). Moodle plugins cannot be downgraded;
# a plugin problem is handled with the kill switch (docs/runbooks/kill-switch.md).
set -euo pipefail

cmd=${1:?deploy|rollback|status}
host=${2:?user@host}
remote_dir=${REMOTE_DIR:-/opt/examproctor}
moodle_dir=${MOODLE_DIR:-/var/www/html/ouklmsdev}
public_health=${PUBLIC_HEALTH:-https://agiledev.ouk.ac.ke/examproctor-api/v1/health/ready}
root=$(cd "$(dirname "$0")/.." && pwd)

remote() { ssh -o BatchMode=yes "$host" "$@"; }

wait_healthy() {
  for _ in $(seq 1 30); do
    if curl -fsS "$public_health" | grep -q '"status":"ok"'; then echo "healthy"; return 0; fi
    sleep 2
  done
  echo "NOT HEALTHY: $public_health" >&2
  return 1
}

switch_to() {
  local tag=$1
  remote "cd $remote_dir && sudo docker tag examproctor-service:$tag examproctor-service:live && \
    sudo docker compose up -d --no-build service worker && echo $tag | sudo tee current_tag >/dev/null"
}

case $cmd in
  deploy)
    tag=$(git -C "$root" rev-parse --short HEAD)
    if [ -n "$(git -C "$root" status --porcelain -- service moodle)" ]; then
      echo "uncommitted changes under service/ or moodle/; commit first" >&2; exit 1
    fi
    rsync -az --delete --exclude .venv --exclude __pycache__ --exclude tests --exclude models \
      "$root/service" "$root/moodle" "$host:$remote_dir/"
    remote "cd $remote_dir && sudo docker build -q -t examproctor-service:$tag service >/dev/null && \
      (cat current_tag 2>/dev/null || true) | sudo tee previous_tag >/dev/null"
    switch_to "$tag"
    remote "set -e; M=$moodle_dir; sudo rsync -a --delete $remote_dir/moodle/local_examproctor/ \$M/local/examproctor/; \
      sudo rsync -a --delete $remote_dir/moodle/quizaccess_examproctor/ \$M/mod/quiz/accessrule/examproctor/; \
      sudo chown -R www-data:www-data \$M/local/examproctor \$M/mod/quiz/accessrule/examproctor; \
      cd \$M && sudo -u www-data php admin/cli/upgrade.php --non-interactive >/dev/null && \
      sudo -u www-data php admin/cli/purge_caches.php"
    wait_healthy
    echo "deployed $tag"
    ;;
  rollback)
    prev=$(remote "cat $remote_dir/previous_tag 2>/dev/null || true")
    [ -n "$prev" ] || { echo "no previous tag recorded" >&2; exit 1; }
    cur=$(remote "cat $remote_dir/current_tag")
    switch_to "$prev"
    remote "echo $cur | sudo tee $remote_dir/previous_tag >/dev/null"
    wait_healthy
    echo "rolled back $cur -> $prev"
    ;;
  status)
    remote "cd $remote_dir && echo current=\$(cat current_tag 2>/dev/null) previous=\$(cat previous_tag 2>/dev/null) && \
      sudo docker compose ps --format '{{.Service}} {{.Status}}'"
    curl -fsS "$public_health"; echo
    ;;
  *) echo "unknown command $cmd" >&2; exit 2 ;;
esac
