# TPC-H on ClickHouse over Parquet (Docker)

Steps to query TPC-H data stored as Parquet files directly from ClickHouse 26.8 (LTS) in Docker,
with no load step: views over the `file()` table function read the files that `tpchgen`
generates. Status: all steps below were run on SF10 (all eight tables, Q6 and Q12). The native
MergeTree run is in `../clickhouse/`.

Assumes Docker is installed. Run the commands from the repository root.

## 1. Stop the other engines

Run one engine at a time so they do not compete for CPU and cache.

```bash
docker stop pg18 ch whpg mdb chs3 pgaa starrocks 2>/dev/null || true      # whichever of the other engines are running
```

## 2. Generate Parquet

```bash
sudo mkdir -p /data/tpch-parquet && sudo chown ubuntu:ubuntu /data/tpch-parquet
docker run --rm -v /data/tpch-parquet:/out ghcr.io/jsc0218/tpchgen:latest parquet -s 10 --output-dir /out
ls -lh /data/tpch-parquet      # one <table>.parquet per table; 3.9 GB in total (`ls -lh` shows 3.7G, in GiB)
```

## 3. Start ClickHouse with the files mounted

`file()` only reads under `user_files`, so mount the Parquet directory there.

```bash
sudo mkdir -p /data/chpq && sudo chown ubuntu:ubuntu /data/chpq
docker pull clickhouse/clickhouse-server:26.8.30.8

docker run -d --name chpq \
  --network host \
  --ulimit nofile=262144:262144 \
  -v /data/chpq:/var/lib/clickhouse \
  -v /data/tpch-parquet:/var/lib/clickhouse/user_files/tpch \
  clickhouse/clickhouse-server:26.8.30.8

docker exec -it chpq clickhouse-client -q "SELECT version()"    # expect 26.8.30.8
```

Do not mount the directory read-only (`:ro`): the image entrypoint runs `chown` on
`user_files` and the container exits with "Read-only file system".

## 4. Create the views

```bash
docker exec -i chpq clickhouse-client --multiquery < clickhouse-parquet/schema.sql

docker exec -it chpq clickhouse-client -q "SELECT count() FROM lineitem"   # SF10: 59986052
```

## 5. Run Q6

```bash
docker exec -i chpq clickhouse-client --time < clickhouse-parquet/queries/q6.sql
```

Expect `1230113636.0101`, then the elapsed time in seconds (0.126 = 126 ms).

Median of runs 2 to 6 (run 1 is cold):

```bash
for i in 1 2 3 4 5 6; do docker exec -i chpq clickhouse-client --time < clickhouse-parquet/queries/q6.sql; done
```

## 6. Run Q12

```bash
docker exec -i chpq clickhouse-client --time < clickhouse-parquet/queries/q12.sql
```

At SF10 the result is MAIL 62071 93045 and SHIP 62426 93261. The query files are the same as in
`../clickhouse/queries/`, so the decimal pitfall in `../clickhouse/README.md` applies: write
decimal bounds as literals and check every result before trusting its timing.

## Parquet in S3 (object storage)

The same Parquet files can be queried from S3. The bucket must be in the same region as the EC2
host (here `us-east-1`), and the instance role needs read access.

```bash
aws s3 sync /data/tpch-parquet s3://<bucket>/tpch-parquet/sf10/      # 3.65 GiB (3.9 GB), 8 objects, about 7 s

docker stop chpq 2>/dev/null || true      # both servers use the default ports on the host network
sudo mkdir -p /data/chs3 && sudo chown ubuntu:ubuntu /data/chs3
docker run -d --name chs3 --network host --ulimit nofile=262144:262144 \
  -v /data/chs3:/var/lib/clickhouse clickhouse/clickhouse-server:26.8.30.8
```

ClickHouse 26.8 refuses to use the server's own credentials (instance profile) from `s3()` in
user queries. To use the instance role instead of static keys, enable the setting for the default
profile:

```bash
docker exec chs3 bash -c 'cat > /etc/clickhouse-server/users.d/s3_creds.xml <<EOF
<clickhouse><profiles><default><s3_allow_server_credentials_in_user_queries>1</s3_allow_server_credentials_in_user_queries></default></profiles></clickhouse>
EOF'

sed 's/<bucket>/YOUR-BUCKET/' clickhouse-parquet/schema_s3.sql \
  | docker exec -i chs3 clickhouse-client --multiquery
```

Run Q6 and Q12 as in steps 5 and 6, with `chs3` in place of `chpq`. With no filesystem cache
configured (the default), every run reads from S3 again, which is the object-storage cost.

Optional, cache on: define a 10 GiB ClickHouse filesystem cache, restart, and add two client
settings. The first run fills the cache.

```bash
docker exec chs3 bash -c 'cat > /etc/clickhouse-server/config.d/fscache.xml <<EOF
<clickhouse><filesystem_caches><s3cache><path>/var/lib/clickhouse/s3cache/</path><max_size>10Gi</max_size></s3cache></filesystem_caches></clickhouse>
EOF'
docker restart chs3
docker exec -i chs3 clickhouse-client --enable_filesystem_cache=1 --filesystem_cache_name=s3cache \
  --time < clickhouse-parquet/queries/q6.sql
```

