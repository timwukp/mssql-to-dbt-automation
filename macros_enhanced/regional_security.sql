-- Regional Security Macros
-- Auto-generated utility macros for regional data access

{% macro validate_region_access(user_region) %}
    {% if user_region is not none %}
        -- Regional access validation
        {% if user_region not in ['US', 'EU', 'APAC'] %}
            {{ exceptions.raise_compiler_error("Invalid region: " + user_region) }}
        {% endif %}
    {% endif %}
{% endmacro %}

{% macro apply_regional_filter(table_alias, column_name) %}
    {% if var('user_region', none) is not none %}
        AND {{ table_alias }}.{{ column_name }} = '{{ var('user_region') }}'
    {% endif %}
{% endmacro %}

{% macro get_incremental_filter(timestamp_column='updated_at') %}
    {% if is_incremental() %}
        WHERE {{ timestamp_column }} > (SELECT MAX({{ timestamp_column }}) FROM {{ this }})
    {% endif %}
{% endmacro %}