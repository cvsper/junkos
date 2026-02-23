#!/bin/bash
# Create 10 test jobs via the booking API
# These will show up as available jobs for drivers to accept

API_URL="https://junkos-backend.onrender.com/api/booking"

# Color output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Creating 10 test jobs...${NC}\n"

# Job 1: Miami Beach - Couch
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Ocean Drive, Miami Beach, FL 33139",
    "lat": 25.7907,
    "lng": -80.1300,
    "items": [{"category": "furniture", "size": "medium", "quantity": 1}],
    "estimated_price": 85.0,
    "scheduled_date": "'$(date -v+1d +%Y-%m-%d)'",
    "scheduled_time": "10:00",
    "customerEmail": "test@umuve.com",
    "customerName": "Test Customer",
    "customerPhone": "+15555551234",
    "notes": "Please call when arriving. Couch is on the second floor."
  }' | jq -r '.job.id' && echo -e "${GREEN}✓ Job 1 created${NC}"

sleep 1

# Job 2: Fort Lauderdale - Mattress & Box Spring
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "456 Palm Ave, Fort Lauderdale, FL 33301",
    "lat": 26.1224,
    "lng": -80.1373,
    "items": [{"category": "mattress", "quantity": 2}],
    "estimated_price": 105.0,
    "scheduled_date": "'$(date -v+1d +%Y-%m-%d)'",
    "scheduled_time": "11:00",
    "customerEmail": "test@umuve.com",
    "customerName": "Test Customer",
    "customerPhone": "+15555551234",
    "notes": "Gate code is 1234. Items in garage."
  }' | jq -r '.job.id' && echo -e "${GREEN}✓ Job 2 created${NC}"

sleep 1

# Job 3: Boca Raton - Refrigerator
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "789 Glades Road, Boca Raton, FL 33431",
    "lat": 26.3683,
    "lng": -80.1289,
    "items": [{"category": "appliances", "size": "large", "quantity": 1}],
    "estimated_price": 120.0,
    "scheduled_date": "'$(date -v+2d +%Y-%m-%d)'",
    "scheduled_time": "09:00",
    "customerEmail": "test@umuve.com",
    "customerName": "Test Customer",
    "customerPhone": "+15555551234",
    "notes": "Heavy item - may need extra help."
  }' | jq -r '.job.id' && echo -e "${GREEN}✓ Job 3 created${NC}"

sleep 1

# Job 4: Pompano Beach - TV & Microwave
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "321 Atlantic Blvd, Pompano Beach, FL 33062",
    "lat": 26.2379,
    "lng": -80.1248,
    "items": [
      {"category": "electronics", "size": "medium", "quantity": 1},
      {"category": "electronics", "size": "small", "quantity": 1}
    ],
    "estimated_price": 80.0,
    "scheduled_date": "'$(date -v+2d +%Y-%m-%d)'",
    "scheduled_time": "14:00",
    "customerEmail": "test@umuve.com",
    "customerName": "Test Customer",
    "customerPhone": "+15555551234",
    "notes": "Electronics - please handle with care."
  }' | jq -r '.job.id' && echo -e "${GREEN}✓ Job 4 created${NC}"

sleep 1

# Job 5: Deerfield Beach - Washing Machine
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "567 Hillsboro Blvd, Deerfield Beach, FL 33441",
    "lat": 26.3184,
    "lng": -80.0998,
    "items": [{"category": "appliances", "size": "medium", "quantity": 1}],
    "estimated_price": 115.0,
    "scheduled_date": "'$(date -v+3d +%Y-%m-%d)'",
    "scheduled_time": "10:00",
    "customerEmail": "test@umuve.com",
    "customerName": "Test Customer",
    "customerPhone": "+15555551234",
    "notes": "Disconnected and ready to go."
  }' | jq -r '.job.id' && echo -e "${GREEN}✓ Job 5 created${NC}"

sleep 1

# Job 6: Hollywood - Desk
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "890 Hollywood Blvd, Hollywood, FL 33020",
    "lat": 26.0112,
    "lng": -80.1495,
    "items": [{"category": "furniture", "size": "medium", "quantity": 1}],
    "estimated_price": 90.0,
    "scheduled_date": "'$(date -v+3d +%Y-%m-%d)'",
    "scheduled_time": "13:00",
    "customerEmail": "test@umuve.com",
    "customerName": "Test Customer",
    "customerPhone": "+15555551234",
    "notes": "Office furniture - wooden desk with drawers."
  }' | jq -r '.job.id' && echo -e "${GREEN}✓ Job 6 created${NC}"

sleep 1

# Job 7: Coral Gables - Dining Set
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "234 Coral Way, Coral Gables, FL 33134",
    "lat": 25.7481,
    "lng": -80.2620,
    "items": [
      {"category": "furniture", "size": "large", "quantity": 1},
      {"category": "furniture", "size": "small", "quantity": 4}
    ],
    "estimated_price": 125.0,
    "scheduled_date": "'$(date -v+4d +%Y-%m-%d)'",
    "scheduled_time": "11:00",
    "customerEmail": "test@umuve.com",
    "customerName": "Test Customer",
    "customerPhone": "+15555551234",
    "notes": "Full dining set - table plus 4 chairs."
  }' | jq -r '.job.id' && echo -e "${GREEN}✓ Job 7 created${NC}"

sleep 1

# Job 8: West Palm Beach - Grill
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "678 Marina Drive, West Palm Beach, FL 33401",
    "lat": 26.7153,
    "lng": -80.0534,
    "items": [{"category": "general", "quantity": 1}],
    "estimated_price": 70.0,
    "scheduled_date": "'$(date -v+4d +%Y-%m-%d)'",
    "scheduled_time": "15:00",
    "customerEmail": "test@umuve.com",
    "customerName": "Test Customer",
    "customerPhone": "+15555551234",
    "notes": "Outdoor grill, needs cleaning but functional."
  }' | jq -r '.job.id' && echo -e "${GREEN}✓ Job 8 created${NC}"

sleep 1

# Job 9: Pembroke Pines - Bookshelf
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "135 Pines Blvd, Pembroke Pines, FL 33027",
    "lat": 26.0073,
    "lng": -80.2962,
    "items": [
      {"category": "furniture", "size": "medium", "quantity": 1},
      {"category": "general", "quantity": 3}
    ],
    "estimated_price": 110.0,
    "scheduled_date": "'$(date -v+5d +%Y-%m-%d)'",
    "scheduled_time": "10:00",
    "customerEmail": "test@umuve.com",
    "customerName": "Test Customer",
    "customerPhone": "+15555551234",
    "notes": "Heavy books - may need dolly."
  }' | jq -r '.job.id' && echo -e "${GREEN}✓ Job 9 created${NC}"

sleep 1

# Job 10: Aventura - Treadmill
curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "999 Biscayne Blvd, Aventura, FL 33180",
    "lat": 25.9564,
    "lng": -80.1393,
    "items": [{"category": "appliances", "size": "large", "quantity": 1}],
    "estimated_price": 130.0,
    "scheduled_date": "'$(date -v+5d +%Y-%m-%d)'",
    "scheduled_time": "14:00",
    "customerEmail": "test@umuve.com",
    "customerName": "Test Customer",
    "customerPhone": "+15555551234",
    "notes": "Exercise equipment - large and heavy."
  }' | jq -r '.job.id' && echo -e "${GREEN}✓ Job 10 created${NC}"

echo -e "\n${GREEN}✅ Successfully created 10 test jobs!${NC}"
echo -e "${BLUE}These jobs are now visible to drivers in the Umuve Pro app.${NC}"
