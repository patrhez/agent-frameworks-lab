"""Only these mock tools are exposed; execution isolation belongs to the harness."""
RISK = {"get_weather": "low", "book_flight": "high"}


def validate_city(city: str) -> str:
    if not isinstance(city, str) or not 1 <= len(city.strip()) <= 100:
        raise ValueError("City must contain 1-100 characters")
    return city.strip()


def get_weather(city: str) -> str:
    return f"{validate_city(city)}: sunny, 22 C (mock data)."


def book_flight(city: str, operation_id: str) -> str:
    """Return the mock booking receipt; caller records the side effect atomically."""
    return f"MOCK booking to {validate_city(city)}; operation_id={operation_id}"
