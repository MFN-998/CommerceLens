{# Owner policy forbids automatic deletion, including dbt's normal backup swap. #}
{% materialization view, adapter='postgres' %}
    {% set existing = load_cached_relation(this) %}
    {% set target = this.incorporate(type='view') %}
    {% if existing is not none and existing.type != 'view' %}
        {{ exceptions.raise_compiler_error('Preserved view cannot replace a non-view relation') }}
    {% endif %}
    {% if pre_hooks or post_hooks or config.get('grants') or config.get('sql_header') %}
        {{ exceptions.raise_compiler_error('Hooks, grant overrides and SQL headers require a separate reviewed change') }}
    {% endif %}
    {# PostgreSQL preserves ownership, grants and dependents; incompatible columns fail.
       The adapter macro also validates an enforced model contract when configured. #}
    {% call statement('main') %}
        {{ get_replace_view_sql(target, sql) }}
    {% endcall %}
    {% do persist_docs(target, model) %}
    {{ adapter.commit() }}
    {{ return({'relations': [target]}) }}
{% endmaterialization %}
