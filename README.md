# tpch-docker

Docker image that generates TPC-H data with
[tpchgen-cli](https://github.com/datafusion-contrib/tpcgen-rs), a Rust generator whose output is
byte-for-byte identical to the reference `dbgen` (per the upstream test suite).

## Use

```bash
docker pull ghcr.io/jsc0218/tpchgen:latest
docker run --rm -v /data/tpch:/out ghcr.io/jsc0218/tpchgen:latest -s <scale_factor> --output-dir /out
```

Examples:

```bash
# SF100 as pipe-delimited .tbl files
docker run --rm -v /data/tpch:/out ghcr.io/jsc0218/tpchgen:latest -s 100 --output-dir /out

# SF100 as Parquet
docker run --rm -v /data/tpch:/out ghcr.io/jsc0218/tpchgen:latest parquet -s 100 --output-dir /out

# one table, split into 20 parts, generate part 3 only (for spreading across machines)
docker run --rm -v /data/tpch:/out ghcr.io/jsc0218/tpchgen:latest \
  --tables lineitem -s 1000 --parts 20 --part 3 --output-dir /out
```

All options are those of `tpchgen-cli`; run the image with `--help` to list them.

## Benchmark steps

Run these from the repository root.

- [postgres/](postgres/README.md): TPC-H on PostgreSQL 18 in Docker
- [clickhouse/](clickhouse/README.md): TPC-H on ClickHouse 26.8 (LTS) in Docker
- [whpg/](whpg/README.md): TPC-H on WarehousePG 7 in Docker (single host, no mirror)
- [monetdb/](monetdb/README.md): TPC-H on MonetDB (Dec2025-SP3) in Docker

Each folder has the same layout: `README.md` (steps), `schema.sql`, `queries/q6.sql` and
`queries/q12.sql`; all but ClickHouse (which streams the files through its client) also have
`load.sql`. Q6 is a scan with an aggregate and Q12 a join of `orders` and `lineitem`. The
queries are the standard text with the validation parameters, adapted only for each engine's
SQL dialect.

For a larger scale factor, generate it into its own directory (for example `-s 10` into
`/data/tpch10`) and use a separate data directory per engine; the folder READMEs say how.

## Results (SF1 and SF10, Q6 and Q12, not a benchmark)

One EC2 host (Ubuntu, x86_64, 32 vCPUs = 16 cores with hyperthreading, 61 GB RAM), one engine
running at a time, median of 5 warm runs in one session. Every engine returns the same answers:
Q6 is `123141078.2283` at SF1 and `1230113636.0101` at SF10, and Q12 gives the same rows.

| Engine | Load SF1 | Load SF10 | Q6 SF1 | Q6 SF10 | Q12 SF1 | Q12 SF10 |
|---|---|---|---|---|---|---|
| MonetDB 11.55.7 (Dec2025-SP3) | 15.7 s | 122 s | 3.8 ms | 17.1 ms | 9.5 ms | 43.6 ms |
| ClickHouse 26.8 | 4.6 s | 13.7 s | 16 ms | 75 ms | 27 ms | 122 ms |
| WarehousePG 7 (16 segments, no mirror) | 18.0 s | 227 s | 77 ms | 495 ms | 117 ms | 696 ms |
| PostgreSQL 18.6 | 40.7 s | 305 s | 115 ms | 831 ms | 225 ms | 2174 ms |

Database size (not the data directory, which also holds WAL and logs):

| | SF1 | SF10 |
|---|---|---|
| Raw `.tbl` files | 1.10 GB | 11.23 GB |
| ClickHouse (compressed, active parts) | 0.46 GB | 4.65 GB |
| MonetDB (`sys.storage`) | 0.89 GB | 9.11 GB |
| PostgreSQL | 1.45 GB | 14.39 GB |
| WarehousePG (all segments) | 1.80 GB | 14.62 GB |

Settings: PostgreSQL uses the flags in `postgres/README.md` (16 GB `shared_buffers`, parallel
workers, JIT off). WarehousePG is untuned apart from 16 segments and no mirror. ClickHouse and
MonetDB run on server defaults. The tables have no keys or secondary indexes (ClickHouse's
`ORDER BY` sort key is the TPC-H primary key). Loads are not like for like: ClickHouse streams
through its client, the others use a server-side `COPY`.

## Build locally

```bash
docker build -t tpchgen .
```

Override the version with `--build-arg TPCHGEN_VERSION=<version>`.

## Notes

- This image generates data only. It does not generate the 22 queries.
- Results from this data are TPC-H-derived, not audited TPC-H results, and are not comparable to
  official TPC Benchmark Results.
- TPC-H is a trademark of the Transaction Processing Performance Council. The upstream project
  embeds TPC data files (e.g. `dists.dss`); check the TPC EULA and your own legal guidance before
  redistributing or publishing results.
