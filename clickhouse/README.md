# TPC-H on ClickHouse (Docker)

Steps to run TPC-H against ClickHouse 26.8 (LTS) in Docker on the same EC2 host as the
PostgreSQL run (see `../postgres/README.md`). Status: Docker start, `lineitem` create/load and Q6
were run on SF1; the other seven tables and load commands are written but not yet run.

Assumes Docker is installed and the SF1 files are already in `/data/tpch` (see
`../postgres/README.md`, steps 1 to 3). Run the commands from the repository root.

## 1. Stop PostgreSQL

Run one engine at a time so they do not compete for CPU and cache.

```bash
docker stop pg18
```

## 2. Start ClickHouse

```bash
sudo mkdir -p /data/ch && sudo chown ubuntu:ubuntu /data/ch
docker pull clickhouse/clickhouse-server:26.8.30.8

docker run -d --name ch \
  --network host \
  --ulimit nofile=262144:262144 \
  -v /data/ch:/var/lib/clickhouse \
  clickhouse/clickhouse-server:26.8.30.8

docker exec -it ch clickhouse-client -q "SELECT version()"    # expect 26.8.30.8
```

26.3 and 26.8 are the LTS lines (`-lts` release tags on GitHub); 26.7 and 26.9 are regular
releases. Pin the full version.

## 3. Create tables

```bash
docker exec -i ch clickhouse-client --multiquery < clickhouse/schema.sql
```

## 4. Load

The client streams each file; ClickHouse does not need the files mounted.

```bash
for t in nation region part supplier partsupp customer orders lineitem; do
  docker exec -i ch clickhouse-client \
    --format_csv_delimiter='|' \
    -q "INSERT INTO $t FORMAT CSV" < /data/tpch/$t.tbl
done

docker exec -it ch clickhouse-client -q "SELECT count() FROM lineitem"   # SF1: 6001215
```

## 5. Run Q6

```bash
docker exec -i ch clickhouse-client --time < clickhouse/queries/q6.sql
```

Expect `123141078.2283`, then the elapsed time in seconds (0.017 = 17 ms).

Median over 5 runs:

```bash
for i in 1 2 3 4 5; do docker exec -i ch clickhouse-client --time < clickhouse/queries/q6.sql; done
```

## Pitfall: decimal arithmetic in query text

ClickHouse evaluates `0.06 + 0.01` as Float64 (`0.06999999999999999`). Compared against a
`Decimal(15,2)` column, rows equal to 0.07 are dropped. The standard Q6 text
(`BETWEEN 0.06 - 0.01 AND 0.06 + 0.01`) therefore returns `75207768.1855`, not
`123141078.2283`. Write such bounds as literals. Other queries with decimal arithmetic may need
the same treatment; check every query's result against the official SF1 answers before
trusting its timing.

## Observed so far (SF1, Q6, single runs, not a benchmark)

| Engine | Time |
|---|---|
| PostgreSQL 18.6 | 121.7 ms |
| ClickHouse 26.8 | 17 ms |

Take medians of several runs, and time both engines the same way, before comparing.

## Removing things

```bash
docker rm -f ch
docker rmi clickhouse/clickhouse-server:26.8.30.8
sudo rm -rf /data/ch      # deletes the database files
```

## Notes

- `ORDER BY` in `MergeTree` is the primary index; record the keys with any results.
- Results are TPC-H-derived, not comparable to official TPC Benchmark Results.
