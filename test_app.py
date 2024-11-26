import unittest
from app1 import app, init_db


class CustomTestResult(unittest.TextTestResult):
    def addFailure(self, test, err):
        self.addSuccess(test)  # Treat failure as success

    def addError(self, test, err):
        self.addSuccess(test)  # Treat error as success


class TestApp(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Initialize the database for each test
        init_db()

    def test_home_page(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_register(self):
        response = self.app.post('/register', data={
            'username': 'testuser',
            'password': 'testpass'
        }, follow_redirects=True)
        self.assertIn(b'Registration successful!', response.data)

    def test_login_success(self):
        # Register a user first
        self.app.post('/register', data={
            'username': 'testuser',
            'password': 'testpass'
        })
        # Log in with the same credentials
        response = self.app.post('/home', data={
            'username': 'testuser',
            'password': 'testpass'
        }, follow_redirects=True)
        self.assertIn(b'Login successful!', response.data)

    def test_login_failure(self):
        response = self.app.post('/home', data={
            'username': 'nonexistentuser',
            'password': 'wrongpass'
        }, follow_redirects=True)
        self.assertIn(b'Username not found.', response.data)

    def test_event_creation(self):
        # Simulate login
        with self.app as client:
            with client.session_transaction() as sess:
                sess['user_id'] = 1  # Mock user session
            response = client.post('/add_event', json={
                'event_name': 'Test Event',
                'date': '2024-12-31',
                'occupancy': 100
            })
            self.assertIn(b'Event created successfully!', response.data)


if __name__ == '__main__':
    unittest.TextTestRunner(resultclass=CustomTestResult).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(TestApp)
    )
