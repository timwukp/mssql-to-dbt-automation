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
            # Remove MSSQL procedure syntax - with proper flags
            r'CREATE\s+PROCEDURE\s+[\w\[\]\.]+.*?AS\s*BEGIN': '',
            r'SET\s+NOCOUNT\s+ON;?': '',
            r'END\s*$': '',
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
            return 0.0  # No automation if no patterns applied
        
        automation_percentage = (patterns_applied / total_complexity) * 100
        return automation_percentage  # Return actual calculated percentage
        
        automation_percentage = (patterns_applied / total_complexity) * 100
        return automation_percentage  # Return actual calculated percentage

def main():
    """Main conversion function with multi-platform support"""
    print("MSSQL to DBT Multi-Platform Converter")
    return True

if __name__ == "__main__":
    main()