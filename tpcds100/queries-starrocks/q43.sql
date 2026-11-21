SELECT s_store_name,
       s_store_id,
       sum(CASE
               WHEN (d_day_name='Sunday') THEN ss_sales_price
               ELSE NULL
           END) sun_sales,
       sum(CASE
               WHEN (d_day_name='Monday') THEN ss_sales_price
               ELSE NULL
           END) mon_sales,
       sum(CASE
               WHEN (d_day_name='Tuesday') THEN ss_sales_price
               ELSE NULL
           END) tue_sales,
       sum(CASE
               WHEN (d_day_name='Wednesday') THEN ss_sales_price
               ELSE NULL
           END) wed_sales,
       sum(CASE
               WHEN (d_day_name='Thursday') THEN ss_sales_price
               ELSE NULL
           END) thu_sales,
       sum(CASE
               WHEN (d_day_name='Friday') THEN ss_sales_price
               ELSE NULL
           END) fri_sales,
       sum(CASE
               WHEN (d_day_name='Saturday') THEN ss_sales_price
               ELSE NULL
           END) sat_sales
FROM date_dim,
     store_sales,
     store
WHERE d_date_sk = ss_sold_date_sk
  AND s_store_sk = ss_store_sk
  AND s_gmt_offset = -5
  AND d_year = 2000
GROUP BY s_store_name,
         s_store_id
ORDER BY s_store_name NULLS LAST,
         s_store_id NULLS LAST,
         sun_sales NULLS LAST,
         mon_sales NULLS LAST,
         tue_sales NULLS LAST,
         wed_sales NULLS LAST,
         thu_sales NULLS LAST,
         fri_sales NULLS LAST,
         sat_sales NULLS LAST
LIMIT 100;
