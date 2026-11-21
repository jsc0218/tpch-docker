#!/bin/bash
# Load the dsdgen .dat files into the tpcds database of the ClickHouse container "ch".
# env: DAT_DIR (default /data/tpcds), PARALLEL (files loaded at once, default 8)
# The files end every row with '|', hence input_format_csv_allow_variable_number_of_columns.
set -eo pipefail
DIR=${DAT_DIR:-/data/tpcds}; P=${PARALLEL:-8}
load() {
  f=$1; t=$(basename "$f" | sed -E 's/_[0-9]+_[0-9]+\.dat$//')
  docker exec -i ch clickhouse-client --format_csv_delimiter='|' --input_format_csv_allow_variable_number_of_columns=1 \
    --database tpcds -q "INSERT INTO $t FORMAT CSV" < "$f" || { echo "FAILED $f" >&2; exit 1; }
}
export -f load; export DIR
# big tables first so that the long loads overlap with the small ones
ls "$DIR"/*.dat | grep -Ev '/dbgen_version_' | xargs -d '\n' ls -S | xargs -P "$P" -I{} bash -c 'load {}'
until [ "$(docker exec ch clickhouse-client -q 'select count() from system.merges')" = 0 ]; do sleep 2; done
