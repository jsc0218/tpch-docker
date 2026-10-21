-- Server-side COPY INTO: the files must be visible inside the container (mounted at /data/tpch).
-- The record delimiter '|\n' absorbs the trailing '|' on every row of the generated .tbl files.
COPY INTO nation   FROM '/data/tpch/nation.tbl'   USING DELIMITERS '|', '|\n';
COPY INTO region   FROM '/data/tpch/region.tbl'   USING DELIMITERS '|', '|\n';
COPY INTO part     FROM '/data/tpch/part.tbl'     USING DELIMITERS '|', '|\n';
COPY INTO supplier FROM '/data/tpch/supplier.tbl' USING DELIMITERS '|', '|\n';
COPY INTO partsupp FROM '/data/tpch/partsupp.tbl' USING DELIMITERS '|', '|\n';
COPY INTO customer FROM '/data/tpch/customer.tbl' USING DELIMITERS '|', '|\n';
COPY INTO orders   FROM '/data/tpch/orders.tbl'   USING DELIMITERS '|', '|\n';
COPY INTO lineitem FROM '/data/tpch/lineitem.tbl' USING DELIMITERS '|', '|\n';
