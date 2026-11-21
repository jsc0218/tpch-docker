#!/usr/bin/env python3
"""Write schema-clickhouse.sql and schema-starrocks.sql from the TPC-DS tool's own tpcds.sql.

usage: make_schema.py <tools/tpcds.sql> <out_dir>
Types follow the specification (decimal stays decimal). Sort keys: the primary key, except the big
fact tables, which use the same keys as the Altinity ClickHouse schema (item first).
"""
import re, sys

src, out = sys.argv[1:3]
text = open(src).read()
tables = []
for m in re.finditer(r"create table (\w+)\s*\((.*?)\n\);", text, re.S):
    name, body = m.group(1), m.group(2)
    if name == 'dbgen_version': continue
    cols, pk = [], None
    for line in body.strip().split('\n'):
        line = line.strip().rstrip(',')
        if not line: continue
        if line.startswith('primary key'):
            pk = [c.strip() for c in re.search(r"\((.*)\)", line).group(1).split(',')]
            continue
        parts = line.split()
        if parts[0] == 'c_last_review_date': parts[0:2] = ['c_last_review_date_sk', 'integer']   # the queries and dsdgen use the key
        cols.append((parts[0], parts[1], 'not null' in line))
    tables.append((name, cols, pk))

FACT_KEY = {'store_sales': ['ss_item_sk', 'ss_ticket_number'], 'store_returns': ['sr_item_sk', 'sr_ticket_number'],
            'catalog_sales': ['cs_item_sk', 'cs_order_number'], 'catalog_returns': ['cr_item_sk', 'cr_order_number'],
            'web_sales': ['ws_item_sk', 'ws_order_number'], 'web_returns': ['wr_item_sk', 'wr_order_number'],
            'inventory': ['inv_date_sk', 'inv_item_sk', 'inv_warehouse_sk']}
HASH = {'store_sales': 'ss_item_sk', 'store_returns': 'sr_item_sk', 'catalog_sales': 'cs_item_sk',
        'catalog_returns': 'cr_item_sk', 'web_sales': 'ws_item_sk', 'web_returns': 'wr_item_sk', 'inventory': 'inv_item_sk'}
BUCKETS = {'customer': 8, 'customer_address': 8, 'customer_demographics': 8, 'item': 8, 'date_dim': 1}

def ch_type(t):
    t = t.lower()
    if t == 'integer': return 'Int32'
    if t.startswith('decimal'): return 'Decimal' + t[len('decimal'):].replace(',', ', ')
    if t == 'date': return 'Date'
    return 'String'                                    # char(n), varchar(n), time

def sr_type(t):
    t = t.lower()
    if t == 'integer': return 'INT'
    if t.startswith('decimal'): return 'DECIMAL' + t[len('decimal'):]
    if t == 'date': return 'DATE'
    if t.startswith('time'): return 'VARCHAR(16)'
    n = re.search(r"\((\d+)\)", t).group(1)
    return f'VARCHAR({n})'

ch = ['CREATE DATABASE IF NOT EXISTS tpcds;', 'USE tpcds;', '']
sr = ['CREATE DATABASE IF NOT EXISTS tpcds;', 'USE tpcds;', '']
for name, cols, pk in tables:
    key = FACT_KEY.get(name, pk)
    ch.append(f'CREATE TABLE {name}\n(')
    ch.append(',\n'.join(f"    {c:<26}{ch_type(t) if nn else 'Nullable(' + ch_type(t) + ')'}" for c, t, nn in cols))
    ch.append(f") ENGINE = MergeTree\nORDER BY ({', '.join(key)});\n")
    # StarRocks wants the key columns first and in key order; the load maps columns by name
    ordered = [c for k in key for c in cols if c[0] == k] + [c for c in cols if c[0] not in key]
    sr.append(f'CREATE TABLE {name}\n(')
    sr.append(',\n'.join(f"    {c:<26}{sr_type(t)}{' NOT NULL' if nn else ' NULL'}" for c, t, nn in ordered))
    if name in HASH:
        dist, b, colo = HASH[name], 32, ', "colocate_with" = "tpcds_item"'
    else:
        dist, b, colo = key[0], BUCKETS.get(name, 1), ''
    sr.append(f") DUPLICATE KEY ({', '.join(key)})\nDISTRIBUTED BY HASH({dist}) BUCKETS {b}\n"
              f'PROPERTIES ("replication_num" = "1"{colo});\n')
open(f'{out}/schema-clickhouse.sql', 'w').write('\n'.join(ch))
open(f'{out}/schema-starrocks.sql', 'w').write('\n'.join(sr))
# column lists for the StarRocks loader: file order; an empty string in a nullable text column is a NULL in dsdgen
# files, but Stream Load keeps it as '', so those columns are read as tmp_<col> and stored as nullif(tmp_<col>, '')
with open(f'{out}/columns.txt', 'w') as f:
    for name, cols, _ in tables:
        fc, ex = [], []
        for c, t, nn in cols:
            if not nn and sr_type(t).startswith('VARCHAR'): fc.append('tmp_' + c); ex.append(f"{c}=nullif(tmp_{c},'')")
            else: fc.append(c)
        f.write(f"{name} {','.join(fc)} {';'.join(ex) or '-'}\n")
print(len(tables), 'tables')
