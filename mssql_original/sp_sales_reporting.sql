-- Original MSSQL Stored Procedure: Sales Reporting with Regional Security
CREATE PROCEDURE sp_sales_reporting
    @user_region VARCHAR(50),
    @report_month INT,
    @report_year INT
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Role-based security check
    IF @user_region NOT IN ('NORTH', 'SOUTH', 'EAST', 'WEST')
    BEGIN
        RAISERROR('Invalid region access', 16, 1);
        RETURN;
    END
    
    -- Temporary table for calculations
    CREATE TABLE #monthly_sales (
        product_id INT,
        product_name VARCHAR(100),
        region VARCHAR(50),
        monthly_revenue DECIMAL(15,2),
        units_sold INT
    );
    
    INSERT INTO #monthly_sales
    SELECT 
        p.product_id,
        p.product_name,
        s.region,
        SUM(s.sale_amount) as monthly_revenue,
        SUM(s.quantity) as units_sold
    FROM products p
    INNER JOIN sales s ON p.product_id = s.product_id
    WHERE MONTH(s.sale_date) = @report_month
        AND YEAR(s.sale_date) = @report_year
        AND s.region = @user_region
    GROUP BY p.product_id, p.product_name, s.region;
    
    -- Final result with rankings
    SELECT 
        product_id,
        product_name,
        region,
        monthly_revenue,
        units_sold,
        RANK() OVER (ORDER BY monthly_revenue DESC) as revenue_rank,
        PERCENT_RANK() OVER (ORDER BY monthly_revenue) as revenue_percentile
    FROM #monthly_sales
    ORDER BY monthly_revenue DESC;
    
    DROP TABLE #monthly_sales;
END