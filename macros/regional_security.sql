-- dbt Macro: Regional Security Implementation
-- Amazon Q Developer automated conversion from MSSQL security patterns

{% macro validate_region_access(user_region) %}
  {% set valid_regions = ['NORTH', 'SOUTH', 'EAST', 'WEST'] %}
  
  {% if user_region not in valid_regions %}
    {{ exceptions.raise_compiler_error("Invalid region access: " ~ user_region ~ ". Valid regions: " ~ valid_regions | join(', ')) }}
  {% endif %}
{% endmacro %}

{% macro apply_regional_filter(table_alias='', region_column='region') %}
  {% if var('user_region', none) is not none %}
    {{ validate_region_access(var('user_region')) }}
    {% if table_alias %}
      AND {{ table_alias }}.{{ region_column }} = '{{ var('user_region') }}'
    {% else %}
      AND {{ region_column }} = '{{ var('user_region') }}'
    {% endif %}
  {% endif %}
{% endmacro %}

{% macro generate_redshift_rls_policy(table_name, region_column='region') %}
  -- Generate Redshift Row Level Security policy
  {% set policy_name = table_name ~ '_regional_policy' %}
  
  CREATE RLS POLICY {{ policy_name }}
  ON {{ table_name }}
  FOR ALL
  TO PUBLIC
  USING ({{ region_column }} = current_setting('app.user_region'));
  
  ALTER TABLE {{ table_name }} ENABLE ROW LEVEL SECURITY;
{% endmacro %}