#!/bin/bash
# The survivor round's model switcher, on Adlerbot (README, "Run protocol"). Sherlock's runner asks
# for a model by requesting http://192.168.40.110:8080/runner/load/<name>: the server answers 404
# and logs the request, and this script, watching that log, serves the model (.mlx_active_config,
# with its published sampling from models.txt, then a restart). Once it answers, its memory and
# the swap it added go to results/loads.tsv. A request for production, or 76 h, puts production
# back and ends the script. One copy runs at a time.
set -u
cd "$(dirname "$0")" || exit 1
LOG=~/scripts-llm/mlx-server.err CONF=~/scripts-llm/.mlx_active_config
PROD_MODEL=mlx-community/Qwen3.8-27B-4bit PROD_CACHE=16
# Elsewhere (an optional secondary server, as its own user): no launchd service and no sudo, so this script
# runs the server itself, with run-mlx's settings, from ~/mlx; prompt cache at most 8 GB.
# That host's own model service restarts any server it stops, so its admin stops it first.
SELF=""; [ "$(id -un)" = adlerbot ] || SELF=1
MLX=~/mlx/bin CACHE_CAP=8
END_AT=$(( $(date +%s) + 273600 ))   # 76 h: the round's 72 h and some
mkdir -p results; TSV=results/loads.tsv
mkdir results/adlerbot.lock 2>/dev/null || { p=$(cat results/adlerbot.lock/pid 2>/dev/null)
    echo "another adlerbot.sh holds the lock (pid ${p:-unknown}, $(kill -0 "${p:-0}" 2>/dev/null && echo running || echo "not running: if none is, rm -r results/adlerbot.lock"))"; exit 1; }
echo $$ > results/adlerbot.lock/pid
[ -f "$TSV" ] || printf 'time\tname\tmodel\tanswered\tmemory_gb\tswap_added_mb\tsampling\n' > "$TSV"

