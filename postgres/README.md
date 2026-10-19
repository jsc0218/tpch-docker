# TPC-H on PostgreSQL (Docker)

Steps to run TPC-H against PostgreSQL 18 in Docker on an EC2 host (Ubuntu, x86_64).
Status: written down, not yet run end to end. Update this file as steps are confirmed.

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

```bash
docker run -d --name pg18 \
  --network host \
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
a separate data directory per major version. The data mount path (`/var/lib/postgresql`) for
the 18 image is unverified; check with `docker inspect` if startup fails.

## 5. Create tables and load

```bash
docker exec -i pg18 psql -U postgres < postgres/schema.sql
docker exec -i pg18 psql -U postgres < postgres/load.sql
docker exec -it pg18 psql -U postgres -c "SELECT count(*) FROM lineitem"   # SF1: 6001215
```

## 6. Run a query (Q6)

```bash
docker exec -i pg18 psql -U postgres -c '\timing on' -f - < postgres/queries/q6.sql
```

At SF1 with the standard parameters the result should be `123141078.2283`. Run each query
several times and keep the median; the first run is cold.

## Removing things

```bash
docker rm -f pg18
docker rmi postgres:18.6
sudo rm -rf /data/pg18      # deletes the database files
```

## Notes

- Tables have no keys or indexes yet; add them deliberately and record them with the results.
- Results are TPC-H-derived, not comparable to official TPC Benchmark Results.
- The `clickhouse` branch will hold the matching ClickHouse steps.
