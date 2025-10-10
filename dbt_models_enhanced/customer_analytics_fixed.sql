-- dbt Model: Customer Analytics (Generated from MSSQL)
-- Platform: Multi-target (Glue/Athena/Redshift)
-- Pattern: full_load
-- Auto-generated DBT model

{{ config(
    materialized='table',
    tags=['analytics', 'customer'],
    sort=['total_revenue'],
    dist='customer_id'
) }}

-- Variable validation
{% set required_vars = ['start_date', 'end_date'] %}
{% for var_name in required_vars %}
    {% if var(var_name, none) is none %}
        {{ exceptions.raise_compiler_error("Required variable '" + var_name + "' is not defined") }}
    {% endif %}
{% endfor %}

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
)

SELECT 
    customer_id,
    customer_name,
    region,
    COUNT(order_id) as total_orders,
    SUM(order_amount) as total_revenue,
    AVG(order_amount) as avg_order_value,
    DATE_DIFF('day', MAX(order_date), CURRENT_DATE) as days_since_last_order
FROM customer_orders
WHERE order_id IS NOT NULL
GROUP BY customer_id, customer_name, region
ORDER BY total_revenue DESC