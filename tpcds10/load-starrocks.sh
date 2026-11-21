#!/bin/bash
# Stream Load the dsdgen .dat files into the tpcds database of a StarRocks FE on 127.0.0.1:8030.
# env: DAT_DIR (default /data/tpcds), PARALLEL (files loaded at once, default 8)
# columns.txt lists each table's columns in file order; every row ends with '|', hence the dummy column.
set -eo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
export DIR=${DAT_DIR:-/data/tpcds} HERE; P=${PARALLEL:-8}
load() {
  f=$1; t=$(basename "$f" | sed -E 's/_[0-9]+_[0-9]+\.dat$//')
  cols=$(awk -v t="$t" '$1 == t {print $2}' "$HERE/columns.txt"),dummy
  curl -sS --location-trusted -u root: -H "label: load_$(basename "$f" .dat)_$(date +%s%N)" -H "column_separator:|" \
       -H "columns: $cols" -H "max_filter_ratio: 0" -H "timeout: 3600" -H "Expect: 100-continue" \
       -T "$f" "http://127.0.0.1:8030/api/tpcds/$t/_stream_load" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('$(basename "$f")', r['Status'], r.get('NumberLoadedRows'), r.get('Message','')[:100]); sys.exit(0 if r['Status']=='Success' else 1)"
}
export -f load
ls -S "$DIR"/*.dat | grep -Ev '/dbgen_version_' | xargs -d '\n' -n1 -P "$P" bash -c 'load "$0"'
