CREATE SCHEMA auth;
CREATE SCHEMA baseschema;

CREATE TABLE auth.sessionInfo(
    session_id CHAR(8) PRIMARY KEY,
    session_password CHAR(8),
    retailer_id CHAR(8)
);

CREATE TABLE baseschema.Licence(
  licence_code CHAR(5) PRIMARY KEY,
  deeplink VARCHAR(100) NOT NULL,
  order_id CHAR(8)
);

CREATE TABLE baseschema.RetailerAccount(
    retailer_id CHAR(8) PRIMARY KEY,
    stripe_customer_id CHAR(2),
    name VARCHAR(50) NOT NULL,
    email VARCHAR(50) NOT NULL
);

CREATE TABLE baseschema.subclient(
    subclient_id CHAR(8) PRIMARY KEY,
    subclient_name VARCHAR(50) NOT NULL,
    retailer_id CHAR(8) REFERENCES baseschema.RetailerAccount(retailer_id)
);

CREATE TABLE baseschema.Subscription (
    order_id CHAR(24) PRIMARY KEY,
    purchase_token CHAR(144),
    subscription_date TIMESTAMP,
    subclient_id CHAR(8) REFERENCES baseschema.subclient(subclient_id),
    location VARCHAR(50) NOT NULL
);

CREATE TABLE baseschema.Licence (
    licence_code CHAR(5) PRIMARY KEY,
    deeplink VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    order_id CHAR(24) REFERENCES baseschema.Subscription(order_id)
);

CREATE TABLE baseschema.Subscription_History (
    order_id CHAR(24) PRIMARY KEY REFERENCES baseschema.Subscription(order_id),
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    subclient_id CHAR(16) REFERENCES baseschema.subclient(subclient_id)
);

CREATE FUNCTION before_subscription_insert()
RETURNS TRIGGER AS $$
DECLARE
    old_order_id CHAR(24);
    Start_date1 TIMESTAMP;
    End_date1 TIMESTAMP;
BEGIN
    -- Check if there's an existing subscription for the same retailer_id and load the details of the latest one
    SELECT order_id, subscription_date, CURRENT_TIMESTAMP
    INTO old_order_id, Start_date1, End_date1
    FROM baseschema.Subscription
    WHERE subclient_id = NEW.subclient_id
    ORDER BY subscription_date DESC
    LIMIT 1;

    -- If a subscription existed, insert it into Subscription_History before inserting a new one
    IF old_order_id IS NOT NULL THEN
        INSERT INTO baseschema.Subscription_History (order_id, start_date, end_date, subclient_id)
        VALUES (old_order_id, Start_date1, End_date1, NEW.subclient_id);
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER before_subscription_insert_trigger
BEFORE INSERT ON baseschema.Subscription
FOR EACH ROW
EXECUTE FUNCTION before_subscription_insert();
