#!/bin/bash
# Time the 22 queries with a cold start for each one: restart the engine, drop the OS page cache,
# run the query once (cold), then five more times (warm). Also records how much the data disk read
# during the cold run and during the five warm runs.
#
# usage: run_cold.sh <clickhouse|starrocks> <query_dir> <out_dir> <data_disk, e.g. nvme1n1>
# needs: the engine container running (ch or starrocks), the tpch-harness image, sudo
set -e
engine=$1; qdir=$(realpath "$2"); out=$(realpath "$3"); disk=$4
case $engine in clickhouse) name=ch ;; starrocks) name=starrocks ;; *) echo "unknown engine"; exit 1 ;; esac
mkdir -p "$out"; : > "$out/disk_mib.csv"; echo "query,cold_mib_read,warm_mib_read" > "$out/disk_mib.csv"
sectors() { awk '{print $3}' /sys/block/$disk/stat; }      # sectors read so far (512 bytes each)
mib() { echo $(( ($2 - $1) * 512 / 1048576 )); }
ready() {
  if [ $engine = clickhouse ]; then
    until docker exec $name clickhouse-client -q 'select 1' >/dev/null 2>&1; do sleep 1; done
  else
    until docker exec $name mysql -h127.0.0.1 -P9030 -uroot -N -e "show backends" 2>/dev/null | grep -q true; do sleep 2; done
    until docker exec $name mysql -h127.0.0.1 -P9030 -uroot -N -e "select count(*) from tpch.region" >/dev/null 2>&1; do sleep 2; done
  fi
}
harness() {   # $1 = query number, $2 = runs, $3 = output file
  docker run --rm --network container:$name -e RUNS=$2 -e ONLY=$1 -e TIMEOUT=900 \
    -e CH_SETTINGS='{"join_use_nulls":1}' -v "$qdir":/q:ro -v "$out":/out tpch-harness $engine /q /out/$3 | grep -E "^q[0-9]+ "
}
for q in $(seq 1 22); do
  docker restart -t 60 $name >/dev/null; ready
  sync; echo 3 | sudo tee /proc/sys/vm/drop_caches >/dev/null; sleep 2
  a=$(sectors); harness $q 1 cold_q$q.json; b=$(sectors)          # run 1: cold
  harness $q 5 warm_q$q.json >/dev/null; c=$(sectors)              # runs 2 to 6: warm
  echo "Q$q,$(mib $a $b),$(mib $b $c)" >> "$out/disk_mib.csv"
done
python3 "$(dirname "$(realpath "$0")")/merge.py" "$out" "$engine"
