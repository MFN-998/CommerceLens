{% macro commercelens_nullable_bigint(column) -%}
    {# Match decimal syntax and PostgreSQL representability before conversion.
       POSIX/input whitespace is not every Python Unicode strip character.
       Casting guarded text prevents planning-time casts of invalid constants.
       Rejected nonempty input becomes NULL and fails the source-domain test. #}
    {% set safe_numeric -%}
        cast(case
            when {{ column }} ~ '^[[:space:]]*[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?[[:space:]]*$'
                and pg_input_is_valid({{ column }}, 'numeric')
            then {{ column }}
        end as numeric)
    {%- endset %}
    case
        when {{ safe_numeric }} = trunc({{ safe_numeric }})
            and {{ safe_numeric }} between -9223372036854775808 and 9223372036854775807
        then cast({{ safe_numeric }} as bigint)
    end
{%- endmacro %}

{% macro commercelens_nullable_double(column) -%}
    {# Decimal grammar excludes PostgreSQL NaN/Infinity extensions. Native
       representability rejects overflow/underflow rather than inventing zero. #}
    cast(case
        when {{ column }} ~ '^[[:space:]]*[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?[[:space:]]*$'
            and pg_input_is_valid({{ column }}, 'double precision')
        then {{ column }}
    end as double precision)
{%- endmacro %}
