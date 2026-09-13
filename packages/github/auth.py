import time

import jwt


def generate_app_jwt(private_key: str, app_id: int) -> str:
    """Generate a GitHub App JWT (RS256, 10-minute expiry).

    iat is set 60 seconds in the past to tolerate clock skew.
    exp is 10 minutes (GitHub's maximum).
    iss is the App ID.
    """
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": app_id}
    return jwt.encode(payload, private_key, algorithm="RS256")
