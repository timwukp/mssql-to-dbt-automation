-- dbt Model: Inventory Summary Statistics
-- Amazon Q Developer automated conversion - replaces summary logic from stored procedure

{{ config(
    materialized='view',
    tags=['inventory', 'summary']
) }}

WITH inventory_stats AS (
    SELECT 
        warehouse_id,
        COUNT(*) as total_products,
        COUNT(CASE WHEN available_stock <= {{ var('low_stock_threshold', 10) }} THEN 1 END) as low_stock_products,
        AVG(available_stock) as avg_stock_level,
        MIN(available_stock) as min_stock_level,
        MAX(available_stock) as max_stock_level
    FROM {{ ref('inventory_management') }}
    GROUP BY warehouse_id
)

SELECT 
    warehouse_id,
    total_products,
    low_stock_products,
    CASE 
        WHEN total_products > 0 THEN 
            ROUND((low_stock_products::FLOAT / total_products * 100), 2)
        ELSE 0 
    END as low_stock_percentage,
    avg_stock_level,
    min_stock_level,
    max_stock_level,
    CURRENT_TIMESTAMP as summary_generated_at
FROM inventory_stats