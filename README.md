# E-commerce Low Stock Notification System

## System Workflow Overview

The workflow remains the same as described earlier:
1. Inventory thresholds are configured
2. Orders or inventory updates reduce stock levels
3. Low stock conditions trigger notifications via Redis
4. Admin receives email notifications

## Step-by-Step Testing Procedure (Revised)

### 1. Start the System

```bash
docker-compose up -d
```

Wait for all services to initialize (about 30 seconds).

### 2. Verify Services Are Running

```bash
# Check service status
docker-compose ps

# Verify API Gateway is responsive
curl http://localhost/health
```

All services should be in the "Up" state with their respective health checks passing.

### 3. Create a Dedicated Test Product

```bash
# Create a unique test product with an initial quantity
curl -X POST "http://localhost/api/v1/products/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Notification Test Monitor",
    "description": "Product specifically for testing notification system",
    "category": "Electronics",
    "price": 249.99,
    "quantity": 10
  }' | jq .
```

Save the product ID from the response:

```bash
PRODUCT_ID=$(curl -s -X GET "http://localhost/api/v1/products/" | \
  jq -r '.[] | select(.name=="Notification Test Monitor") | ._id')

echo "Product ID: $PRODUCT_ID"
```

### 4. Verify Inventory Setup

Check that the inventory record was automatically created for the product:

```bash
# Check initial inventory
curl -s -X GET "http://localhost/api/v1/inventory/$PRODUCT_ID" | jq .
```

You should see something like:
```json
{
  "id": 1,
  "product_id": "your-product-id",
  "available_quantity": 10,
  "reserved_quantity": 0,
  "reorder_threshold": 5,
  "created_at": "2023-05-27T12:00:00",
  "updated_at": "2023-05-27T12:00:00"
}
```

### 5. Test Direct Email Functionality

Test the email notification system directly:

```bash
# Send a test notification
curl -X POST "http://localhost/api/v1/notifications/test"
```

Check your Mailtrap inbox for the test email. You should see a "Test Notification" email.

### 6. Trigger a Low Stock Notification via Inventory Update

Update the inventory to simulate a low stock condition:

```bash
# Update inventory to below threshold
curl -X PUT "http://localhost/api/v1/inventory/$PRODUCT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "available_quantity": 3,
    "reorder_threshold": 5
  }' | jq .
```

Check your Mailtrap inbox again. You should see a "Low Stock Alert" email for "Notification Test Monitor" with details about the product.

### 7. Verify Notification Database Record

Check that the notification was recorded in the database:

```bash
# List recent notifications
curl -s "http://localhost/api/v1/notifications/?limit=5" | jq .
```

You should see a low stock notification with status "sent" for the "Notification Test Monitor" product.

### 8. Test Order-Triggered Notification

Test the complete flow from order placement to notification by creating another unique product:

```bash
# Create a second unique test product
curl -X POST "http://localhost/api/v1/products/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Order Flow Test Keyboard",
    "description": "Product for testing order-triggered notifications",
    "category": "Electronics",
    "price": 89.99,
    "quantity": 10
  }' | jq .

# Get the new product ID
ORDER_TEST_PRODUCT_ID=$(curl -s -X GET "http://localhost/api/v1/products/" | \
  jq -r '.[] | select(.name=="Order Flow Test Keyboard") | ._id')

echo "Order Test Product ID: $ORDER_TEST_PRODUCT_ID"

# Check its inventory and threshold
curl -s -X GET "http://localhost/api/v1/inventory/$ORDER_TEST_PRODUCT_ID" | jq .

# Create a user (if one doesn't exist)
curl -X POST "http://localhost/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "notification-test@example.com",
    "password": "Password123",
    "first_name": "Notification",
    "last_name": "Tester",
    "phone": "555-123-9876"
  }' | jq .

# Login to get token
TOKEN=$(curl -s -X POST "http://localhost/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=notification-test@example.com&password=Password123" | jq -r .access_token)

# Get user ID
USER_ID=$(curl -s -X GET "http://localhost/api/v1/users/me" \
  -H "Authorization: Bearer $TOKEN" | jq -r .id)

# Place an order that will reduce inventory below threshold
curl -s -X POST "http://localhost/api/v1/orders/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "'$USER_ID'",
    "items": [
      {
        "product_id": "'$ORDER_TEST_PRODUCT_ID'",
        "quantity": 6,
        "price": 89.99
      }
    ],
    "shipping_address": {
      "line1": "456 Notification St",
      "city": "Alert City",
      "state": "NT",
      "postal_code": "54321",
      "country": "Testland"
    }
  }' | jq .
```

Wait a few seconds for the order to be processed, then check your Mailtrap inbox for another low stock notification specifically for the "Order Flow Test Keyboard" product.

### 9. Check Notification Service Logs

Examine the notification service logs to see the entire process:

```bash
# View notification service logs
docker-compose logs notification-service | tail -n 50
```

Look for messages showing the processing of notifications for our test products.

### 10. Test Direct Redis Message

Test sending a notification message directly through Redis:

```bash
# Publish a test Redis message directly
docker-compose exec redis redis-cli PUBLISH inventory:low-stock '{"type":"low_stock","product_id":"direct-redis-test","product_name":"Direct Redis Test Product","current_quantity":2,"threshold":5}'
```

After publishing the direct Redis message, check your Mailtrap inbox for a notification about "Direct Redis Test Product".

### 11. Test System Resilience

Test how the system handles service outages:

```bash
# Create another unique product for resilience testing
curl -X POST "http://localhost/api/v1/products/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Resilience Test Headphones",
    "description": "Product for testing system resilience",
    "category": "Audio",
    "price": 129.99,
    "quantity": 10
  }' | jq .

# Get the resilience test product ID
RESILIENCE_PRODUCT_ID=$(curl -s -X GET "http://localhost/api/v1/products/" | \
  jq -r '.[] | select(.name=="Resilience Test Headphones") | ._id')

echo "Resilience Test Product ID: $RESILIENCE_PRODUCT_ID"

# Stop the notification service
docker-compose stop notification-service

# Trigger a low stock condition
curl -X PUT "http://localhost/api/v1/inventory/$RESILIENCE_PRODUCT_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "available_quantity": 1,
    "reorder_threshold": 5
  }' | jq .

# Start the notification service again
docker-compose start notification-service

# Check logs to see if message was processed after restart
docker-compose logs --tail=50 notification-service
```

## Verifying Results

After running the tests, you should have:

1. **Three Product-Specific Notifications**:
   - "Notification Test Monitor" (triggered by direct inventory update)
   - "Order Flow Test Keyboard" (triggered by order placement)
   - "Resilience Test Headphones" (testing service resilience)

2. **Two Additional Notifications**:
   - Test notification (from the /test endpoint)
   - "Direct Redis Test Product" (from manual Redis message)

In your Mailtrap inbox, each notification should have:
- A clear subject line identifying the product
- The current quantity and threshold information
- Product details formatted in HTML

## Checking Database Records

To review all notifications in the database:

```bash
# View all stored notifications
curl -s "http://localhost/api/v1/notifications/?limit=10" | jq .
```

Each notification should have a status of "sent" if email delivery was successful.

## Conclusion

By using distinct product names for each test case, you can clearly identify which notifications correspond to which test scenarios. This makes it easier to verify that each part of the system is working correctly and to troubleshoot any issues that might arise.

The low stock notification system provides a streamlined way to monitor inventory levels and alert administrators when products need to be replenished, helping to prevent stockouts and ensure a smooth shopping experience for customers.