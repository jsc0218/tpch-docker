# TPC-H on EDB Postgres Analytics Accelerator (pgaa, Docker)

Steps to run Q6 and Q12 on SF10 through PostgreSQL 18 with the pgaa extension. pgaa sends the
query to Seafowl (an Apache DataFusion engine, run as a Postgres background worker) over Arrow
Flight, and Seafowl reads the Parquet files in place from S3. Nothing is loaded into Postgres.
Same EC2 host and same SF10 Parquet files as `../clickhouse-parquet/`.

## 1. Get the packages

pgaa needs two Debian 12 packages: `postgresql-18-pgaa` (includes the Seafowl binary) and
`edb-pg18-pgfs` (its dependency). They come from EDB's package repository, which needs an EDB
repository token (not part of this repo). Put them in `pgaa/debs/`.

## 2. Data

Use the SF10 Parquet from `../clickhouse-parquet/README.md`, with one folder per table, because
pgaa takes a folder of Parquet files, not a single file path:

```bash
for t in region nation supplier customer part partsupp orders lineitem; do
  aws s3 cp s3://<bucket>/tpch-parquet/sf10/$t.parquet \
            s3://<bucket>/tpch-parquet-dirs/sf10/$t/$t.parquet
done
```

Edit the bucket name in `schema.sql`. The instance needs read access to the bucket (an instance
role works; no keys go into the SQL).

## 3. Build and start

```bash
docker build -t pg18-pgaa pgaa/
docker run -d --name pgaa --network host --shm-size=16g \
  -e POSTGRES_PASSWORD=bench -v /data/pgaa:/var/lib/postgresql \
  pg18-pgaa \
  -c shared_preload_libraries=pgaa \
  -c pgaa.autostart_seafowl=on
```

`pgaa.autostart_seafowl` is off by default; without it every query fails with `Connection
refused` on port 47470. Other Seafowl settings (`pgaa.autostart_seafowl_*`: memory limit,
object-store cache, metadata cache) were left at their defaults, except the object-store cache in the
cache rows of the results below.

## 4. Create the tables

```bash
docker exec -i pgaa psql -U postgres < pgaa/schema.sql
```

## 5. Run Q6 and Q12

```bash
docker exec -i pgaa psql -U postgres -c '\timing on' -f - < pgaa/queries/q6.sql
docker exec -i pgaa psql -U postgres -c '\timing on' -f - < pgaa/queries/q12.sql
```

`EXPLAIN` shows a `SeafowlDirectScan` node when pgaa has pushed the query to Seafowl. Expected
answers at SF10: Q6 `1230113636.0101`; Q12 MAIL 62071 93045 and SHIP 62426 93261 (both matched).

## Observed so far (not a benchmark)

S3 in the same region, one session, with the pgaa extension 1.12.0 (from a CI snapshot of the
`postgresql-18-pgaa` package, `1.11.0~53`) and `pgfs` 3.2.1. Each configuration is a fresh container, then the query six
times on one `psql` connection; the table gives run 1 (cold) and the median of runs 2 to 6. The only
setting changed is Seafowl's object-store cache (`pgaa.autostart_seafowl_enable_object_store_cache`,
`pgaa.autostart_seafowl_object_store_cache_capacity_mb`):

| Seafowl object-store cache | Q6 first run | Q6 | Q12 first run | Q12 |
|---|---|---|---|---|
| off | 1369 ms | 873 ms | 1587 ms | 1446 ms |
| on, 1 GiB (default) | 2352 ms | 874 ms | 2056 ms | 1805 ms |
| on, 10 GiB | 1401 ms | 230 ms | 1560 ms | 369 ms |

For comparison, ClickHouse on the same files with `remote_read_min_bytes_for_seek` set to 1 MiB (its
best setting here; the default 4 MiB gives Q6 3109 / 253 ms and Q12 5363 / 550 ms without / with the
10 GiB cache), median of runs 2 to 6, one `clickhouse-client` call per run:

| ClickHouse | Q6 | Q12 |
|---|---|---|
| no cache, 1 MiB seek | 1150 ms | 2853 ms |
| 10 GiB cache, 1 MiB seek | 166 ms | 439 ms |

<img alt="Bar charts of pgaa and ClickHouse on SF10 Parquet in S3, lower is better. Q6 time: pgaa cache off 873 ms, cache 1 GiB (default) 874 ms, cache 10 GiB 230 ms; ClickHouse no cache 1150 ms, 10 GiB cache 166 ms. Q12 time: pgaa 1446, 1805 and 369 ms; ClickHouse 2853 and 439 ms. The tables hold the same values." src="sf10.svg">

Drawn from [`results.csv`](results.csv) by `python3 pgaa/make_chart.py` (standard library only). The
chart has one linear axis per panel, so bar lengths compare within a panel but not between panels.

The default 1 GiB cache is smaller than `lineitem` (2.4 GiB), so it keeps evicting and is no better
than no cache (Q12 is about 1.25 times as slow); 10 GiB holds all eight tables. The ClickHouse setup is in
[`../clickhouse-parquet/`](../clickhouse-parquet/README.md).

The numbers are for a connection that is already open. With the 10 GiB cache, a fresh connection
per query gave Q6 434 ms and Q12 693 ms, against 237 and 362 ms on an open connection (median of
six runs each): about 0.2 s more for Q6 and 0.33 s more for Q12. The cause was not investigated.

## Why the default cache does not help

Seafowl's cache counters (`localhost:9090/metrics`, `seafowl_object_store_cache_*`) show the
working set each query needs cached: about 1.1 GiB for Q6 and about 1.9 GiB for Q12. The default
capacity is 1 GiB, so Q12 scans the same data in the same order every run and each run evicts what
the next one needs: no cache hits, 1.9 GiB fetched, written and evicted on every run. Q6 is only
slightly over the capacity, so it gets partial hits (about 0.5 to 0.9 GiB per run) and still
fetches 0.24 to 0.64 GiB each time, which is why it ends up about level with no cache. (The hit
counter `seafowl_object_store_cache_hit_read_bytes_total` did not move even when everything was
cached, so hits here are the working set minus the bytes fetched.) The cache also fetches about
3.4 times the bytes the query asks for (1915 MiB against 554 MiB for Q12). At 10 GiB everything fits and later runs are all hits.
The cache has only a capacity, a TTL and a minimum fetch size to set, so size it to the working set.

## Removing things

```bash
docker rm -f pgaa
docker rmi pg18-pgaa postgres:18.6-bookworm
sudo rm -rf /data/pgaa      # deletes the database files
aws s3 rm s3://<bucket>/tpch-parquet-dirs/ --recursive      # the per-table copies from step 2
```

## Notes

- A local `file://` storage location created tables but every query failed with `No files found
  at file:///...` from Seafowl, in several path layouts. S3 worked.
- The base `postgres` image has no CA certificates, which made S3 fail with a generic
  `error sending request`; the Dockerfile installs them.
- Results are TPC-H-derived, not comparable to official TPC Benchmark Results.
