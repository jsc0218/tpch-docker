-- TPC-H views over Parquet files in S3. Replace <bucket> (e.g. with sed) before running.
-- Credentials come from the instance role; ClickHouse 26.8 needs
-- s3_allow_server_credentials_in_user_queries=1 for that (see README).
CREATE VIEW nation   AS SELECT * FROM s3('https://<bucket>.s3.us-east-1.amazonaws.com/tpch-parquet/sf10/nation.parquet',   Parquet);
CREATE VIEW region   AS SELECT * FROM s3('https://<bucket>.s3.us-east-1.amazonaws.com/tpch-parquet/sf10/region.parquet',   Parquet);
CREATE VIEW part     AS SELECT * FROM s3('https://<bucket>.s3.us-east-1.amazonaws.com/tpch-parquet/sf10/part.parquet',     Parquet);
CREATE VIEW supplier AS SELECT * FROM s3('https://<bucket>.s3.us-east-1.amazonaws.com/tpch-parquet/sf10/supplier.parquet', Parquet);
CREATE VIEW partsupp AS SELECT * FROM s3('https://<bucket>.s3.us-east-1.amazonaws.com/tpch-parquet/sf10/partsupp.parquet', Parquet);
CREATE VIEW customer AS SELECT * FROM s3('https://<bucket>.s3.us-east-1.amazonaws.com/tpch-parquet/sf10/customer.parquet', Parquet);
CREATE VIEW orders   AS SELECT * FROM s3('https://<bucket>.s3.us-east-1.amazonaws.com/tpch-parquet/sf10/orders.parquet',   Parquet);
CREATE VIEW lineitem AS SELECT * FROM s3('https://<bucket>.s3.us-east-1.amazonaws.com/tpch-parquet/sf10/lineitem.parquet', Parquet);
