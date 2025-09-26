-- dbt Model: Sales Reporting with Regional Security (Converted from MSSQL)
-- Amazon Q Developer automated conversion with Redshift row-level security

{{ config(
    materialized='view',
    tags=['sales', 'reporting', 'security']
) }}

WITH monthly_sales AS (
    SELECT 
        p.product_id,
        p.product_name,
        s.region,
        SUM(s.sale_amount) as monthly_revenue,
        SUM(s.quantity) as units_sold
    FROM {{ ref('products') }} p
    INNER JOIN {{ ref('sales') }} s 
        ON p.product_id = s.product_id
    WHERE EXTRACT(MONTH FROM s.sale_date) = {{ var('report_month') }}
        AND EXTRACT(YEAR FROM s.sale_date) = {{ var('report_year') }}
        -- Regional security implemented via dbt variables and Redshift RLS
        {% if var('user_region', none) is not none %}
        AND s.region = '{{ var('user_region') }}'
        {% endif %}
    GROUP BY p.product_id, p.product_name, s.region
)

SELECT 
    product_id,
    product_name,
    region,
    monthly_revenue,
    units_sold,
    RANK() OVER (ORDER BY monthly_revenue DESC) as revenue_rank,
    PERCENT_RANK() OVER (ORDER BY monthly_revenue) as revenue_percentile,
    -- Additional dbt enhancements
    '{{ var('report_month') }}' as report_month,
    '{{ var('report_year') }}' as report_year,
    CURRENT_TIMESTAMP as generated_at
FROM monthly_sales
ORDER BY monthly_revenue DESC