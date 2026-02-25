"""
Module 13 - API Error Handling Integration Tests
Tests error handling in API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.database import Base, get_db

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_module13.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestAuthValidation:
    def test_signup_invalid_email(self):
        response = client.post("/auth/signup", json={
            "email": "invalid-email",
            "password": "password123",
            "role": "recruiter",
            "name": "Test User"
        })
        assert response.status_code == 400
        data = response.json()
        assert "email" in data.get("error", "").lower() or "email" in data.get("detail", "").lower()
    
    def test_signup_weak_password(self):
        response = client.post("/auth/signup", json={
            "email": "test@example.com",
            "password": "123",
            "role": "recruiter",
            "name": "Test User"
        })
        assert response.status_code == 400
        data = response.json()
        assert "password" in data.get("error", "").lower() or "password" in data.get("detail", "").lower()
    
    def test_signup_invalid_role(self):
        response = client.post("/auth/signup", json={
            "email": "test@example.com",
            "password": "password123",
            "role": "invalid_role",
            "name": "Test User"
        })
        assert response.status_code == 400
        data = response.json()
        assert "role" in data.get("error", "").lower() or "role" in data.get("detail", "").lower()
    
    def test_signup_duplicate_email(self):
        # First signup
        client.post("/auth/signup", json={
            "email": "duplicate@example.com",
            "password": "password123",
            "role": "recruiter",
            "name": "Test User"
        })
        
        # Duplicate signup
        response = client.post("/auth/signup", json={
            "email": "duplicate@example.com",
            "password": "password123",
            "role": "recruiter",
            "name": "Test User 2"
        })
        assert response.status_code == 400
        data = response.json()
        assert "exists" in data.get("error", "").lower() or "exists" in data.get("detail", "").lower()
    
    def test_login_invalid_credentials(self):
        response = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        data = response.json()
        assert "credential" in data.get("error", "").lower() or "credential" in data.get("detail", "").lower()


class TestJobValidation:
    def setup_method(self):
        # Create a test recruiter
        response = client.post("/auth/signup", json={
            "email": "recruiter@example.com",
            "password": "password123",
            "role": "recruiter",
            "name": "Test Recruiter"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_create_job_missing_title(self):
        response = client.post("/jobs", headers=self.headers, json={
            "description": "Test description",
            "status": "active"
        })
        assert response.status_code == 400
    
    def test_create_job_title_too_short(self):
        response = client.post("/jobs", headers=self.headers, json={
            "title": "A",
            "description": "Test description that is long enough",
            "status": "active"
        })
        assert response.status_code == 400
    
    def test_create_job_description_too_short(self):
        response = client.post("/jobs", headers=self.headers, json={
            "title": "Valid Title",
            "description": "Short",
            "status": "active"
        })
        assert response.status_code == 400
    
    def test_create_job_invalid_status(self):
        response = client.post("/jobs", headers=self.headers, json={
            "title": "Valid Title",
            "description": "Valid description that is long enough for the requirements",
            "status": "invalid_status"
        })
        assert response.status_code == 400
    
    def test_get_nonexistent_job(self):
        response = client.get("/jobs/99999", headers=self.headers)
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data.get("error", "").lower() or "not found" in data.get("detail", "").lower()


class TestUnauthorizedAccess:
    def test_jobs_without_token(self):
        response = client.post("/jobs", json={
            "title": "Test Job",
            "description": "Test description"
        })
        assert response.status_code in [401, 403]
    
    def test_resumes_without_token(self):
        response = client.get("/resumes/mine")
        assert response.status_code in [401, 403]
    
    def test_interviews_without_token(self):
        response = client.get("/interviews/mine")
        assert response.status_code in [401, 403]


class TestErrorResponseFormat:
    def test_error_has_success_false(self):
        response = client.post("/auth/login", json={
            "email": "bad@example.com",
            "password": "wrong"
        })
        data = response.json()
        # Check for success field (our format) or just detail (FastAPI default)
        if "success" in data:
            assert data["success"] is False
    
    def test_error_has_message(self):
        response = client.post("/auth/signup", json={
            "email": "invalid",
            "password": "123456",
            "role": "recruiter"
        })
        data = response.json()
        # Should have error, detail, or message field
        assert "error" in data or "detail" in data or "message" in data


class TestFileUploadValidation:
    def setup_method(self):
        # Create a test candidate
        response = client.post("/auth/signup", json={
            "email": "candidate@example.com",
            "password": "password123",
            "role": "candidate",
            "name": "Test Candidate"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_upload_without_file(self):
        response = client.post("/resumes/upload", headers=self.headers)
        assert response.status_code in [400, 422]
    
    def test_upload_invalid_extension(self):
        files = {"file": ("test.txt", b"fake content", "text/plain")}
        response = client.post("/resumes/upload", headers=self.headers, files=files)
        assert response.status_code == 400
        data = response.json()
        error_text = (data.get("error", "") + data.get("detail", "")).lower()
        assert "pdf" in error_text or "docx" in error_text or "type" in error_text


class TestHealthCheck:
    def test_health_endpoint(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestErrorLogging:
    """Verify errors don't crash the application"""
    
    def test_malformed_json(self):
        response = client.post(
            "/auth/signup",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        # Should return 422 for malformed JSON, not 500
        assert response.status_code in [400, 422]
    
    def test_missing_required_field(self):
        response = client.post("/auth/signup", json={
            "email": "test@example.com"
            # Missing password and role
        })
        assert response.status_code in [400, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
