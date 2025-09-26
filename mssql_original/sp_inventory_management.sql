-- Original MSSQL Stored Procedure: Inventory Management
CREATE PROCEDURE sp_inventory_management
    @warehouse_id INT,
    @low_stock_threshold INT = 10
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @total_products INT;
    DECLARE @low_stock_count INT;
    
    -- Get total product count
    SELECT @total_products = COUNT(*) 
    FROM inventory 
    WHERE warehouse_id = @warehouse_id;
    
    -- Complex inventory analysis with multiple CTEs equivalent
    WITH current_inventory AS (
        SELECT 
            i.product_id,
            p.product_name,
            i.current_stock,
            i.reserved_stock,
            i.available_stock,
            i.last_updated
        FROM inventory i
        INNER JOIN products p ON i.product_id = p.product_id
        WHERE i.warehouse_id = @warehouse_id
    ),
    stock_movements AS (
        SELECT 
            product_id,
            SUM(CASE WHEN movement_type = 'IN' THEN quantity ELSE 0 END) as total_inbound,
            SUM(CASE WHEN movement_type = 'OUT' THEN quantity ELSE 0 END) as total_outbound,
            COUNT(*) as movement_count
        FROM stock_movements
        WHERE warehouse_id = @warehouse_id
            AND movement_date >= DATEADD(day, -30, GETDATE())
        GROUP BY product_id
    )
    SELECT 
        ci.product_id,
        ci.product_name,
        ci.current_stock,
        ci.available_stock,
        sm.total_inbound,
        sm.total_outbound,
        sm.movement_count,
        CASE 
            WHEN ci.available_stock <= @low_stock_threshold THEN 'CRITICAL'
            WHEN ci.available_stock <= (@low_stock_threshold * 2) THEN 'LOW'
            ELSE 'NORMAL'
        END as stock_status,
        CASE 
            WHEN sm.movement_count > 0 THEN sm.total_outbound / 30.0
            ELSE 0
        END as daily_usage_rate,
        CASE 
            WHEN sm.total_outbound > 0 THEN ci.available_stock / (sm.total_outbound / 30.0)
            ELSE 999
        END as days_of_stock
    FROM current_inventory ci
    LEFT JOIN stock_movements sm ON ci.product_id = sm.product_id
    ORDER BY 
        CASE 
            WHEN ci.available_stock <= @low_stock_threshold THEN 1
            WHEN ci.available_stock <= (@low_stock_threshold * 2) THEN 2
            ELSE 3
        END,
        ci.available_stock ASC;
END