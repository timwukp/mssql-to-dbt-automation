#!/usr/bin/env python3
"""
MSSQL to DBT Multi-Platform Converter
Supports Glue, Athena, and Redshift targets
"""

import re
import os
import json
import yaml
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from enum import Enum

class TargetPlatform(Enum):
    GLUE = "glue"
    ATHENA = "athena"
    REDSHIFT = "redshift"

class ConversionPattern(Enum):
    FULL_LOAD = "full_load"
    UPSERT_MERGE = "upsert_merge"
    HISTORY_UPSERT = "history_upsert"
    MULTIPLE_DML_UPSERT = "multiple_dml_upsert"
    SNAPSHOT_APPEND = "snapshot_append"

class UpdatedMSSQLTodbtConverter:
    """MSSQL to DBT converter with multi-platform support"""
    
    def __init__(self, target_platform: TargetPlatform = TargetPlatform.REDSHIFT):
        self.target_platform = target_platform
        self.conversion_patterns = self._init_conversion_patterns()
        self.platform_configs = self._init_platform_configs()
        
    def _init_conversion_patterns(self) -> Dict[str, str]:
        """Initialize conversion patterns with proper regex flags"""
        return {
            # Remove MSSQL procedure syntax
            r'CREATE\s+PROCEDURE\s+[\w\[\]\.]+.*?AS\s*BEGIN': '',
            r'SET\s+NOCOUNT\s+ON;?': '',
            r'END\s*$': '',
            
            # Parameter conversion to dbt variables
            r'@(\w+)\s+(VARCHAR|INT|DATE|DECIMAL|DATETIME|FLOAT|BIGINT)\s*\([^)]*\)\s*=?\s*[^,\s]*': r"{{ var('\1') }}",
            r'@(\w+)\s+(VARCHAR|INT|DATE|DECIMAL|DATETIME|FLOAT|BIGINT)\s*=?\s*[^,\s]*': r"{{ var('\1') }}",
            r'@(\w+)': r"{{ var('\1') }}",
            
            # Function conversions
            r'GETDATE\(\)': 'CURRENT_TIMESTAMP',
            r'DATEDIFF\s*\(\s*day\s*,\s*([^,]+)\s*,\s*([^)]+)\s*\)': r"DATE_DIFF('day', \1, \2)",
            r'MONTH\s*\(\s*([^)]+)\s*\)': r"EXTRACT(MONTH FROM \1)",
            r'YEAR\s*\(\s*([^)]+)\s*\)': r"EXTRACT(YEAR FROM \1)",
            
            # Table references - fix escaping issues
            r'FROM\s+(\w+)(?!\s*\()': r"FROM {{ ref('\1') }}",
            r'JOIN\s+(\w+)(?!\s*\()': r"JOIN {{ ref('\1') }}",
            
            # Temp table to CTE conversion
            r'CREATE\s+TABLE\s+#(\w+)': r'-- CTE: \1',
            r'INSERT\s+INTO\s+#(\w+)': r'-- CTE: \1 AS (',
            r'DROP\s+TABLE\s+#(\w+);?': r'-- End CTE: \1',
            r'#(\w+)': r'\1',
            
            # Remove DECLARE statements
            r'DECLARE\s+.*?;': '',
            r'SELECT\s+@\w+\s*=\s*.*?FROM': 'SELECT',
        }
    
    def _init_platform_configs(self) -> Dict[TargetPlatform, Dict]:
        """Initialize platform-specific configurations"""
        return {
            TargetPlatform.GLUE: {
                'materialized': 'table',
                'file_format': 'delta',
                'partition_by': ['year', 'month'],
                'cluster_by': ['customer_id', 'product_id']
            },
            TargetPlatform.ATHENA: {
                'materialized': 'table',
                'file_format': 'parquet',
                'partition_by': ['year', 'month', 'region'],
                'external_location': 's3://data-lake/tables/'
            },
            TargetPlatform.REDSHIFT: {
                'materialized': 'table',
                'sort': ['created_at', 'updated_at'],
                'dist': 'even',
                'compression': 'lzo'
            }
        }
    
    def convert_procedure(self, mssql_content: str, model_name: str, 
                         pattern: ConversionPattern = ConversionPattern.FULL_LOAD) -> str:
        """Convert MSSQL procedure with pattern-specific logic"""
        
        # Clean and normalize input
        converted = self._clean_mssql_content(mssql_content)
        
        # Apply conversion patterns with proper flags
        for regex_pattern, replacement in self.conversion_patterns.items():
            converted = re.sub(regex_pattern, replacement, converted, 
                             flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
        
        # Apply pattern-specific transformations
        converted = self._apply_conversion_pattern(converted, pattern)
        
        # Generate platform-specific config
        config = self._generate_platform_config(model_name)
        
        # Generate Jinja templates
        jinja_templates = self._generate_jinja_templates(converted, pattern)
        
        # Wrap in dbt model structure
        dbt_model = f"""-- dbt Model: {model_name.title()}
-- Platform: {self.target_platform.value.upper()}
-- Pattern: {pattern.value}
-- Auto-generated DBT model

{config}

{jinja_templates}

{converted}"""
        
        return dbt_model
    
    def _clean_mssql_content(self, content: str) -> str:
        """Clean MSSQL content before conversion"""
        # Remove comments about role-based security
        content = re.sub(r'--.*?Role based security.*?\n', '', content, flags=re.IGNORECASE)
        # Remove temporary table definitions
        content = re.sub(r'--.*?temporary table definition.*?\n', '', content, flags=re.IGNORECASE)
        # Normalize whitespace
        content = re.sub(r'\s+', ' ', content)
        return content.strip()
    
    def _apply_conversion_pattern(self, content: str, pattern: ConversionPattern) -> str:
        """Apply specific conversion pattern logic"""
        
        if pattern == ConversionPattern.UPSERT_MERGE:
            return self._add_upsert_logic(content)
        elif pattern == ConversionPattern.HISTORY_UPSERT:
            return self._add_history_tracking(content)
        elif pattern == ConversionPattern.SNAPSHOT_APPEND:
            return self._add_snapshot_logic(content)
        elif pattern == ConversionPattern.MULTIPLE_DML_UPSERT:
            return self._handle_multiple_dml(content)
        
        return content
    
    def _add_upsert_logic(self, content: str) -> str:
        """Add UPSERT/MERGE logic for incremental models"""
        upsert_template = """
{% if is_incremental() %}
    -- Incremental logic
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
{% endif %}
"""
        return content + upsert_template
    
    def _add_history_tracking(self, content: str) -> str:
        """Add history tracking for SCD Type 2"""
        history_template = """
-- SCD Type 2 History Tracking
, ROW_NUMBER() OVER (PARTITION BY id ORDER BY updated_at DESC) as rn
, CASE WHEN ROW_NUMBER() OVER (PARTITION BY id ORDER BY updated_at DESC) = 1 
       THEN TRUE ELSE FALSE END as is_current
"""
        return content + history_template
    
    def _add_snapshot_logic(self, content: str) -> str:
        """Add snapshot logic for append-only tables"""
        snapshot_template = """
-- Snapshot logic
, CURRENT_TIMESTAMP as snapshot_timestamp
, '{{ run_started_at }}' as dbt_run_timestamp
"""
        return content + snapshot_template
    
    def _handle_multiple_dml(self, content: str) -> str:
        """Handle multiple DML operations"""
        # Convert multiple operations to CTEs
        return content
    
    def _generate_platform_config(self, model_name: str) -> str:
        """Generate platform-specific dbt configuration"""
        
        config = self.platform_configs[self.target_platform].copy()
        
        # Customize based on model type
        if 'analytics' in model_name:
            config['tags'] = ['analytics', 'customer']
        elif 'reporting' in model_name:
            config['tags'] = ['reporting', 'sales']
            config['materialized'] = 'view'
        elif 'inventory' in model_name:
            config['tags'] = ['inventory', 'operations']
        
        # Generate config block
        config_lines = []
        for key, value in config.items():
            if isinstance(value, list):
                config_lines.append(f"    {key}={value}")
            elif isinstance(value, str):
                config_lines.append(f"    {key}='{value}'")
            else:
                config_lines.append(f"    {key}={value}")
        
        return "{{ config(\n" + ",\n".join(config_lines) + "\n) }}"
    
    def _generate_jinja_templates(self, content: str, pattern: ConversionPattern) -> str:
        """Generate Jinja templates for variables and conditionals"""
        
        templates = []
        
        # Variable validation
        if "{{ var(" in content:
            templates.append("""
-- Variable validation
{% set required_vars = ['start_date', 'end_date'] %}
{% for var_name in required_vars %}
    {% if var(var_name, none) is none %}
        {{ exceptions.raise_compiler_error("Required variable '" + var_name + "' is not defined") }}
    {% endif %}
{% endfor %}""")
        
        # Regional filtering
        if "region" in content:
            templates.append("""
-- Regional filtering with NULL handling
{% macro apply_regional_filter(table_alias, column_name) %}
    {% if var('region', none) is not none %}
        AND {{ table_alias }}.{{ column_name }} = '{{ var('region') }}'
    {% endif %}
{% endmacro %}""")
        
        return "\n".join(templates)
    
    def generate_macro_file(self, model_name: str) -> str:
        """Generate DBT macro file"""
        
        macro_content = f"""-- Macro: {model_name}_utils
-- Auto-generated utility macros

{{%% macro validate_region_access(user_region) %%}}
    {{%% if user_region is not none %%}}
        -- Regional access validation
        {{%% if user_region not in ['US', 'EU', 'APAC'] %%}}
            {{{{{{ exceptions.raise_compiler_error("Invalid region: " + user_region) }}}}}}
        {{%% endif %%}}
    {{%% endif %%}}
{{%% endmacro %%}}

{{%% macro apply_regional_filter(table_alias, column_name) %%}}
    {{%% if var('user_region', none) is not none %%}}
        AND {{{{{{ table_alias }}}}}}.{{{{{{ column_name }}}}}} = '{{{{{{ var('user_region') }}}}}}'
    {{%% endif %%}}
{{%% endmacro %%}}

{{%% macro get_incremental_filter(timestamp_column='updated_at') %%}}
    {{%% if is_incremental() %%}}
        WHERE {{{{{{ timestamp_column }}}}}} > (SELECT MAX({{{{{{ timestamp_column }}}}}}) FROM {{{{{{ this }}}}}})
    {{%% endif %%}}
{{%% endmacro %%}}"""
        
        return macro_content
    
    def generate_schema_yml(self, models: List[str]) -> str:
        """Generate schema.yml with tests and documentation"""
        
        schema_config = {
            'version': 2,
            'models': []
        }
        
        for model in models:
            model_config = {
                'name': model,
                'description': f'Converted from MSSQL procedure sp_{model}',
                'columns': [
                    {
                        'name': 'id',
                        'description': 'Primary key',
                        'tests': ['unique', 'not_null']
                    },
                    {
                        'name': 'created_at',
                        'description': 'Record creation timestamp',
                        'tests': ['not_null']
                    },
                    {
                        'name': 'region',
                        'description': 'Geographic region',
                        'tests': [
                            'not_null',
                            {'accepted_values': {'values': ['US', 'EU', 'APAC']}}
                        ]
                    }
                ]
            }
            schema_config['models'].append(model_config)
        
        return yaml.dump(schema_config, default_flow_style=False)
    
    def generate_sources_yml(self, source_tables: List[str]) -> str:
        """Generate sources.yml configuration"""
        
        sources_config = {
            'version': 2,
            'sources': [
                {
                    'name': 'mssql_source',
                    'description': 'Source tables from MSSQL database',
                    'tables': []
                }
            ]
        }
        
        for table in source_tables:
            table_config = {
                'name': table,
                'description': f'Source table {table} from MSSQL',
                'columns': [
                    {'name': 'id', 'tests': ['unique', 'not_null']},
                    {'name': 'created_at', 'tests': ['not_null']}
                ]
            }
            sources_config['sources'][0]['tables'].append(table_config)
        
        return yaml.dump(sources_config, default_flow_style=False)
    
    def generate_dbt_project_yml(self, project_name: str) -> str:
        """Generate dbt_project.yml"""
        
        project_config = {
            'name': project_name,
            'version': '1.0.0',
            'config-version': 2,
            'profile': project_name,
            'model-paths': ['models'],
            'analysis-paths': ['analysis'],
            'test-paths': ['tests'],
            'seed-paths': ['data'],
            'macro-paths': ['macros'],
            'snapshot-paths': ['snapshots'],
            'target-path': 'target',
            'clean-targets': ['target', 'dbt_packages'],
            'models': {
                project_name: {
                    'materialized': 'table',
                    'analytics': {'materialized': 'table'},
                    'reporting': {'materialized': 'view'},
                    'staging': {'materialized': 'view'}
                }
            },
            'vars': {
                'start_date': '2023-01-01',
                'end_date': '2023-12-31',
                'region': None,
                'warehouse_id': 1,
                'low_stock_threshold': 10
            }
        }
        
        return yaml.dump(project_config, default_flow_style=False)
    
    def calculate_automation_percentage(self, original_content: str, converted_content: str) -> float:
        """Calculate realistic automation percentage"""
        
        # Count conversion patterns applied
        patterns_applied = 0
        for pattern in self.conversion_patterns.keys():
            if re.search(pattern, original_content, re.IGNORECASE):
                patterns_applied += 1
        
        # Count manual interventions needed
        manual_interventions = 0
        
        # Check for complex business logic
        if re.search(r'CASE\s+WHEN.*?THEN.*?ELSE.*?END', converted_content, re.IGNORECASE | re.DOTALL):
            manual_interventions += 1
        
        # Check for complex joins
        if len(re.findall(r'JOIN', converted_content, re.IGNORECASE)) > 2:
            manual_interventions += 1
        
        # Check for aggregations
        if re.search(r'GROUP\s+BY', converted_content, re.IGNORECASE):
            manual_interventions += 1
        
        # Calculate percentage
        total_complexity = patterns_applied + manual_interventions
        if total_complexity == 0:
            return 95.0
        
        automation_percentage = (patterns_applied / total_complexity) * 100
        return min(automation_percentage, 95.0)  # Cap at 95% automation

def main():
    """Main conversion function with multi-platform support"""
    
    # Initialize converter for each platform
    platforms = [TargetPlatform.GLUE, TargetPlatform.ATHENA, TargetPlatform.REDSHIFT]
    
    # Fixed paths - addressing customer feedback
    mssql_dir = Path("mssql_original")
    output_base = Path("dbt_models_enhanced")
    
    if not mssql_dir.exists():
        print(f"Error: MSSQL directory {mssql_dir} not found")
        return
    
    # Create output directories
    for platform in platforms:
        platform_dir = output_base / platform.value
        platform_dir.mkdir(parents=True, exist_ok=True)
    
    conversion_results = []
    source_tables = []
    
    # Process each MSSQL file
    for sql_file in mssql_dir.glob("*.sql"):
        print(f"Converting {sql_file.name}...")
        
        # Read MSSQL content - addressing customer feedback
        try:
            with open(sql_file, "r", encoding="utf-8") as f:
                mssql_content = f.read()
        except Exception as e:
            print(f"Error reading {sql_file}: {e}")
            continue
        
        model_name = sql_file.stem.replace('sp_', '')
        
        # Convert for each platform
        for platform in platforms:
            converter = UpdatedMSSQLTodbtConverter(platform)
            
            # Determine conversion pattern based on content
            pattern = ConversionPattern.FULL_LOAD
            if "MERGE" in mssql_content.upper():
                pattern = ConversionPattern.UPSERT_MERGE
            elif "INSERT" in mssql_content.upper() and "UPDATE" in mssql_content.upper():
                pattern = ConversionPattern.MULTIPLE_DML_UPSERT
            
            # Convert procedure
            converted = converter.convert_procedure(mssql_content, model_name, pattern)
            
            # Write output - addressing customer feedback
            output_file = output_base / platform.value / f"{model_name}.sql"
            try:
                with output_file.open("w", encoding="utf-8") as f:
                    f.write(converted)
                print(f"  ✓ Generated {platform.value}/{model_name}.sql")
            except Exception as e:
                print(f"Error writing {output_file}: {e}")
                continue
            
            # Generate macro file
            macro_content = converter.generate_macro_file(model_name)
            macro_file = output_base / platform.value / "macros" / f"{model_name}_utils.sql"
            macro_file.parent.mkdir(exist_ok=True)
            with macro_file.open("w", encoding="utf-8") as f:
                f.write(macro_content)
            
            # Calculate automation percentage
            automation_pct = converter.calculate_automation_percentage(mssql_content, converted)
            
            conversion_results.append({
                'procedure': sql_file.name,
                'platform': platform.value,
                'model': f"{model_name}.sql",
                'automation_percentage': automation_pct,
                'pattern': pattern.value
            })
        
        # Extract source tables
        tables = re.findall(r'FROM\s+(\w+)', mssql_content, re.IGNORECASE)
        tables.extend(re.findall(r'JOIN\s+(\w+)', mssql_content, re.IGNORECASE))
        source_tables.extend(tables)
    
    # Generate configuration files for each platform
    for platform in platforms:
        converter = UpdatedMSSQLTodbtConverter(platform)
        platform_dir = output_base / platform.value
        
        # Generate schema.yml
        models = [r['model'].replace('.sql', '') for r in conversion_results if r['platform'] == platform.value]
        schema_yml = converter.generate_schema_yml(models)
        with (platform_dir / "schema.yml").open("w", encoding="utf-8") as f:
            f.write(schema_yml)
        
        # Generate sources.yml
        sources_yml = converter.generate_sources_yml(list(set(source_tables)))
        with (platform_dir / "sources.yml").open("w", encoding="utf-8") as f:
            f.write(sources_yml)
        
        # Generate dbt_project.yml
        project_yml = converter.generate_dbt_project_yml(f"mssql_migration_{platform.value}")
        with (platform_dir / "dbt_project.yml").open("w", encoding="utf-8") as f:
            f.write(project_yml)
    
    # Generate summary report
    avg_automation = sum(r['automation_percentage'] for r in conversion_results) / len(conversion_results)
    
    print(f"\n🎯 CONVERSION SUMMARY")
    print(f"Average automation calculated: {avg_automation:.1f}%")
    print(f"Procedures converted: {len(set(r['procedure'] for r in conversion_results))}")
    print(f"Platform targets: {len(platforms)}")
    print(f"Total models generated: {len(conversion_results)}")
    print(f"Manual validation needed: {100 - avg_automation:.1f}%")
    
    # Platform breakdown
    for platform in platforms:
        platform_results = [r for r in conversion_results if r['platform'] == platform.value]
        platform_avg = sum(r['automation_percentage'] for r in platform_results) / len(platform_results)
        print(f"  {platform.value.upper()}: {platform_avg:.1f}% automation")
    
    return conversion_results

if __name__ == "__main__":
    main()