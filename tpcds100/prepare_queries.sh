#!/bin/bash
# usage: prepare_queries.sh <clickhouse|starrocks> <out_dir>
# The 99 standard queries, then the SF10 rewrites for the engine (../tpcds10/queries-<engine>), then the extra
# rewrites that SF100 needed (queries-<engine> here).
set -e
cd "$(dirname "$0")"
mkdir -p "$2"; cp ../tpcds10/queries/q*.sql "$2"/; cp ../tpcds10/queries-$1/q*.sql "$2"/; cp queries-$1/q*.sql "$2"/
echo "$(ls ../tpcds10/queries-$1 | wc -l) + $(ls queries-$1 | wc -l) queries rewritten for $1"
