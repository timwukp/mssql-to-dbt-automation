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
            
            # Table references
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
    
    def _init_platform_configs(self) -> Dict[str, Dict]:
        """Initialize platform-specific configurations"""
        return {
            "glue": {"materialized": "table", "file_format": "parquet"},
            "athena": {"materialized": "table", "file_format": "parquet"},
            "redshift": {"materialized": "table", "dist": "auto"}
        }
    
    def calculate_automation_percentage(self, original_content: str, converted_content: str) -> float:
        """Calculate realistic automation percentage"""
        patterns_applied = 0
        for pattern in self.conversion_patterns.keys():
            try:
                if re.search(pattern, original_content, re.IGNORECASE):
                    patterns_applied += 1
            except re.error:
                continue
        
        manual_interventions = 0
        if re.search(r'CASE\s+WHEN.*?THEN.*?ELSE.*?END', converted_content, re.IGNORECASE | re.DOTALL):
            manual_interventions += 1
        if len(re.findall(r'JOIN', converted_content, re.IGNORECASE)) > 2:
            manual_interventions += 1
        if re.search(r'GROUP\s+BY', converted_content, re.IGNORECASE):
            manual_interventions += 1
        
        total_complexity = patterns_applied + manual_interventions
        if total_complexity == 0:
            return 0.0
        
        return (patterns_applied / total_complexity) * 100
    
    def generate_macro_file(self, model_name: str) -> str:
        """Generate DBT macro file content"""
        return f"""-- Macro for {model_name}
{{% macro get_{model_name}_sql() %}}
    SELECT * FROM {{{{ ref('{model_name}') }}}}
{{% endmacro %}}"""
    
    def process_sql_files(self, input_dir: str = "mssql_original", output_dir: str = "dbt_models_enhanced"):
        """Process SQL files with UTF-8 encoding"""
        mssql_dir = Path(input_dir)
        output_base = Path(output_dir)
        
        if not mssql_dir.exists():
            print(f"Input directory {input_dir} not found")
            return
        
        platform_dir = output_base / self.target_platform.value
        platform_dir.mkdir(parents=True, exist_ok=True)
        
        for sql_file in mssql_dir.glob("*.sql"):
            try:
                with open(sql_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                converted_content = content
                for pattern, replacement in self.conversion_patterns.items():
                    converted_content = re.sub(pattern, replacement, converted_content, flags=re.IGNORECASE | re.MULTILINE)
                
                model_name = sql_file.stem
                output_file = platform_dir / f"{model_name}.sql"
                
                with output_file.open("w", encoding="utf-8") as f:
                    f.write(f"-- DBT model for {model_name}\n")
                    f.write(f"-- Platform: {self.target_platform.value}\n\n")
                    f.write(converted_content)
                
                macro_file = platform_dir / "macros" / f"{model_name}_macro.sql"
                macro_file.parent.mkdir(exist_ok=True)
                with macro_file.open("w", encoding="utf-8") as f:
                    f.write(self.generate_macro_file(model_name))
                
                automation_pct = self.calculate_automation_percentage(content, converted_content)
                print(f"Processed {sql_file.name}: {automation_pct:.1f}% automated")
                
            except Exception as e:
                print(f"Error processing {sql_file}: {e}")
        
        self._create_config_files(platform_dir)
    
    def _create_config_files(self, platform_dir: Path):
        """Create DBT configuration files"""
        schema_yml = {
            "version": 2,
            "models": [{"name": "example_model", "description": "Example model"}]
        }
        with (platform_dir / "schema.yml").open("w", encoding="utf-8") as f:
            yaml.dump(schema_yml, f)
        
        sources_yml = {"version": 2, "sources": []}
        with (platform_dir / "sources.yml").open("w", encoding="utf-8") as f:
            yaml.dump(sources_yml, f)
        
        dbt_project = {"name": f"mssql_conversion_{self.target_platform.value}", "version": "1.0.0"}
        with (platform_dir / "dbt_project.yml").open("w", encoding="utf-8") as f:
            yaml.dump(dbt_project, f)

def main():
    """Main conversion function with multi-platform support"""
    print("MSSQL to DBT Multi-Platform Converter")
    
    converter = UpdatedMSSQLTodbtConverter(TargetPlatform.REDSHIFT)
    converter.process_sql_files()
    return True

if __name__ == "__main__":
    main()