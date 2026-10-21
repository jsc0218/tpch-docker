# TPC-H on ClickHouse (Docker)

Steps to run TPC-H against ClickHouse 26.8 (LTS) in Docker on the same EC2 host as the
PostgreSQL run (see `../postgres/README.md`). Status: all steps below were run on SF1 and SF10
(all eight tables, Q6 and Q12). The other engines are in `../whpg/` and `../monetdb/`.

Assumes Docker is installed and the SF1 files are already in `/data/tpch` (see
`../postgres/README.md`, steps 1 to 3). Run the commands from the repository root.

## 1. Stop the other engines

Run one engine at a time so they do not compete for CPU and cache.

```bash
docker stop pg18 whpg mdb 2>/dev/null || true      # whichever of the other engines are running
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

To run SF10 next to SF1, create a database and load into it:

```bash
docker exec ch clickhouse-client -q "CREATE DATABASE tpch10"
docker exec -i ch clickhouse-client -d tpch10 --multiquery < clickhouse/schema.sql
for t in nation region part supplier partsupp customer orders lineitem; do
  docker exec -i ch clickhouse-client -d tpch10 \
    --format_csv_delimiter='|' \
    -q "INSERT INTO $t FORMAT CSV" < /data/tpch10/$t.tbl
done
```

and add `-d tpch10` to the queries below.

## 5. Run Q6

```bash
docker exec -i ch clickhouse-client --time < clickhouse/queries/q6.sql
```

Expect `123141078.2283` (SF10: `1230113636.0101`), then the elapsed time in seconds
(0.017 = 17 ms).

Median over 5 runs:

```bash
for i in 1 2 3 4 5; do docker exec -i ch clickhouse-client --time < clickhouse/queries/q6.sql; done
```

## 6. Run Q12

```bash
docker exec -i ch clickhouse-client --time < clickhouse/queries/q12.sql
```

Q12 is a join of `orders` and `lineitem`; the query uses an explicit `JOIN ... ON`. At SF1 the
result is MAIL 6202 9324 and SHIP 6200 9262 (SF10: MAIL 62071 93045, SHIP 62426 93261).

## Pitfall: decimal arithmetic in query text

ClickHouse evaluates `0.06 + 0.01` as Float64 (`0.06999999999999999`). Compared against a
`Decimal(15,2)` column, rows equal to 0.07 are dropped. The standard Q6 text
(`BETWEEN 0.06 - 0.01 AND 0.06 + 0.01`) therefore returns `75207768.1855`, not
`123141078.2283`. Write such bounds as literals. Other queries with decimal arithmetic may need
the same treatment; check every query's result against the official SF1 answers before
trusting its timing.

## Observed so far (not a benchmark)

| | SF1 | SF10 |
|---|---|---|
| Load (all tables, client streaming) | 4.6 s | 13.7 s |
| Q6, median of 5 | 16 ms | 75 ms |
| Q12, median of 5 | 27 ms | 122 ms |
| Table size on disk (compressed, active parts) | 0.46 GB | 4.65 GB |

Server defaults, default compression, one session, warm cache. The comparison with the other
engines is in the [root README](../README.md#results-sf1-and-sf10-q6-and-q12-not-a-benchmark).

## Removing things

```bash
docker rm -f ch
docker rmi clickhouse/clickhouse-server:26.8.30.8
sudo rm -rf /data/ch      # deletes the database files
```

## Notes

- `ORDER BY` in `MergeTree` is the primary index; record the keys with any results. `lineitem`
  is ordered by `(l_orderkey, l_linenumber)`, which does not help Q6, because Q6 filters on
  `l_shipdate`.
- Table size is the sum of `bytes_on_disk` over active parts in `system.parts`. Right after a
  load, background merges leave inactive parts on disk until the server has run for a few
  minutes (1.88 GB extra on SF10 when measured too early), so `du` on the data directory
  overstates it.
- Results are TPC-H-derived, not comparable to official TPC Benchmark Results.
