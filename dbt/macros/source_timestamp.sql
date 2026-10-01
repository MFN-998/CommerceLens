{% macro commercelens_nullable_timestamp(column) -%}
    {# Accept the fixed source second-format only, within the Phase 2 nanosecond
       timestamp domain. PostgreSQL calendar validation supplements the grammar;
       do not normalize 24h, leap seconds, special dates, fractions or timezones.
       Guard the text operand before casting, including inline source constants.
       Rejected nonempty input becomes typed NULL and fails source-domain tests. #}
    cast(case
        when {{ column }} ~ '^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01]) ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$'
            and pg_input_is_valid({{ column }}, 'timestamp without time zone')
            and {{ column }} collate "C" between '1677-09-21 00:12:44' and '2262-04-11 23:47:16'
        then {{ column }}
    end as timestamp without time zone)
{%- endmacro %}
