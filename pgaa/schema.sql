-- pgaa reads the Parquet files in place from S3; nothing is loaded into Postgres.
-- Each table path is a prefix (folder) holding that table's Parquet file(s).
CREATE EXTENSION IF NOT EXISTS pgaa CASCADE;   -- also creates pgfs

-- Credentials come from the EC2 instance role (no keys in the options).
SELECT pgfs.create_storage_location('tpch', 's3://<bucket>', '{"region": "us-east-1"}');
SELECT pgaa.test_storage_location('tpch', false);   -- NULL means readable

-- Empty column list: pgaa discovers the schema from the Parquet headers on first query.
CREATE TABLE region   () USING PGAA WITH (pgaa.format='parquet', pgaa.storage_location='tpch', pgaa.path='tpch-parquet-dirs/sf10/region');
CREATE TABLE nation   () USING PGAA WITH (pgaa.format='parquet', pgaa.storage_location='tpch', pgaa.path='tpch-parquet-dirs/sf10/nation');
CREATE TABLE supplier () USING PGAA WITH (pgaa.format='parquet', pgaa.storage_location='tpch', pgaa.path='tpch-parquet-dirs/sf10/supplier');
CREATE TABLE customer () USING PGAA WITH (pgaa.format='parquet', pgaa.storage_location='tpch', pgaa.path='tpch-parquet-dirs/sf10/customer');
CREATE TABLE part     () USING PGAA WITH (pgaa.format='parquet', pgaa.storage_location='tpch', pgaa.path='tpch-parquet-dirs/sf10/part');
CREATE TABLE partsupp () USING PGAA WITH (pgaa.format='parquet', pgaa.storage_location='tpch', pgaa.path='tpch-parquet-dirs/sf10/partsupp');
CREATE TABLE orders   () USING PGAA WITH (pgaa.format='parquet', pgaa.storage_location='tpch', pgaa.path='tpch-parquet-dirs/sf10/orders');
CREATE TABLE lineitem () USING PGAA WITH (pgaa.format='parquet', pgaa.storage_location='tpch', pgaa.path='tpch-parquet-dirs/sf10/lineitem');
