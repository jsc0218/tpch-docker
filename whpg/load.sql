-- Server-side COPY on the coordinator: the files must be visible inside the container (mounted at
-- /data/tpch). The coordinator parses one stream and distributes rows to the segments.
COPY nation   FROM '/data/tpch/nation.tbl'   WITH (FORMAT csv, DELIMITER '|');
COPY region   FROM '/data/tpch/region.tbl'   WITH (FORMAT csv, DELIMITER '|');
COPY part     FROM '/data/tpch/part.tbl'     WITH (FORMAT csv, DELIMITER '|');
COPY supplier FROM '/data/tpch/supplier.tbl' WITH (FORMAT csv, DELIMITER '|');
COPY partsupp FROM '/data/tpch/partsupp.tbl' WITH (FORMAT csv, DELIMITER '|');
COPY customer FROM '/data/tpch/customer.tbl' WITH (FORMAT csv, DELIMITER '|');
COPY orders   FROM '/data/tpch/orders.tbl'   WITH (FORMAT csv, DELIMITER '|');
COPY lineitem FROM '/data/tpch/lineitem.tbl' WITH (FORMAT csv, DELIMITER '|');

ANALYZE;
