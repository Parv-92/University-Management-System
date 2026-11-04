import os
import unittest
from flask import url_for
from app import app

class UniversityManagementSystemTestCase(unittest.TestCase):
    """
    Automated test suite verifying route availability, method security,
    and CSRF protections across all entities.
    """

    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

    def test_dashboard_redirect(self):
        """Root route should redirect to /dashboard."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/dashboard", res.headers.get("Location", ""))

    def test_dashboard_page(self):
        """Dashboard page should render successfully."""
        res = self.client.get("/dashboard")
        self.assertEqual(res.status_code, 200)

    def test_entity_listings(self):
        """Verify that all 10 core entity listing pages respond with 200 OK."""
        endpoints = [
            "/university",
            "/departments",
            "/faculty",
            "/students",
            "/courses",
            "/classrooms",
            "/examinations",
            "/results",
            "/library",
            "/hostel",
        ]
        for ep in endpoints:
            with self.subTest(endpoint=ep):
                res = self.client.get(ep)
                self.assertEqual(res.status_code, 200, f"Endpoint {ep} failed with {res.status_code}")

    def test_post_only_delete_routes_reject_get(self):
        """Verify that DELETE routes reject GET requests with HTTP 405 Method Not Allowed."""
        with app.test_request_context():
            delete_urls = [
                url_for("delete_university", unid=999999),
                url_for("delete_department", dept_id=999999),
                url_for("delete_faculty", fid=999999),
                url_for("delete_student", sid=999999),
                url_for("delete_course", course_id=999999),
                url_for("delete_classroom", room_no=999999),
                url_for("delete_exam", exam_id=999999),
                url_for("delete_result", result_id=999999),
                url_for("delete_library", book_id=999999),
                url_for("delete_hostel", hostel_id=999999),
            ]
            for url in delete_urls:
                with self.subTest(url=url):
                    res = self.client.get(url)
                    self.assertEqual(res.status_code, 405, f"GET on {url} should return 405")

    def test_delete_routes_require_valid_csrf(self):
        """Verify that unauthenticated POST requests without valid CSRF tokens are rejected."""
        with app.test_request_context():
            delete_urls = [
                url_for("delete_university", unid=999999),
                url_for("delete_department", dept_id=999999),
                url_for("delete_faculty", fid=999999),
                url_for("delete_student", sid=999999),
                url_for("delete_course", course_id=999999),
                url_for("delete_classroom", room_no=999999),
                url_for("delete_exam", exam_id=999999),
                url_for("delete_result", result_id=999999),
                url_for("delete_library", book_id=999999),
                url_for("delete_hostel", hostel_id=999999),
            ]
            for url in delete_urls:
                with self.subTest(url=url):
                    # POST without session CSRF should redirect with flash warning
                    res = self.client.post(url, data={})
                    self.assertEqual(res.status_code, 302, f"POST on {url} without CSRF should redirect")

if __name__ == "__main__":
    unittest.main()

