-- Raw files on disk: one CSV and one Parquet per calendar year.
select file_name, format, size as size_bytes, round(size / 1024 / 1024, 1) as size_mb
from source_files
order by format, file_name;
