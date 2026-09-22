{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set allowed_schemas = ['staging', 'core', 'marts'] -%}
    {%- if target.schema not in allowed_schemas -%}
        {{ exceptions.raise_compiler_error('Warehouse target schema is not approved') }}
    {%- endif -%}
    {%- set schema_name = target.schema if custom_schema_name is none
        else custom_schema_name | trim -%}
    {%- if schema_name not in allowed_schemas -%}
        {{ exceptions.raise_compiler_error('Warehouse model schema is not approved') }}
    {%- endif -%}
    {{ schema_name }}
{%- endmacro %}
