-- dbt Model: Customer Analytics (Converted from MSSQL Stored Procedure)
-- Amazon Q Developer automated conversion with Redshift optimizations

{{ config(
    materialized='table',
    sort=['total_revenue'],
    dist='customer_id',
    tags=['analytics', 'customer']
) }}

WITH customer_orders AS (
    SELECT 
        c.customer_id,
        c.customer_name,
        c.region,
        o.order_id,
        o.order_amount,
        o.order_date
    FROM {{ ref('customers') }} c
    LEFT JOIN {{ ref('orders') }} o 
        ON c.customer_id = o.customer_id
    WHERE o.order_date BETWEEN '{{ var("start_date") }}' AND '{{ var("end_date") }}'
        {% if var("region", none) is not none %}
        AND c.region = '{{ var("region") }}'
        {% endif %}
),

customer_metrics AS (
    SELECT 
        customer_id,
        customer_name,
        region,
        COUNT(order_id) as total_orders,
        SUM(order_amount) as total_revenue,
        AVG(order_amount) as avg_order_value,
        MAX(order_date) as last_order_date
    FROM customer_orders
    WHERE order_id IS NOT NULL
    GROUP BY customer_id, customer_name, region
)

SELECT 
    customer_id,
    customer_name,
    region,
    total_orders,
    total_revenue,
    avg_order_value,
    CASE 
        WHEN total_revenue > 10000 THEN 'High Value'
        WHEN total_revenue > 5000 THEN 'Medium Value'
        ELSE 'Low Value'
    END as customer_segment,
    DATEDIFF('day', last_order_date, CURRENT_DATE) as days_since_last_order
FROM customer_metrics
ORDER BY total_revenue DESC