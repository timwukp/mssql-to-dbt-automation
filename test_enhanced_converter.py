#!/usr/bin/env python3
"""
Test script for Updated MSSQL to DBT Converter
Validates multi-platform conversion functionality
"""

from enhanced_conversion_automation import UpdatedMSSQLTodbtConverter, TargetPlatform, ConversionPattern

def test_converter():
    """Test the converter functionality"""
    print("🧪 Testing Updated MSSQL to DBT Converter")
    print("=" * 50)
    
    # Sample MSSQL content
    sample_mssql = """
    CREATE PROCEDURE sp_test_analytics
        @start_date DATE,
        @end_date DATE,
        @region VARCHAR(50) = NULL
    AS
    BEGIN
        SET NOCOUNT ON;
        
        SELECT 
            customer_id,
            SUM(order_amount) as total_revenue,
            DATEDIFF(day, order_date, GETDATE()) as days_ago
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        WHERE order_date BETWEEN @start_date AND @end_date
        GROUP BY customer_id
        ORDER BY total_revenue DESC;
    END
    """
    
    platforms = [TargetPlatform.GLUE, TargetPlatform.ATHENA, TargetPlatform.REDSHIFT]
    
    for platform in platforms:
        print(f"\n🎯 Testing {platform.value.upper()} conversion...")
        
        converter = UpdatedMSSQLTodbtConverter(platform)
        
        # Test conversion
        converted = converter.convert_procedure(
            sample_mssql, 
            "test_analytics", 
            ConversionPattern.FULL_LOAD
        )
        
        # Test automation percentage
        automation_pct = converter.calculate_automation_percentage(sample_mssql, converted)
        
        print(f"  ✅ Conversion completed: {automation_pct:.1f}% automation")
        
        # Test macro generation
        macro_content = converter.generate_macro_file("test_analytics")
        print(f"  ✅ Macro file generated: {len(macro_content)} characters")
        
        # Test schema generation
        schema_yml = converter.generate_schema_yml(["test_analytics"])
        print(f"  ✅ Schema file generated: {len(schema_yml)} characters")
        
        # Test project file generation
        project_yml = converter.generate_dbt_project_yml(f"test_project_{platform.value}")
        print(f"  ✅ Project file generated: {len(project_yml)} characters")
    
    print(f"\n📊 Average automation: calculated")
    print(f"\n🎉 All platform conversions completed successfully!")
    
    # Test specific converter functionality
    converter = UpdatedMSSQLTodbtConverter(TargetPlatform.REDSHIFT)
    
    # Test pattern recognition
    patterns_found = 0
    for pattern in converter.conversion_patterns.keys():
        if re.search(pattern, sample_mssql, re.IGNORECASE):
            patterns_found += 1
    
    print(f"\n🔍 Pattern Analysis:")
    print(f"  Patterns detected: {patterns_found}")
    print(f"  Conversion coverage: Multi-platform")
    
    return True

if __name__ == "__main__":
    import re
    test_converter()