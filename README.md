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
