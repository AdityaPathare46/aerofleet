# 🚀 AeroFleet API - Test Guide

## ✅ Server is Running!

Your API is live at: **http://localhost:8000**

## 📚 Interactive Documentation

Open these in your browser:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🧪 Quick API Tests

### 1. Health Check
```bash
curl http://localhost:8000/health
```

### 2. Get Agent Roster (11 core agents)
```bash
curl http://localhost:8000/api/v1/agents/roster
```

### 3. Get Specific Agent Details
```bash
curl http://localhost:8000/api/v1/agents/roster/ROUTE
curl http://localhost:8000/api/v1/agents/roster/BATTERY
```

### 4. Register a User + Get a Token

Orders are user-scoped, so register and log in first:
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "operator1", "email": "operator1@example.com", "password": "changeme123"}'

TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/auth/login" \
  -d "username=operator1&password=changeme123" \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
```

### 5. Check Fleet & Depot State
```bash
curl http://localhost:8000/api/v1/fleet/drones
curl http://localhost:8000/api/v1/fleet/depots
```
Copy a `depot_id` from the response (e.g. `DEPOT-1`) for the next step.

### 6. Create a Delivery Order
```bash
curl -X POST "http://localhost:8000/api/v1/orders/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "origin_depot_id": "DEPOT-1",
    "destination_lat": 18.53,
    "destination_lon": 73.86,
    "payload_kg": 1.5,
    "priority": "STANDARD",
    "deadline_minutes": 30
  }'
```

### 7. List / Get Orders
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/orders/
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/orders/ORD-XXXXXXXX
```

### 8. Dispatch an Order (deterministic CBF check only — fast)
```bash
curl -X POST "http://localhost:8000/api/v1/orders/ORD-XXXXXXXX/dispatch" \
  -H "Authorization: Bearer $TOKEN"
```

### 9. Dispatch With the Full Agent Council (slower, needs Ollama or `USE_MOCK_AGENTS=true`)
```bash
curl -X POST "http://localhost:8000/api/v1/orders/ORD-XXXXXXXX/dispatch?use_council=true" \
  -H "Authorization: Bearer $TOKEN"
```

### 10. Calculate a Route Directly
```bash
curl -X POST "http://localhost:8000/api/v1/routes/calculate" \
  -H "Content-Type: application/json" \
  -d '{"origin_lat": 18.5204, "origin_lon": 73.8567, "destination_lat": 18.53, "destination_lon": 73.86, "payload_kg": 1.5}'
```

### 11. Check Airspace Zones & Geofence
```bash
curl http://localhost:8000/api/v1/geofence/zones
curl "http://localhost:8000/api/v1/geofence/check?lat=18.53&lon=73.86"
```

### 12. Verify the CBF Safety Gate Directly
```bash
curl -X POST "http://localhost:8000/api/v1/safety/verify" \
  -H "Content-Type: application/json" \
  -d '{"dispatch_plan": {"wind_speed_mps": 14, "max_wind_mps": 10}}'
```

### 13. Run the Full Council Debate (Advanced)
```bash
curl -X POST "http://localhost:8000/api/v1/agents/debate" \
  -H "Content-Type: application/json" \
  -d '{
    "dispatch_plan": {
      "order_id": "TEST-001",
      "outbound_km": 4.2, "return_km": 4.2,
      "payload_kg": 1.5, "priority": "STANDARD",
      "battery_capacity_wh": 500, "battery_soc": 1.0,
      "wind_speed_mps": 3.0, "zone_colour": "GREEN"
    },
    "chat_history": []
  }'
```

## 🎯 Example Workflow — End to End

```bash
# 1. Register + login (see step 4 above) to get $TOKEN

# 2. Check available depots and drones
curl http://localhost:8000/api/v1/fleet/depots

# 3. Create a delivery order
ORDER_ID=$(curl -s -X POST "http://localhost:8000/api/v1/orders/" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"origin_depot_id": "DEPOT-1", "destination_lat": 18.53, "destination_lon": 73.86, "payload_kg": 1.5}' \
  | grep -o '"order_id":"[^"]*"' | cut -d'"' -f4)

# 4. Dispatch it
curl -X POST "http://localhost:8000/api/v1/orders/$ORDER_ID/dispatch" -H "Authorization: Bearer $TOKEN"

# 5. Check the fleet digital twin
curl http://localhost:8000/api/v1/fleet/twin
```

## 🌐 Browser Testing

Just open: **http://localhost:8000/docs**

You'll see an interactive Swagger UI where you can explore every endpoint, test requests
directly in the browser, and see request/response schemas.

## 📊 What You Can Test

✅ **Order CRUD** - Create, read, update, delete delivery orders
✅ **Dispatch** - Deterministic CBF-gated dispatch, with an optional full agent council debate
✅ **Fleet State** - Live drones, depots, and the fleet digital twin
✅ **Geofence** - DGCA Red/Yellow/Green zones + altitude bands
✅ **Agent System** - 11 core agents + 5 trigger-based specialists
✅ **Database** - SQLite persistence (check `data/aerofleet.db`)

## 🛑 Stopping the Server

Press `Ctrl+C` in the terminal where uvicorn is running

---

**Your AeroFleet API is ready to test!** 🛰️🚁
