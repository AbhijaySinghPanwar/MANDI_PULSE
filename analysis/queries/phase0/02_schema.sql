-- Column names and types as read through the `prices` view (prices cast to DOUBLE).
-- Raw note: 2001.parquet stores Min_Price/Modal_Price as INT64; 2002-2026 store DOUBLE.
-- arrival_date_raw is the original VARCHAR 'YYYY-MM-DD'; arrival_date is the parsed DATE.
describe select * from prices;
