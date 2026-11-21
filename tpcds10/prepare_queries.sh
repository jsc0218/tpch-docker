#!/bin/bash
# usage: prepare_queries.sh <clickhouse|starrocks> <out_dir>
# Copies the 99 standard queries to <out_dir> and puts the engine's rewritten ones on top.
set -e
cd "$(dirname "$0")"
mkdir -p "$2"; cp queries/q*.sql "$2"/; cp queries-$1/q*.sql "$2"/
echo "$(ls queries-$1 | wc -l) of 99 queries rewritten for $1"
