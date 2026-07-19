from slowapi import Limiter
from slowapi.util import get_remote_address

# headers_enabled=True makes slowapi write Retry-After/X-RateLimit-* headers
# on every rate-limited response. To do that on a 2xx response it needs a
# starlette Response object to mutate — if the decorated handler's return
# value isn't already one (e.g. it returns a Pydantic model), the handler
# MUST declare a `response: Response` parameter for FastAPI to inject, or
# slowapi raises instead of just skipping the headers. See the `response:
# Response` parameters on update_vehicle/register_vehicle (routers/vehicles.py)
# and get_ser_zone (routers/parking.py) — they look unused but are load-bearing.
limiter = Limiter(key_func=get_remote_address, headers_enabled=True)
