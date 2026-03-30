"""
Umuve Backend E2E API Tests

Covers the core API surface:
  1. Health check
  2. Price estimation
  3. Auth flow (signup + login)
  4. Protected endpoints require auth
  5. Service area check
  6. Promo code validation
"""

import pytest


# ============================================================================
# 1. Health Check
# ============================================================================

class TestHealthCheck:
    """GET /api/health -- public, no auth required."""

    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_body_shape(self, client):
        data = client.get("/api/health").get_json()
        assert data["status"] == "healthy"
        assert "service" in data
        assert "version" in data


# ============================================================================
# 2. Price Estimation
# ============================================================================

class TestPriceEstimation:
    """POST /api/bookings/estimate -- public, no auth required."""

    def test_estimate_basic_furniture(self, client):
        payload = {
            "itemCategory": "furniture",
            "quantity": 1,
        }
        resp = client.post("/api/bookings/estimate", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        est = data["estimate"]
        assert "total" in est
        assert "subtotal" in est
        assert "serviceFee" in est
        assert "estimatedDuration" in est
        assert est["total"] > 0

    def test_estimate_with_items_array(self, client):
        """Test the v2 format with an items array."""
        payload = {
            "items": [
                {"category": "appliances", "quantity": 2, "size": "large"},
            ],
        }
        resp = client.post("/api/bookings/estimate", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        est = data["estimate"]
        assert est["total"] > 0
        # v2 detailed breakdown should be present
        assert "items" in est
        assert "items_subtotal" in est

    def test_estimate_multiple_items(self, client):
        """Test estimate with multiple item categories."""
        payload = {
            "items": [
                {"category": "furniture", "quantity": 2},
                {"category": "electronics", "quantity": 1},
            ],
        }
        resp = client.post("/api/bookings/estimate", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        est = data["estimate"]
        # Multiple items should cost more than a single item
        assert est["total"] > 0
        assert est["items_subtotal"] > 0

    def test_estimate_empty_body(self, client):
        """An empty body should still return a valid estimate using defaults."""
        resp = client.post("/api/bookings/estimate", json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_estimate_contains_truck_size(self, client):
        """Estimate should include a truck size recommendation."""
        payload = {"itemCategory": "furniture", "quantity": 3}
        resp = client.post("/api/bookings/estimate", json=payload)
        data = resp.get_json()
        est = data["estimate"]
        assert "truckSize" in est


# ============================================================================
# 3. Auth Flow -- Signup and Login
# ============================================================================

class TestAuthSignup:
    """POST /api/auth/signup"""

    def test_signup_success(self, client):
        payload = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "name": "New User",
        }
        resp = client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "token" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["name"] == "New User"

    def test_signup_missing_email(self, client):
        payload = {"password": "SecurePass123!"}
        resp = client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 400

    def test_signup_missing_password(self, client):
        payload = {"email": "user@example.com"}
        resp = client.post("/api/auth/signup", json=payload)
        assert resp.status_code == 400

    def test_signup_duplicate_email(self, client):
        payload = {
            "email": "dup@example.com",
            "password": "SecurePass123!",
            "name": "First",
        }
        # First signup succeeds
        resp1 = client.post("/api/auth/signup", json=payload)
        assert resp1.status_code == 200
        # Second signup with same email fails
        resp2 = client.post("/api/auth/signup", json=payload)
        assert resp2.status_code == 409

    def test_signup_returns_referral_code(self, client):
        payload = {
            "email": "refuser@example.com",
            "password": "SecurePass123!",
            "name": "Referral Test User",
        }
        resp = client.post("/api/auth/signup", json=payload)
        data = resp.get_json()
        assert data["success"] is True
        # Every new user should get a referral code
        assert data["user"].get("referral_code") is not None
        assert len(data["user"]["referral_code"]) == 8


class TestAuthLogin:
    """POST /api/auth/login"""

    def test_login_success(self, client):
        # First, create a user
        client.post("/api/auth/signup", json={
            "email": "login@example.com",
            "password": "MyPassword1!",
            "name": "Login Tester",
        })
        # Now login
        resp = client.post("/api/auth/login", json={
            "email": "login@example.com",
            "password": "MyPassword1!",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "token" in data
        assert data["user"]["email"] == "login@example.com"

    def test_login_wrong_password(self, client):
        client.post("/api/auth/signup", json={
            "email": "wrongpw@example.com",
            "password": "CorrectPassword1!",
            "name": "Wrong PW Tester",
        })
        resp = client.post("/api/auth/login", json={
            "email": "wrongpw@example.com",
            "password": "WrongPassword!",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_email(self, client):
        resp = client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "Whatever123!",
        })
        assert resp.status_code == 401

    def test_login_missing_fields(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400


class TestAuthMe:
    """GET /api/auth/me -- requires auth."""

    def test_get_me_authenticated(self, client, auth_headers):
        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["user"]["email"] == "testuser@example.com"

    def test_get_me_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


# ============================================================================
# 4. Protected Endpoints Require Auth
# ============================================================================

class TestProtectedEndpoints:
    """Endpoints guarded by @require_auth should return 401 without a token."""

    def test_jobs_list_requires_auth(self, client):
        """GET /api/jobs should return 401 without a bearer token."""
        resp = client.get("/api/jobs")
        assert resp.status_code == 401

    def test_jobs_list_with_invalid_token(self, client):
        resp = client.get(
            "/api/jobs",
            headers={"Authorization": "Bearer invalid-garbage-token"},
        )
        assert resp.status_code == 401

    def test_customer_bookings_requires_auth(self, client):
        """POST /api/bookings/customer should return 401 without auth."""
        resp = client.post("/api/bookings/customer", json={})
        assert resp.status_code == 401

    def test_booking_photos_requires_auth(self, client):
        """POST /api/bookings/upload-photos should return 401 without auth."""
        resp = client.post("/api/bookings/upload-photos")
        assert resp.status_code == 401


# ============================================================================
# 5. Service Area Check
# ============================================================================

class TestServiceArea:
    """POST /api/service-area/check -- public."""

    def test_inside_service_area(self, client):
        """Miami Beach coordinates should be inside the service area."""
        payload = {"lat": 25.7907, "lng": -80.1300}
        resp = client.post("/api/service-area/check", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["in_service_area"] is True
        assert "nearest_boundary_km" in data

    def test_outside_service_area(self, client):
        """New York coordinates should be outside the service area."""
        payload = {"lat": 40.7128, "lng": -74.0060}
        resp = client.post("/api/service-area/check", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["in_service_area"] is False

    def test_missing_coordinates(self, client):
        """Missing lat/lng should return 400."""
        resp = client.post("/api/service-area/check", json={})
        assert resp.status_code == 400

    def test_address_only_not_supported(self, client):
        """Sending only an address (no lat/lng) returns 400 with guidance."""
        payload = {"address": "123 Ocean Drive, Miami Beach, FL"}
        resp = client.post("/api/service-area/check", json=payload)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "geocode" in data.get("error", "").lower() or "lat" in data.get("error", "").lower()

    def test_invalid_coordinates(self, client):
        """Non-numeric coordinates should return 400."""
        payload = {"lat": "not-a-number", "lng": "also-bad"}
        resp = client.post("/api/service-area/check", json=payload)
        assert resp.status_code == 400

    def test_service_area_info_endpoint(self, client):
        """GET /api/service-area should return polygon info for map display."""
        resp = client.get("/api/service-area")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "service_area" in data


# ============================================================================
# 6. Promo Code Validation
# ============================================================================

class TestPromoCodeValidation:
    """POST /api/promos/validate -- public."""

    def _create_promo(self, db_session, code="SAVE20", discount_type="percentage",
                      discount_value=20.0, is_active=True, min_order_amount=0.0,
                      max_uses=None, expires_at=None):
        """Helper to insert a promo code directly into the database."""
        from models import PromoCode, generate_uuid, utcnow
        promo = PromoCode(
            id=generate_uuid(),
            code=code.upper(),
            discount_type=discount_type,
            discount_value=discount_value,
            is_active=is_active,
            min_order_amount=min_order_amount,
            max_uses=max_uses,
            use_count=0,
            expires_at=expires_at,
        )
        db_session.add(promo)
        db_session.commit()
        return promo

    def test_validate_valid_percentage_code(self, client, db_session):
        self._create_promo(db_session, code="SAVE20", discount_type="percentage",
                           discount_value=20.0)
        resp = client.post("/api/promos/validate", json={
            "code": "SAVE20",
            "order_amount": 100.0,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True
        assert data["discount_amount"] == 20.0
        assert data["new_total"] == 80.0

    def test_validate_valid_fixed_code(self, client, db_session):
        self._create_promo(db_session, code="FLAT10", discount_type="fixed",
                           discount_value=10.0)
        resp = client.post("/api/promos/validate", json={
            "code": "FLAT10",
            "order_amount": 100.0,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True
        assert data["discount_amount"] == 10.0
        assert data["new_total"] == 90.0

    def test_validate_nonexistent_code(self, client, db_session):
        resp = client.post("/api/promos/validate", json={
            "code": "DOESNOTEXIST",
            "order_amount": 50.0,
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["valid"] is False

    def test_validate_inactive_code(self, client, db_session):
        self._create_promo(db_session, code="INACTIVE", is_active=False)
        resp = client.post("/api/promos/validate", json={
            "code": "INACTIVE",
            "order_amount": 100.0,
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["valid"] is False

    def test_validate_expired_code(self, client, db_session):
        from datetime import datetime, timezone, timedelta
        expired = datetime.now(timezone.utc) - timedelta(days=1)
        self._create_promo(db_session, code="EXPIRED", expires_at=expired)
        resp = client.post("/api/promos/validate", json={
            "code": "EXPIRED",
            "order_amount": 100.0,
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["valid"] is False

    def test_validate_below_minimum_order(self, client, db_session):
        self._create_promo(db_session, code="MIN50", min_order_amount=50.0)
        resp = client.post("/api/promos/validate", json={
            "code": "MIN50",
            "order_amount": 30.0,
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["valid"] is False

    def test_validate_max_uses_reached(self, client, db_session):
        promo = self._create_promo(db_session, code="ONCE", max_uses=1)
        promo.use_count = 1
        db_session.commit()
        resp = client.post("/api/promos/validate", json={
            "code": "ONCE",
            "order_amount": 100.0,
        })
        assert resp.status_code == 400
        data = resp.get_json()
        assert data["valid"] is False

    def test_validate_missing_code(self, client, db_session):
        resp = client.post("/api/promos/validate", json={
            "order_amount": 100.0,
        })
        assert resp.status_code == 400

    def test_validate_case_insensitive(self, client, db_session):
        """Promo codes should be matched case-insensitively."""
        self._create_promo(db_session, code="MIXCASE", discount_type="fixed",
                           discount_value=5.0)
        resp = client.post("/api/promos/validate", json={
            "code": "mixcase",
            "order_amount": 100.0,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["valid"] is True


# ============================================================================
# 7. Security Headers
# ============================================================================

class TestSecurityHeaders:
    """Verify that security headers are present on all responses."""

    def test_security_headers_present(self, client):
        resp = client.get("/api/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "strict-origin" in resp.headers.get("Referrer-Policy", "").lower()

    def test_csp_header_present(self, client):
        resp = client.get("/api/health")
        assert "Content-Security-Policy" in resp.headers


# ============================================================================
# 8. Address Validation (stub)
# ============================================================================

class TestAddressValidation:
    """POST /api/bookings/validate-address -- public."""

    def test_validate_address_success(self, client):
        payload = {"address": "123 Ocean Drive, Miami Beach, FL 33139"}
        resp = client.post("/api/bookings/validate-address", json=payload)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "address" in data
        assert data["address"]["formatted"] == payload["address"]

    def test_validate_address_empty(self, client):
        resp = client.post("/api/bookings/validate-address", json={"address": ""})
        assert resp.status_code == 400


# ============================================================================
# 9. Available Time Slots
# ============================================================================

class TestAvailableSlots:
    """GET /api/bookings/available-slots -- public."""

    def test_get_available_slots(self, client):
        resp = client.get("/api/bookings/available-slots?date=2026-04-01")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert isinstance(data["slots"], list)
        assert len(data["slots"]) > 0
        # Each slot should have date, time, and available fields
        slot = data["slots"][0]
        assert "date" in slot
        assert "time" in slot
        assert "available" in slot