say() { echo "$(date '+%F %T') $*"; }
model_of() { awk -v n="$1" '$1==n{print $2}' models.txt; }
cache_of() { awk -v n="$1" '$1==n{print $3}' models.txt; }
sampling_of() { awk -v n="$1" '$1==n{print $4}' models.txt; }
swap_mb() { sysctl -n vm.swapusage | awk '{for(i=1;i<NF;i++) if($i=="used") {v=$(i+2); sub(/M/,"",v); print int(v)}}'; }
memory_gb() {  # the server's processes, physical footprint (top's MEM)
    for p in $(pgrep -f 'mlx_lm.server|ollama (serve|runner)'); do top -l 1 -pid "$p" -stats mem | tail -1; done |
        awk '/^[0-9.]+[KMG][+-]?$/{v=$1; sub(/[+-]$/,"",v); u=substr(v,length(v)); n=substr(v,1,length(v)-1)+0;
              s+= u=="G" ? n : u=="M" ? n/1024 : u=="K" ? n/1048576 : 0} END{printf "%.1f", s}'
}
serve() {  # model cache-GB [temp/top-p/top-k]
    { printf 'MODEL="%s"\nPROMPT_CACHE_GB=%s\n' "$1" "$2"
      case ${3:--} in -) ;; *) IFS=/ read -r t p k <<< "$3"; printf 'TEMP=%s TOP_P=%s TOP_K=%s\n' "$t" "$p" "$k" ;; esac
    } > "$CONF" || return 1
    [ -n "$SELF" ] || { sudo -n /bin/launchctl kickstart -k system/com.mlx.server; return; }
    local t=0.7 p=0.8 k=20 c=$2 i
    case ${3:--} in -) ;; *) IFS=/ read -r t p k <<< "$3" ;; esac
    case $1 in */*) ;; *) say "$1 is an Ollama model: not served here"; return 1 ;; esac
    [ "$c" -gt $CACHE_CAP ] && c=$CACHE_CAP
    pkill -f '[m]lx_lm.server --model'
    for i in $(seq 60); do nc -z 127.0.0.1 8080 2>/dev/null || break; sleep 1; done
    sleep 3; nc -z 127.0.0.1 8080 2>/dev/null && { say "something else holds :8080 once the server stopped"; return 1; }
    say "starting $1 here: sampling $t/$p/$k, prompt cache $c GB"
    (nohup "$MLX/mlx_lm.server" --model "$1" --max-tokens 8192 --chat-template-args '{"enable_thinking": false}' \
        --temp "$t" --top-p "$p" --top-k "$k" --decode-concurrency 1 --prompt-concurrency 1 --prefill-step-size 1024 \
        --prompt-cache-size 4 --prompt-cache-bytes $(( c * 1073741824 )) --host 0.0.0.0 --port 8080 \
        >> ~/scripts-llm/mlx-server.log 2>> "$LOG" < /dev/null &)
}
answers() {  # model: generates, 20 min at most
    local t=$(( $(date +%s) + 1200 ))
    while [ "$(date +%s)" -lt $t ]; do
        sleep 10
        curl -sf -m 120 http://127.0.0.1:8080/v1/chat/completions -H 'Content-Type: application/json' \
            -d "{\"model\":\"$1\",\"max_tokens\":2,\"messages\":[{\"role\":\"user\",\"content\":\"Say ok.\"}]}" >/dev/null && return 0
    done
    return 1
}
restore() { trap - EXIT INT TERM; serve "$PROD_MODEL" "$PROD_CACHE" && say "restored production: $PROD_MODEL" || say "could not restore production"; rm -rf results/adlerbot.lock; }
trap restore EXIT
trap 'exit 130' INT TERM

if [ -n "$SELF" ]; then   # the server's requests must reach $LOG: start it from here
    say "$(id -un): mlx $("$MLX/python" -c 'import mlx.core, mlx_lm; print(mlx.core.__version__, "mlx-lm", mlx_lm.__version__)' 2>&1)"
    serve "$PROD_MODEL" "$PROD_CACHE" && answers "$PROD_MODEL" || { say "could not start the server here"; exit 1; }
fi
say "watching $LOG for load requests"
off=$(stat -f %z "$LOG")
while [ "$(date +%s)" -lt $END_AT ]; do
    sleep 5
    sz=$(stat -f %z "$LOG"); [ "$sz" -lt "$off" ] && off=0; [ "$sz" -gt "$off" ] || continue
    name=$(tail -c +$((off + 1)) "$LOG" | head -c $((sz - off)) | grep -oE 'GET /runner/load/[A-Za-z0-9_-]+' | tail -1 | sed 's|.*/||')
    off=$sz
    [ -n "$name" ] || continue
    [ "$name" = production ] && { say "production requested"; exit 0; }
    model=$(model_of "$name")
    [ -n "$model" ] || { say "ignored a request for $name: not in models.txt"; continue; }
    say "serving $name ($model, sampling $(sampling_of "$name"))"; s0=$(swap_mb)
    serve "$model" "$(cache_of "$name")" "$(sampling_of "$name")" || { say "restart failed"; continue; }
    if answers "$model"; then ok=yes; else ok=no; fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date '+%F %T')" "$name" "$model" "$ok" "$(memory_gb)" $(( $(swap_mb) - s0 )) "$(sampling_of "$name")" | tee -a "$TSV"
    # Requests made while it loaded: for the same model, Sherlock waiting for it (skipped); for
    # another, a new request, read on the next pass.
    sz=$(stat -f %z "$LOG")
    again=$(tail -c +$((off + 1)) "$LOG" | head -c $((sz - off)) | grep -oE 'GET /runner/load/[A-Za-z0-9_-]+' | tail -1 | sed 's|.*/||')
    [ -n "$again" ] && [ "$again" != "$name" ] || off=$sz
done
say "stopped at the 76 h limit"
