-- dbt Model: Sales Reporting (Generated from MSSQL)
-- Platform: Multi-target (Glue/Athena/Redshift)
-- Pattern: full_load
-- Auto-generated DBT model

{{ config(
    materialized='view',
    tags=['reporting', 'sales']
) }}

WITH monthly_sales AS (
    SELECT 
        EXTRACT(YEAR FROM order_date) as sales_year,
        EXTRACT(MONTH FROM order_date) as sales_month,
        region,
        SUM(order_amount) as monthly_revenue,
        COUNT(order_id) as monthly_orders,
        COUNT(DISTINCT customer_id) as unique_customers
    FROM {{ ref('orders') }}
    WHERE order_date >= '{{ var("start_date") }}'
        AND order_date <= '{{ var("end_date") }}'
    GROUP BY 
        EXTRACT(YEAR FROM order_date),
        EXTRACT(MONTH FROM order_date),
        region
)

SELECT 
    sales_year,
    sales_month,
    region,
    monthly_revenue,
    monthly_orders,
    unique_customers,
    ROUND(monthly_revenue / monthly_orders, 2) as avg_order_value
FROM monthly_sales
ORDER BY sales_year DESC, sales_month DESC, monthly_revenue DESC