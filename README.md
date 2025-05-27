# E-commerce Notification System Testing Guide

This comprehensive guide will walk you through testing the **E-commerce Notification System** that automatically monitors inventory levels and sends email alerts when products run low. The system uses **Redis pub/sub** for real-time communication and **SMTP** for email delivery.

## System Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│  Inventory      │    │     Redis        │    │   Notification      │
│  Service        │───▶│   Pub/Sub        │───▶│   Service           │
│                 │    │                  │    │                     │
│ • Stock Updates │    │ • Low Stock      │    │ • Email Alerts     │
│ • Thresholds    │    │   Messages       │    │ • Admin Notifications│
└─────────────────┘    └──────────────────┘    └─────────────────────┘
                                                          │
                                                          ▼
                                                ┌─────────────────────┐
                                                │    Email Provider   │
                                                │   (Mailtrap SMTP)   │
                                                └─────────────────────┘
```

## The Setup

Run the application using docker compose:

```bash
docker-compose up --build -d
```

Install `jq` to make JSON output more readable in the terminal:

```bash
apt-get update && apt-get install -y jq
```

## Quick System Health Check

Verify all services are running:
```bash
docker-compose ps -a 
```

## Testing Scenarios

### Scenario 1: Direct Email Testing

**Purpose**: Verify the email delivery system works independently

**When to Use**: 
- Initial system setup
- Email configuration troubleshooting
- SMTP connectivity verification

**Steps**:

Send test email:

```bash
curl -X POST "http://localhost/api/v1/notifications/test" | jq . 
```

**Expected Response**:

```json
{
  "message": "Test notification created",
  "notification_id": 1,
  "email_sent": true,
  "admin_email": "admin@example.com"
}
```

**Success Indicators**:
- `email_sent: true` in response
- Email appears in Mailtrap inbox
- Subject: "Test Notification"

![alt text](image.png)

### Scenario 2: Product Creation Flow

**Purpose**: Test automatic inventory creation and threshold setup

**When to Use**:
- New product onboarding
- Inventory service integration testing

**Steps**:

1. Create a test product:

    ```bash
    curl -X POST "http://localhost/api/v1/products/" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "Smart Watch",
        "description": "Waterproof fitness tracker with heart rate monitoring",
        "category": "Electronics",
        "price": 299.99,
        "quantity": 15
      }' | jq .
    ```

2. Extract product ID from response:

    ```bash
    PRODUCT_ID=$(curl -s "http://localhost/api/v1/products/" | \
      jq -r '.[] | select(.name=="Smart Watch") | ._id')
    echo "Product ID: $PRODUCT_ID"
    ```

3. Verify automatic inventory creation:

    ```bash
    curl -s "http://localhost/api/v1/inventory/$PRODUCT_ID" | jq .
    ```

**Expected Results**:
- Product created successfully
- Inventory record auto-generated
- Default reorder threshold set (minimum 5 or 10% of initial quantity)

### Scenario 3: Direct Inventory Update Trigger

**Purpose**: Test low stock detection via manual inventory adjustment

**When to Use**:
- Inventory management scenarios
- Stock adjustment workflows
- Immediate notification triggers

**Steps**:

1. Update inventory below threshold to trigger notification:

    ```bash
    curl -X PUT "http://localhost/api/v1/inventory/$PRODUCT_ID" \
      -H "Content-Type: application/json" \
      -d '{
        "available_quantity": 3,
        "reorder_threshold": 8
      }' | jq .
    ```

2. Wait for notification processing:

    ```bash
    sleep 10
    ```

3. Verify notification was created:

    ```bash
    curl -s "http://localhost/api/v1/notifications/?limit=3" | jq '.[0]'
    ```

    ![alt text](image-1.png)

**Success Flow**:
- Inventory updated successfully
- Low stock condition detected (3 < 8)
- Redis message published
- Notification service receives message
- Email sent to admin
- Database record created

**📧 Expected Email Content**:
- Subject: "Low Stock Alert: Smart Watch"
- Product details with current quantity (3) and threshold (8)

![alt text](image-2.png)

### Scenario 4: Order-Triggered Notification Flow
**Purpose**: Test complete e-commerce workflow from order to notification

**When to Use**:
- End-to-end system testing
- Customer order impact simulation
- Multi-service integration verification

**Setup**:

1. Create another test product with specific threshold:

    ```bash
    curl -X POST "http://localhost/api/v1/products/" \
      -H "Content-Type: application/json" \
      -d '{
        "name": "Wireless Noise-Cancelling Headphones",
        "description": "Premium headphones with active noise cancellation",
        "category": "Audio",
        "price": 149.99,
        "quantity": 12
      }' | jq .
    ```

2. Get the new product ID:

    ```bash
    ORDER_PRODUCT_ID=$(curl -s "http://localhost/api/v1/products/" | \
      jq -r '.[] | select(.name=="Wireless Noise-Cancelling Headphones") | ._id')
    echo "Order Product ID: $ORDER_PRODUCT_ID"
    ```

**User Registration & Order Process**:

3. Register a test user:

    ```bash
    curl -X POST "http://localhost/api/v1/auth/register" \
      -H "Content-Type: application/json" \
      -d '{
        "email": "order-test@example.com",
        "password": "OrderTest123",
        "first_name": "Order",
        "last_name": "Tester",
        "phone": "555-ORDER-TEST"
      }' | jq .
    ```

4. Login to get authentication token:

    ```bash
    TOKEN=$(curl -s -X POST "http://localhost/api/v1/auth/login" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=order-test@example.com&password=OrderTest123" | \
      jq -r .access_token)
    ```

5. Get user ID for order creation:

    ```bash
    USER_ID=$(curl -s -X GET "http://localhost/api/v1/users/me" \
      -H "Authorization: Bearer $TOKEN" | jq -r .id)
    ```

6. Place order that will trigger low stock (12 - 8 = 4, which is < 5 threshold):

    ```bash
    curl -X POST "http://localhost/api/v1/orders/" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "user_id": "'$USER_ID'",
        "items": [
          {
            "product_id": "'$ORDER_PRODUCT_ID'",
            "quantity": 8,
            "price": 149.99
          }
        ],
        "shipping_address": {
          "line1": "123 Order Test Lane",
          "city": "Notification City",
          "state": "NC",
          "postal_code": "12345",
          "country": "Testland"
        }
      }' | jq .
    ```

**Verification**:

7. Wait for order processing and notification:

    ```bash
    sleep 15
    ```

8. Check inventory was reduced:

    ```bash
    curl -s "http://localhost/api/v1/inventory/$ORDER_PRODUCT_ID" | jq .
    ```

9. Verify notification was triggered:

    ```bash
    curl -s "http://localhost/api/v1/notifications/?limit=5" | \
      jq '.[] | select(.type=="low_stock") | {id, subject, status, created_at}'
    ```

**Complete Order Flow**:

1. **Order Placed** → Order Service creates order
2. **Inventory Reserved** → Inventory Service reduces available stock
3. **Low Stock Detected** → Available quantity (4) < threshold (5)
4. **Redis Message** → Inventory publishes low stock event
5. **Notification Triggered** → Notification Service processes message
6. **Email Sent** → Admin receives low stock alert
7. **Database Updated** → Notification record stored

### Scenario 5: Direct Redis Messaging

**Purpose**: Test Redis pub/sub communication directly

**When to Use**:
- Debugging message queue issues
- Testing notification service isolation
- Verifying Redis connectivity

**Steps**:

1. Send direct Redis message:

    ```bash
    docker-compose exec redis redis-cli PUBLISH inventory:low-stock '{
      "type": "low_stock",
      "product_id": "redis-direct-test",
      "product_name": "Direct Redis Test Product",
      "current_quantity": 2,
      "threshold": 5,
      "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'"
    }'
    ```

2. Wait for processing:

    ```bash
    sleep 5
    ```

3. Check notification was created:

    ```bash
    curl -s "http://localhost/api/v1/notifications/?limit=3" | \
      jq '.[] | select(.data.product_id=="redis-direct-test")'
    ```

**Success Indicators**:
- Redis returns `(integer) 1` (message published to 1 subscriber)
- Notification appears in database
- Email sent to admin

## Conclusion

This comprehensive testing guide covers all major notification scenarios in the e-commerce system. The notification service acts as a critical business intelligence tool, ensuring administrators are promptly informed about inventory levels that require attention.

**Key Benefits**:
- **Prevents Stockouts**: Proactive alerts before inventory depletion
- **Optimizes Cash Flow**: Just-in-time inventory management
- **Improves Customer Satisfaction**: Avoids backorders and delays
- **Reduces Manual Monitoring**: Automated surveillance of thousands of products