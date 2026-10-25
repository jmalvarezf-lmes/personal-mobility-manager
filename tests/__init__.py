"""Shared test constants."""

# A 32-byte (256-bit) secret for HS256 JWT signing in tests. Using a secret
# below PyJWT's recommended length floods the test output with
# InsecureKeyLengthWarning and does not model production key generation.
JWT_SECRET = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
