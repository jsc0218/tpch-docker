# TPC-H on MonetDB (Docker)

Steps to run TPC-H against MonetDB (release Dec2025-SP3, 11.55.7) in Docker on the same EC2 host
as the PostgreSQL, ClickHouse and WarehousePG runs (see `../postgres/README.md`). Status: the
load, Q6 and Q12 were run on SF1 and SF10 with scripted equivalents of the steps below. The other
engines are in `../postgres/`, `../clickhouse/` and `../whpg/`.

Assumes Docker is installed and the SF1 files are already in `/data/tpch` (see
`../postgres/README.md`, steps 1 to 3). Run the commands from the repository root.

## 1. Stop the other engines

Run one engine at a time so they do not compete for CPU and cache.

```bash
docker stop pg18 ch whpg 2>/dev/null || true      # whichever of the other engines are running
```

## 2. Start MonetDB

The image is `amd64` only. It runs as uid 5000 (`monetdb`), so the host directory that holds the
database farm must belong to that uid, or the first start fails with `unable to create file in
directory '/var/monetdb5/dbfarm': Permission denied`.

```bash
docker pull monetdb/monetdb:Dec2025-SP3
sudo mkdir -p /data/mdb && sudo chown 5000:5000 /data/mdb

docker run -d --name mdb \
  -e MDB_DB_ADMIN_PASS=monetdb \
  -v /data/mdb:/var/monetdb5/dbfarm \
  -v /data/tpch:/data/tpch:ro \
  monetdb/monetdb:Dec2025-SP3
```

The first start creates the database `monetdb` with the admin user `monetdb` and the password
above. Run the client inside the container, with the credentials in a file:

```bash
docker exec mdb sh -c 'printf "user=monetdb\npassword=monetdb\n" > /tmp/.monetdb'
mc() { docker exec -i -e DOTMONETDBFILE=/tmp/.monetdb mdb mclient -d monetdb "$@"; }

until mc -s 'SELECT 1' >/dev/null 2>&1; do sleep 2; done
mc -f csv -s "SELECT value FROM sys.env() WHERE name = 'monet_version'"     # expect 11.55.7
```

`mc` is a shell function; define it again in each new shell. Pin the image tag: `latest` moves
with every service pack.

## 3. Create tables

```bash
mc < monetdb/schema.sql
```

The schema is the PostgreSQL one without the `dummy` column (MonetDB's record delimiter in
`load.sql` absorbs the trailing `|`), with `DECIMAL` instead of `NUMERIC`.

## 4. Load

```bash
mc < monetdb/load.sql
mc -f csv -s "SELECT count(*) FROM lineitem"      # SF1: 6001215
```

To keep SF10 next to SF1, also mount `-v /data/tpch10:/data/tpch10:ro`, then use a schema:

```bash
{ echo 'CREATE SCHEMA sf10; SET SCHEMA sf10;'; cat monetdb/schema.sql; } | mc
{ echo 'SET SCHEMA sf10;'; sed 's#/data/tpch/#/data/tpch10/#' monetdb/load.sql; } | mc
```

and put `SET SCHEMA sf10;` before the queries below.

## 5. Run Q6

```bash
mc -t performance < monetdb/queries/q6.sql
```

The `clk:` line is the elapsed time in ms; the client prints it on stderr. Expect
`123141078.2283` (SF10: `1230113636.0101`). Median over 5 runs:

```bash
for i in 1 2 3 4 5; do mc -t performance < monetdb/queries/q6.sql 2>&1 | grep '^clk'; done
```

## 6. Run Q12

```bash
mc -t performance < monetdb/queries/q12.sql
```

Q12 is a join of `orders` and `lineitem`. At SF1 the result is MAIL 6202 9324 and SHIP 6200 9262
(SF10: MAIL 62071 93045, SHIP 62426 93261). The query uses MonetDB's `INTERVAL '1' YEAR` syntax.

## Observed so far (not a benchmark)

| | SF1 | SF10 |
|---|---|---|
| Load (all tables, `load.sql`) | 15.7 s | 122 s |
| Q6, median of 5 | 3.8 ms | 17.1 ms |
| Q12, median of 5 | 9.5 ms | 43.6 ms |
| Database size | 0.89 GB | 9.11 GB |

Server defaults (32 worker threads, about 54 GB of memory chosen by the server), one session,
warm cache. The comparison with the other engines is in the
[root README](../README.md#results-sf1-and-sf10-q6-and-q12-not-a-benchmark).

## Removing things

```bash
docker rm -f mdb
docker rmi monetdb/monetdb:Dec2025-SP3
sudo rm -rf /data/mdb      # deletes the database files
```

## Notes

- Database size is the sum of `columnsize + heapsize + hashes + imprints + orderidx` in
  `sys.storage` for the schema. The farm directory was 10.0 GB with SF1 and SF10 together.
- No keys or indexes; MonetDB builds its own accelerators (hashes, imprints) on demand and they
  count in `sys.storage`.
- `docker stop` ended with exit code 137 (killed after the timeout) with both `-t 60` and
  `-t 120`, so the container does not exit on SIGTERM; use `-t 10` to avoid the wait. The loaded
  data was committed first, and the farm started again after such a kill and ran a query; the
  data was not checked beyond that.
- Results are TPC-H-derived, not comparable to official TPC Benchmark Results.
