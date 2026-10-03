{{ config(severity='error', store_failures=false) }}
-- NULL-safe comparisons verify every standard attribute against the date itself.
select count(*) as invalid_date_dimension_rows
from {{ ref('dim_date') }}
where calendar_date is null
    or calendar_year is distinct from cast(extract(year from calendar_date) as integer)
    or calendar_quarter is distinct from cast(extract(quarter from calendar_date) as integer)
    or calendar_month is distinct from cast(extract(month from calendar_date) as integer)
    or day_of_month is distinct from cast(extract(day from calendar_date) as integer)
    or iso_year is distinct from cast(extract(isoyear from calendar_date) as integer)
    or iso_week is distinct from cast(extract(week from calendar_date) as integer)
    or iso_day_of_week is distinct from cast(extract(isodow from calendar_date) as integer)
    or is_weekend is distinct from (extract(isodow from calendar_date) in (6, 7))
having count(*) > 0
