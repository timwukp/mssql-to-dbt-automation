-- dbt Model: Inventory Management (Converted from MSSQL Stored Procedure)
-- Amazon Q Developer automated conversion with Redshift optimizations

{{ config(
    materialized='table',
    sort=['stock_status', 'available_stock'],
    dist='product_id',
    tags=['inventory', 'operations']
) }}

WITH current_inventory AS (
    SELECT 
        i.product_id,
        p.product_name,
        i.current_stock,
        i.reserved_stock,
        i.available_stock,
        i.last_updated,
        i.warehouse_id
    FROM {{ ref('inventory') }} i
    INNER JOIN {{ ref('products') }} p 
        ON i.product_id = p.product_id
    WHERE i.warehouse_id = {{ var('warehouse_id') }}
),

stock_movements AS (
    SELECT 
        product_id,
        SUM(CASE WHEN movement_type = 'IN' THEN quantity ELSE 0 END) as total_inbound,
        SUM(CASE WHEN movement_type = 'OUT' THEN quantity ELSE 0 END) as total_outbound,
        COUNT(*) as movement_count
    FROM {{ ref('stock_movements') }}
    WHERE warehouse_id = {{ var('warehouse_id') }}
        AND movement_date >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY product_id
)

SELECT 
    product_id,
    product_name,
    current_stock,
    available_stock,
    COALESCE(sm.total_inbound, 0) as total_inbound,
    COALESCE(sm.total_outbound, 0) as total_outbound,
    COALESCE(sm.movement_count, 0) as movement_count,
    CASE 
        WHEN available_stock <= {{ var('low_stock_threshold', 10) }} THEN 'CRITICAL'
        WHEN available_stock <= ({{ var('low_stock_threshold', 10) }} * 2) THEN 'LOW'
        ELSE 'NORMAL'
    END as stock_status,
    CASE 
        WHEN COALESCE(sm.movement_count, 0) > 0 THEN COALESCE(sm.total_outbound, 0) / 30.0
        ELSE 0
    END as daily_usage_rate,
    warehouse_id,
    CURRENT_TIMESTAMP as analysis_timestamp
FROM current_inventory ci
LEFT JOIN stock_movements sm 
    ON ci.product_id = sm.product_id
ORDER BY 
    CASE stock_status
        WHEN 'CRITICAL' THEN 1
        WHEN 'LOW' THEN 2
        ELSE 3
    END,
    available_stock ASC