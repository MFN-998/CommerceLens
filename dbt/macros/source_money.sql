{% macro commercelens_nullable_money(column) -%}
    {# Match M3 parse_money's ASCII nonnegative decimal grammar before conversion.
       Guard raw text before unconstrained numeric CAST, including inline constants.
       Check the exact numeric(18,2) maximum before the constrained cast could round
       or overflow. Rejected/missing input becomes typed NULL; domains block it. #}
    {% set safe_numeric -%}
        cast(case
            when {{ column }} ~ '^[0-9]+([.][0-9]{1,2})?$'
                and pg_input_is_valid({{ column }}, 'numeric')
            then {{ column }}
        end as numeric)
    {%- endset %}
    cast(case
        when {{ safe_numeric }} <= 9999999999999999.99
        then {{ safe_numeric }}
    end as numeric(18,2))
{%- endmacro %}
