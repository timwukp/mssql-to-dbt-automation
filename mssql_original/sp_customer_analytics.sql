-- Original MSSQL Stored Procedure: Customer Analytics
CREATE PROCEDURE sp_customer_analytics
    @region VARCHAR(50) = NULL,
    @start_date DATE,
    @end_date DATE
AS
BEGIN
    SET NOCOUNT ON;
    
    SELECT 
        c.customer_id,
        c.customer_name,
        c.region,
        COUNT(o.order_id) as total_orders,
        SUM(o.order_amount) as total_revenue,
        AVG(o.order_amount) as avg_order_value,
        CASE 
            WHEN SUM(o.order_amount) > 10000 THEN 'High Value'
            WHEN SUM(o.order_amount) > 5000 THEN 'Medium Value'
            ELSE 'Low Value'
        END as customer_segment,
        DATEDIFF(day, MAX(o.order_date), GETDATE()) as days_since_last_order
    FROM customers c
    LEFT JOIN orders o ON c.customer_id = o.customer_id
    WHERE o.order_date BETWEEN @start_date AND @end_date
        AND (@region IS NULL OR c.region = @region)
    GROUP BY c.customer_id, c.customer_name, c.region
    HAVING COUNT(o.order_id) > 0
    ORDER BY total_revenue DESC;
END