# TPC-H on WarehousePG (Docker)

Steps to run TPC-H against WarehousePG 7 in Docker on the same EC2 host as the PostgreSQL and
ClickHouse runs (see `../postgres/README.md` and `../clickhouse/README.md`). Status: every step
below was run on SF1 with 16 segments and no mirror (Ubuntu, x86_64, 32 vCPUs, 61 GB RAM).

Assumes Docker is installed and the SF1 files are already in `/data/tpch` (see
`../postgres/README.md`, steps 1 to 3). Run the commands from the repository root.

## 1. Stop the other engines

Run one engine at a time so they do not compete for CPU and cache.

```bash
docker stop pg18 ch
```

## 2. Start WarehousePG

The image is `amd64` only and is a single-host demo cluster, not a production deployment. It is in
the EnterpriseDB GitHub organisation and an anonymous pull is denied: log in with a GitHub token
that has `read:packages` (authorise it for the organisation's SSO if asked).

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
docker pull ghcr.io/enterprisedb/whpg-rocky9-runtime:latest
```

To keep the token off the EC2 host, pull on another amd64 machine and copy the image over:
`docker save <image> | gzip -1 | ssh <ec2-host> 'gunzip | docker load'`.

```bash
sudo mkdir -p /data/whpg && sudo chown ubuntu:ubuntu /data/whpg

docker run -d --name whpg --hostname cdw \
  --stop-timeout 60 \
  --sysctl net.ipv4.ping_group_range="0 2147483647" \
  --shm-size=1g --ulimit nofile=65536:65536 \
  -v /data/whpg:/data \
  -v /data/tpch:/data/tpch:ro \
  -e WHPG_ROLE=coordinator \
  -e WHPG_SEGMENTS_PER_HOST=16 \
  -e WHPG_MIRRORS=off \
  -p 5432:5432 \
  ghcr.io/enterprisedb/whpg-rocky9-runtime:latest

docker logs -f whpg      # wait for "[whpg-bootstrap] bootstrap complete" (about a minute), Ctrl-C
```

- `WHPG_ROLE=coordinator` is required. Without it the container starts as a segment and creates
  no database.
- `WHPG_SEGMENTS_PER_HOST` is the number of primary segments; 16 was used on a 32 vCPU host.
  `WHPG_MIRRORS=off` leaves out the mirror: with one segment it cut the SF1 load from 67 s to 30 s.
- `--hostname cdw`, the `ping_group_range` sysctl, `--shm-size` and `--ulimit` are the settings
  the image's own validation uses. `--stop-timeout 60` is needed because a clean stop takes about
  12 s and Docker's default grace period is 10 s.
- `/data/whpg` holds the database files. Mounting `/data/tpch` under it also leaves an empty
  root-owned `tpch` directory in `/data/whpg`.
- The role is `gpadmin` and there is no password. Do not expose port 5432 beyond the host.

```bash
docker exec whpg su - gpadmin -c "psql -d postgres -c 'select content, role, status from gp_segment_configuration order by 1, 2'"
```

Expect the coordinator (`-1`) and 16 primaries, all `u`, and no `m` rows.

## 3. Create tables

```bash
docker exec -i whpg su - gpadmin -c "psql -d postgres -v ON_ERROR_STOP=1 -f -" < whpg/schema.sql
```

`nation` and `region` are replicated; the other six tables are hash-distributed. `orders` and
`lineitem` share the order key so that their join needs no data movement.

## 4. Load

Server-side `COPY` runs as one stream on the coordinator, which then distributes the rows.

```bash
docker exec -i whpg su - gpadmin -c "psql -d postgres -v ON_ERROR_STOP=1 -f -" < whpg/load.sql
docker exec whpg su - gpadmin -c "psql -d postgres -c 'SELECT count(*) FROM lineitem'"   # SF1: 6001215
```

All eight tables took about 18 s. That single stream is the bottleneck at larger scale factors;
loading through `gpfdist` external tables would spread it and has not been tried here.

## 5. Run Q6

```bash
docker exec -i whpg su - gpadmin -c "psql -d postgres -c '\timing on' -f -" < whpg/queries/q6.sql
```

Expect `123141078.2283`. Median over 5 runs:

```bash
for i in 1 2 3 4 5; do
  docker exec -i whpg su - gpadmin -c "psql -d postgres -c '\timing on' -f -" < whpg/queries/q6.sql | grep Time
done
```

## Restart

`docker stop whpg` then `docker start whpg` keeps the data: the bootstrap detects the existing
cluster and starts it (a stop took about 12 s). Wait for `bootstrap complete` in `docker logs`
again. After a restart `lineitem` still had 6001215 rows and Q6 gave the same result.

## Observed so far (SF1, Q6, single runs, not a benchmark)

| Engine | Load (all tables) | Q6 (warm) |
|---|---|---|
| PostgreSQL 18.6 (16 parallel workers) | 38.7 s | 108 ms |
| WarehousePG 7, 16 segments, no mirror | 18.0 s | 74 ms |
| ClickHouse 26.8 | 4.2 s | about 15 ms |

With one segment and a mirror, the same load took 67 s and Q6 629 ms; with one segment and no
mirror, 30 s and 633 ms. WarehousePG memory is untuned (`shared_buffers` and `statement_mem` are
125 MB). Take medians of several runs, and time the engines the same way, before comparing.

## Removing things

```bash
docker rm -f whpg
docker rmi ghcr.io/enterprisedb/whpg-rocky9-runtime:latest
sudo rm -rf /data/whpg      # deletes the database files
```

## Notes

- `latest` is the newest plain `main` build of the image, which can be weeks old. The server
  reports `7.0.0-beta.0 build dev` with no commit, so pin the image digest and record it with any
  results.
- No indexes and no tuning; record the distribution keys and any settings with results.
- Results are TPC-H-derived, not comparable to official TPC Benchmark Results.