### Tuning: `remote_read_min_bytes_for_seek`

By default (4 MiB), when the Parquet reader needs two column chunks that are less than 4 MiB apart,
ClickHouse reads straight through the gap instead of issuing a second request. Q6 needs 4 of
`lineitem`'s 16 columns, so it reads 1.93 GiB from S3 where the query needs about 0.6 GiB (a local
read of the same query touches 559 MiB). Q12 reads 2.64 GiB against 556 MiB. Lowering the setting
to 1 MiB removes most of that extra read; lowering it further only adds requests. Add it to the
client command (or put it in the default profile):

```bash
docker exec -i chs3 clickhouse-client --remote_read_min_bytes_for_seek=1048576 --time < clickhouse-parquet/queries/q6.sql
```

Q6, no cache, median of 3 (S3 data read, requests): 4 MiB 4.80 s (1.93 GiB, 131); 1 MiB 1.36 s
(613 MiB, 526); 256 KiB 2.11 s (613 MiB, 917); 8 KiB 17.1 s (561 MiB, 8963); 0 31.1 s (559 MiB,
17817). The cache segment size (`max_file_segment_size`) only changes the filling run. With the
1 MiB seek setting, 4 MiB segments read the same from S3 as the default 32 MiB (Q6 1646 MiB, Q12
494 MiB), while 1 MiB segments read 874 MiB for Q6 and 708 MiB for Q12, with about twice as many
requests for Q6 (1134 against 528). `boundary_alignment` (4 MiB by default) must not exceed the
segment size, so 1 MiB segments also need `boundary_alignment` set to 1 MiB, or the server does
not start. With the default seek setting, 1 MiB segments made the Q6 filling run slower (10.4 s
against 5.4 s) and the second run still read 299 MiB (1.4 s against 0.27 s). Later runs with the
1 MiB seek setting were the same for all three sizes. With the cache on, the filling run reads up
to 1.6 GiB from S3 (2.2 GiB with the default seek setting); only later runs read the lower
amount. Check every answer after changing the setting (they matched here).

## Observed so far (not a benchmark)

<img alt="Bar charts of ClickHouse on SF10 Parquet, lower is better. Q6 time: local Parquet warm 126 ms, S3 no cache with the default 4 MiB seek 3109 ms, S3 no cache with 1 MiB seek 1150 ms, S3 cache on with the default 4 MiB seek 253 ms, S3 cache on with 1 MiB seek 166 ms. Q12 time: 371, 5363, 2853, 550 and 439 ms. The table below holds the same values." src="sf10.svg">

Drawn from [`results.csv`](results.csv) by `python3 clickhouse-parquet/make_chart.py` (standard library
only). The chart has one linear axis per panel, so bar lengths compare within a panel but not
between panels.

| | Q6 | Q12 |
|---|---|---|
| Local Parquet (warm page cache), median of 5 | 126 ms | 371 ms |
| S3, no cache, default seek setting, median of 5 | 3.11 s | 5.36 s |
| S3, no cache, `remote_read_min_bytes_for_seek` 1 MiB, median of 5 | 1.15 s | 2.85 s |
| S3, filesystem cache on, default seek setting, median of 5 (after a filling run) | 253 ms | 550 ms |
| S3, filesystem cache on, 1 MiB seek setting, median of 5 (after a filling run) | 166 ms | 439 ms |

Parquet files on disk: 3.9 GB (3.65 GiB); the same 8 files in S3.

Runs 2 to 6 (s), first or filling run in brackets: local Q6 0.126 0.125 0.153 0.131 0.125
(0.137), Q12 0.371 0.371 0.392 0.367 0.371 (0.372); S3 no cache, default seek, Q6 3.53 2.89 3.11
2.88 3.18 (5.03), Q12 5.44 5.84 5.36 5.17 5.30 (6.83); S3 no cache, 1 MiB seek, Q6 1.35 1.12
1.55 1.15 1.01 (1.09), Q12 2.85 2.65 3.02 2.82 3.06 (2.82); S3 with cache, default seek, Q6
0.267 0.253 0.268 0.237 0.238 (filling run 7.86), Q12 0.616 0.550 0.532 0.614 0.516 (filling
run 9.46); S3 with cache and the 1 MiB seek setting Q6 0.162 0.166 0.177 0.164 0.166 (filling
run 2.84), Q12 0.439 0.439 0.438 0.431 0.545 (filling run 4.54). Server defaults except
where a row says otherwise, one session, same-region S3. The local runs are warm, so they
show decode and compute speed with almost no I/O and are not an object-storage figure. The native
MergeTree figures in the root README (Q6 94 ms, Q12 145 ms) come from a separate run on the same host,
so the comparison is indicative only.

## Removing things

```bash
docker rm -f chpq
docker rmi clickhouse/clickhouse-server:26.8.30.8
sudo rm -rf /data/chpq /data/tpch-parquet      # deletes the database files and the Parquet data

# S3 run
docker rm -f chs3 && sudo rm -rf /data/chs3
aws s3 rm s3://<bucket>/tpch-parquet/sf10/ --recursive
```

## Notes

- The views have no keys or indexes; ClickHouse reads and decompresses the Parquet files on every
  query.
- Results are TPC-H-derived, not comparable to official TPC Benchmark Results.
