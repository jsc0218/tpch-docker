# TPC-H on StarRocks (Docker)

Steps to run TPC-H against StarRocks 4.1.8 in Docker on the same EC2 host as the other engines
(see `../postgres/README.md`). Status: all steps below were run on SF10 (all eight tables, all 22
queries). The other engines are in `../postgres/`, `../clickhouse/`, `../whpg/` and `../monetdb/`;
Parquet runs are in `../clickhouse-parquet/` and `../pgaa/`. The 22-query comparison of StarRocks
and ClickHouse is in `../tpch22/README.md`.

Assumes Docker is installed and the SF10 files are already in `/data/tpch` (see
`../postgres/README.md`, steps 1 to 3). Run the commands from the repository root.

## 1. Stop the other engines

Run one engine at a time so they do not compete for CPU and cache.

```bash
docker stop pg18 ch whpg mdb chpq chs3 pgaa 2>/dev/null || true      # whichever of the other engines are running
```

## 2. Start StarRocks

The `allin1` image runs a frontend (FE) and a backend (BE) in one container, which is a single-node
demo cluster, not a production deployment. The image is `amd64` only here.

```bash
docker pull starrocks/allin1-ubuntu:4.1.8

docker run -d --name starrocks --network host \
  -v /data/tpch:/data/tpch:ro \
  starrocks/allin1-ubuntu:4.1.8

until docker exec starrocks mysql -h127.0.0.1 -P9030 -uroot -N -e "show backends" 2>/dev/null | grep -q true; do sleep 3; done
docker exec starrocks mysql -h127.0.0.1 -P9030 -uroot -e "select current_version()"
```

The client is the `mysql` that ships in the image (SQL port 9030, user `root`, no password); the HTTP
port 8030 is used for loading. Pin the image tag: `latest` moves with every release.

## 3. Create tables

```bash
docker exec -i starrocks mysql -h127.0.0.1 -P9030 -uroot < starrocks/schema.sql
```

The tables are `DUPLICATE KEY` tables sorted on the TPC-H primary key, like the ClickHouse
`MergeTree ORDER BY`, with one replica. They have no other indexes. `orders` and `lineitem` share
the order key and a colocation group, and `part` and `partsupp` share the part key, so those joins
need no data movement. StarRocks wants the key columns first, so `l_linenumber` comes second in
`lineitem`. The bucket counts (32 for `orders` and `lineitem`, 16 for `part` and `partsupp`, 8 for
`customer`, 1 for the rest) were chosen for 32 vCPUs and were not tuned further.

## 4. Load

Stream Load sends each file through the FE HTTP port. The `.tbl` rows end with `|`, so `load.sh`
adds a dummy column to the column list. It needs `curl` and `python3` on the host.

```bash
bash starrocks/load.sh
docker exec starrocks mysql -h127.0.0.1 -P9030 -uroot -N -e "select count(*) from tpch.lineitem"   # SF10: 59986052
```

## 5. Collect statistics

StarRocks plans with a cost-based optimizer. Collect full statistics once, after the load (the other
engines in this repo have no such step):

```bash
for t in region nation supplier customer part partsupp orders lineitem; do
  docker exec starrocks mysql -h127.0.0.1 -P9030 -uroot -e "ANALYZE FULL TABLE tpch.$t"
done
docker exec starrocks mysql -h127.0.0.1 -P9030 -uroot -e "show stats meta"     # every table: FULL, healthy 100%
```

## 6. Run Q6 and Q12

```bash
docker exec -i starrocks mysql -h127.0.0.1 -P9030 -uroot tpch < starrocks/queries/q6.sql
docker exec -i starrocks mysql -h127.0.0.1 -P9030 -uroot tpch < starrocks/queries/q12.sql
```

Expect `1230113636.0101` for Q6, and for Q12 MAIL 62071 93045 and SHIP 62426 93261. The `mysql`
client does not report a usable elapsed time, so the timings in this repo come from the harness in
`../tpch22/` (steps there), which times every query the same way for every engine. All 22 queries
are in `../tpch22/queries/`; only `queries/q22.sql` in this folder differs, because StarRocks does
not accept `substring(c_phone FROM 1 FOR 2)` and needs `substring(c_phone, 1, 2)`.

## Observed so far (not a benchmark)

| | SF10 |
|---|---|
| Load (all tables, `load.sh`) | 56.3 s |
| `ANALYZE FULL` (all tables) | 37.1 s |
| Q6, median of 5 | 34.9 ms |
| Q12, median of 5 | 51.5 ms |
| Database size | 3.17 GB |

Server defaults apart from the schema above, one session, warm cache, timed by the `../tpch22/`
harness (a Python client, so the numbers are not directly comparable to the `clickhouse-client` and
`mclient` timings in the other READMEs; the comparison with ClickHouse on the same harness is in
[`../tpch22/README.md`](../tpch22/README.md)). The load is not like for like with the others (a
single Stream Load per table, through HTTP). I waited about five minutes after the load before
`ANALYZE` and timing, so that background compaction had settled.

## Removing things

```bash
docker rm -f starrocks      # the data lives inside the container, so this deletes it
docker rmi starrocks/allin1-ubuntu:4.1.8
```

## Notes

- Database size is the sum of `data_size` over `information_schema.be_tablets` (3.17 GB; `SHOW DATA`
  reports 2.95 GiB for the same data). The data and metadata live in `/data/deploy/starrocks` inside
  the container, on the host's root volume, like the other engines' `/data` directories.
- The BE reported a 50 GB memory limit on the 61 GB host, `pipeline_dop` was left at its automatic
  setting (0), and the session `query_timeout` default (300 s) was raised to 3600 s; no query came
  near 300 s.
- The image's FE and BE advertise `127.0.0.1` (`priority_networks`), which is why Stream Load works
  from the host with `curl --location-trusted` and `--network host`.
- Results are TPC-H-derived, not comparable to official TPC Benchmark Results.
