-- TPC-H Q6 with the standard validation parameters (DATE=1994-01-01, DISCOUNT=0.06, QUANTITY=24).
-- Expected result at SF1: 123141078.2283
-- The discount bounds are written as literals on purpose: in ClickHouse `0.06 + 0.01` is a
-- Float64 equal to 0.06999999999999999, which drops every row with l_discount = 0.07 and
-- gives 75207768.1855 instead.
SELECT sum(l_extendedprice * l_discount) AS revenue
FROM lineitem
WHERE l_shipdate >= toDate('1994-01-01')
  AND l_shipdate <  toDate('1994-01-01') + INTERVAL 1 YEAR
  AND l_discount BETWEEN 0.05 AND 0.07
  AND l_quantity < 24;
