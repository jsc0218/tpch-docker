#!/bin/bash
# Time the 99 queries with a cold start for each one: restart the engine, drop the OS page cache, run the
# query once (cold), then WARM more times (default 3). Also records how much the data disk read during the
# cold run and during the warm runs. If the cold run fails or times out, the warm runs are skipped.
#
# usage: run_cold.sh <clickhouse|starrocks> <query_dir> <out_dir> <data_disk, e.g. nvme1n1>
# needs: the engine container running (ch or starrocks), the tpcds-harness image, sudo
# env: WARM (default 3), TIMEOUT (seconds per query, default 600), ONLY (comma list of query numbers)
set -e
engine=$1; qdir=$(realpath "$2"); out=$(realpath "$3"); disk=$4
WARM=${WARM:-3}; TIMEOUT=${TIMEOUT:-600}; ONLY=${ONLY:-$(seq -s, 1 99)}
CH_SETTINGS='{"join_use_nulls":1,"group_by_use_nulls":1,"cast_keep_nullable":1,"union_default_mode":"DISTINCT","max_bytes_before_external_group_by":5000000000,"max_bytes_before_external_sort":5000000000}'
case $engine in clickhouse) name=ch ;; starrocks) name=starrocks ;; *) echo "unknown engine"; exit 1 ;; esac
mkdir -p "$out"; echo "query,cold_mib_read,warm_mib_read" > "$out/disk_mib.csv"
sectors() { awk '{print $3}' /sys/block/$disk/stat; }      # sectors read so far (512 bytes each)
mib() { echo $(( ($2 - $1) * 512 / 1048576 )); }
ready() {
  if [ $engine = clickhouse ]; then
    until docker exec $name clickhouse-client -q 'select 1' >/dev/null 2>&1; do sleep 1; done
  else
    until docker exec $name mysql -h127.0.0.1 -P9030 -uroot -N -e "show backends" 2>/dev/null | grep -q true; do sleep 2; done
    until docker exec $name mysql -h127.0.0.1 -P9030 -uroot -N -e "select count(*) from tpcds.date_dim" >/dev/null 2>&1; do sleep 2; done
  fi
}
harness() {   # $1 = query number, $2 = runs, $3 = output file
  docker run --rm --network container:$name -e RUNS=$2 -e ONLY=$1 -e TIMEOUT=$TIMEOUT -e CH_SETTINGS="$CH_SETTINGS" \
    -v "$qdir":/q:ro -v "$out":/out tpcds-harness $engine /q /out/$3 | grep -E "^q[0-9]+ "
}
for q in ${ONLY//,/ }; do
  docker restart -t 60 $name >/dev/null; ready
  sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null; sleep 2
  a=$(sectors); harness $q 1 cold_q$q.json; b=$(sectors)          # run 1: cold
  if python3 -c "import json,sys; sys.exit(1 if json.load(open('$out/cold_q$q.json'))['$q']['error'] else 0)"; then
    harness $q $WARM warm_q$q.json >/dev/null                      # runs 2 and on: warm
  fi
  c=$(sectors)
  echo "Q$q,$(mib $a $b),$(mib $b $c)" >> "$out/disk_mib.csv"
done
python3 "$(dirname "$(realpath "$0")")/merge.py" "$out" "$engine"
