#!/bin/bash
# Stream Load each .tbl file through the FE HTTP port. The files end every row with '|', so the
# column list has a trailing dummy column that is not stored.
set -eo pipefail
DIR=${TBL_DIR:-/data/tpch}          # where the .tbl files are (TBL_DIR), PARALLEL=1 loads all tables at once
cols() { case $1 in
  region)   echo "r_regionkey,r_name,r_comment,dummy" ;;
  nation)   echo "n_nationkey,n_name,n_regionkey,n_comment,dummy" ;;
  supplier) echo "s_suppkey,s_name,s_address,s_nationkey,s_phone,s_acctbal,s_comment,dummy" ;;
  customer) echo "c_custkey,c_name,c_address,c_nationkey,c_phone,c_acctbal,c_mktsegment,c_comment,dummy" ;;
  part)     echo "p_partkey,p_name,p_mfgr,p_brand,p_type,p_size,p_container,p_retailprice,p_comment,dummy" ;;
  partsupp) echo "ps_partkey,ps_suppkey,ps_availqty,ps_supplycost,ps_comment,dummy" ;;
  orders)   echo "o_orderkey,o_custkey,o_orderstatus,o_totalprice,o_orderdate,o_orderpriority,o_clerk,o_shippriority,o_comment,dummy" ;;
  lineitem) echo "l_orderkey,l_partkey,l_suppkey,l_linenumber,l_quantity,l_extendedprice,l_discount,l_tax,l_returnflag,l_linestatus,l_shipdate,l_commitdate,l_receiptdate,l_shipinstruct,l_shipmode,l_comment,dummy" ;;
esac; }
load() {
  curl -sS --location-trusted -u root: -H "label: load_${1}_$(date +%s)" -H "column_separator:|" \
       -H "columns: $(cols $1)" -H "max_filter_ratio: 0" -H "timeout: 3600" -H "Expect: 100-continue" \
       -T $DIR/$1.tbl http://127.0.0.1:8030/api/tpch/$1/_stream_load \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('$1', r['Status'], r.get('NumberLoadedRows'), r.get('Message','')[:80]); sys.exit(0 if r['Status']=='Success' else 1)"
}
if [ -n "$PARALLEL" ]; then                  # PARALLEL=1: all eight tables at the same time
  pids=(); for t in region nation supplier customer part partsupp orders lineitem; do load $t & pids+=($!); done
  fail=0; for p in "${pids[@]}"; do wait $p || fail=1; done; exit $fail
fi
for t in region nation supplier customer part partsupp orders lineitem; do load $t; done
