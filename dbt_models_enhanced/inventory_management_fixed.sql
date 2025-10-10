-- dbt Model: Inventory Management (Generated from MSSQL)
-- Platform: Multi-target (Glue/Athena/Redshift)
-- Pattern: full_load
-- Auto-generated DBT model

{{ config(
    materialized='table',
    tags=['inventory', 'operations']
) }}

WITH inventory_summary AS (
    SELECT 
        product_id,
        product_name,
        category,
        warehouse_id,
        current_stock,
        reorder_level,
        unit_cost,
        last_updated
    FROM {{ ref('inventory') }}
    WHERE warehouse_id = {{ var('warehouse_id') }}
),

low_stock_items AS (
    SELECT 
        product_id,
        product_name,
        current_stock,
        reorder_level,
        (reorder_level - current_stock) as stock_deficit
    FROM inventory_summary
    WHERE current_stock < {{ var('low_stock_threshold') }}
)

SELECT 
    i.product_id,
    i.product_name,
    i.category,
    i.current_stock,
    i.reorder_level,
    i.unit_cost,
    CASE 
        WHEN i.current_stock <= 0 THEN 'Out of Stock'
        WHEN i.current_stock < i.reorder_level THEN 'Low Stock'
        ELSE 'In Stock'
    END as stock_status,
    l.stock_deficit
FROM inventory_summary i
LEFT JOIN low_stock_items l ON i.product_id = l.product_id
ORDER BY i.current_stock ASC