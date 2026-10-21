# TPC-H on PostgreSQL (Docker)

Steps to run TPC-H against PostgreSQL 18 in Docker on an EC2 host (Ubuntu, x86_64, 32 vCPUs,
61 GB RAM). Status: the load, Q6 and Q12 were run on SF1 and SF10 with scripted equivalents of
the steps below (see "Observed so far"). The other engines are in `../clickhouse/`, `../whpg/`
and `../monetdb/`.

## 1. Install Docker

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
 | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu     # then log out and back in
```

If Docker's repo has no directory for the Ubuntu release (404 on `apt-get update`), use the
previous LTS codename (`noble`) or Ubuntu's `docker.io` package.

## 2. Data directories

```bash
sudo mkdir -p /data/tpch /data/pg18
sudo chown -R ubuntu:ubuntu /data
```

## 3. Generate TPC-H data

```bash
docker run --rm -v /data/tpch:/out ghcr.io/jsc0218/tpchgen:latest -s 1 --output-dir /out
ls -lh /data/tpch
```

`-s 1` is scale factor 1 (about 1 GB). The files are pipe-delimited `.tbl` with a trailing `|`.

## 4. Start PostgreSQL 18

Run one engine at a time so they do not compete for CPU and cache.

```bash
docker stop ch whpg mdb 2>/dev/null || true      # whichever of the other engines are running
```

```bash
docker run -d --name pg18 \
  --network host \
  --shm-size=16g \
  -e POSTGRES_PASSWORD=bench \
  -v /data/pg18:/var/lib/postgresql \
  -v /data/tpch:/data/tpch:ro \
  postgres:18.6 \
  -c shared_buffers=16GB \
  -c effective_cache_size=40GB \
  -c work_mem=256MB \
  -c maintenance_work_mem=2GB \
  -c max_parallel_workers=32 \
  -c max_parallel_workers_per_gather=16 \
  -c max_worker_processes=32 \
  -c jit=off
```

Pin the image tag. PostgreSQL 19 is only at a release candidate (`19rc1`) as of 2026-10-19; use
a separate data directory per major version. The 18 image keeps its data in
`/var/lib/postgresql/18/docker`, so mounting `/var/lib/postgresql` works.

`--shm-size=16g` is needed: Docker gives a container only 64 MB of `/dev/shm` by default, and
Q12's parallel hash join then fails with `could not resize shared memory segment ... No space
left on device`. Q6 does not need it, so the problem only shows up on the join.

To run a larger scale factor, generate it into its own directory (`-s 10` into `/data/tpch10`)
and mount that directory at `/data/tpch` of a container with its own data directory, so that
`load.sql` stays unchanged.

## 5. Create tables and load

```bash
docker exec -i pg18 psql -U postgres < postgres/schema.sql
docker exec -i pg18 psql -U postgres < postgres/load.sql
docker exec -it pg18 psql -U postgres -c "SELECT count(*) FROM lineitem"   # SF1: 6001215
```

## 6. Run Q6

```bash
docker exec -i pg18 psql -U postgres -c '\timing on' -f - < postgres/queries/q6.sql
```

At SF1 with the standard parameters the result should be `123141078.2283` (SF10:
`1230113636.0101`). Run each query several times and keep the median; the first run is cold.

## 7. Run Q12

```bash
docker exec -i pg18 psql -U postgres -c '\timing on' -f - < postgres/queries/q12.sql
```

Q12 is a join of `orders` and `lineitem`. At SF1 the result is MAIL 6202 9324 and SHIP 6200 9262
(SF10: MAIL 62071 93045, SHIP 62426 93261).

## Observed so far (not a benchmark)

| | SF1 | SF10 |
|---|---|---|
| Load (all tables, `load.sql`) | 40.7 s | 305 s |
| Q6, median of 5 | 115 ms | 831 ms |
| Q12, median of 5 | 225 ms | 2174 ms |
| Database size | 1.45 GB | 14.39 GB |

With the settings above, one session, warm cache. The comparison with the other engines is in the
[root README](../README.md#results-sf1-and-sf10-q6-and-q12-not-a-benchmark).

## Removing things

```bash
docker rm -f pg18
docker rmi postgres:18.6
sudo rm -rf /data/pg18      # deletes the database files
```

## Notes

- Tables have no keys or indexes; add them deliberately and record them with the results. On SF10,
  primary keys on `orders` and `lineitem` plus single-column indexes on `l_shipdate` and
  `l_receiptdate` (all within the TPC-H rules) made Q6 and Q12 slower, not faster: the planner
  chose bitmap scans on the date indexes, which read scattered pages. They were dropped again.
- Database size is `pg_database_size(current_database())`. The data directory is larger because
  of recycled WAL (about 1 GiB).
- Results are TPC-H-derived, not comparable to official TPC Benchmark Results.
- The matching steps for the other engines are in `../clickhouse/README.md`, `../whpg/README.md`
  and `../monetdb/README.md`.
