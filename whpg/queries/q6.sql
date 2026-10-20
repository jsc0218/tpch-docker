-- TPC-H Q6 with the standard validation parameters (DATE=1994-01-01, DISCOUNT=0.06, QUANTITY=24).
-- Expected result at SF1: 123141078.2283
SELECT sum(l_extendedprice * l_discount) AS revenue
FROM lineitem
WHERE l_shipdate >= DATE '1994-01-01'
  AND l_shipdate <  DATE '1994-01-01' + INTERVAL '1 year'
  AND l_discount BETWEEN 0.06 - 0.01 AND 0.06 + 0.01
  AND l_quantity < 24;
