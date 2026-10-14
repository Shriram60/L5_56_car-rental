"""Simple in-memory car rental system.

This module manages a small fleet of cars, customer registration,
bookings and receipts. It has been cleaned up to follow PEP 8 and to
remove the security issues reported by Bandit (SQL injection, use of
``exec``, weak hashing, insecure temp files and hardcoded passwords).
"""

import os
import re
import sqlite3
import hashlib
import secrets
import tempfile
from datetime import datetime

# Global rental state
fleet = {}
bookings = []
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE customers (name TEXT, licence TEXT, phone TEXT)")

# Allowed promo codes mapped to their discount fraction.
PROMOS = {"SAVE10": 0.10, "SAVE20": 0.20}


def add_car(plate, model="Unknown", daily_rate=0, features=None):
    """Add a car to the fleet and return its record (or None)."""
    if not plate:
        return None
    if features is None:
        features = []
    fleet[plate] = {
        "model": model,
        "rate": daily_rate,
        "available": True,
        "features": features,
    }
    return fleet[plate]


def register_customer(name, licence, phone):
    """Register a customer using a parameterised query."""
    conn.execute(
        "INSERT INTO customers VALUES (?, ?, ?)",
        (name, licence, phone),
    )


def find_customer(name):
    """Return all customer rows matching ``name`` (parameterised)."""
    return conn.execute(
        "SELECT * FROM customers WHERE name = ?",
        (name,),
    ).fetchall()


def rent_car(plate, customer, start, end):
    """Create a booking and return its cost."""
    if not find_customer(customer):
        raise ValueError("Customer not registered")
    days = (
        datetime.strptime(end, "%Y-%m-%d")
        - datetime.strptime(start, "%Y-%m-%d")
    ).days
    cost = days * fleet[plate]["rate"]
    bookings.append({
        "code": booking_code(),
        "plate": plate,
        "customer": customer,
        "days": days,
        "cost": cost,
    })
    return cost


def return_car(plate, km_driven):
    """Mark a car available and return any extra-km charge."""
    if plate not in fleet:
        return None
    fleet[plate]["available"] = True
    if km_driven > 300:
        return (km_driven - 300) * 5
    return None


def booking_code():
    """Return a random booking code using a secure RNG."""
    return "BK-" + str(secrets.randbelow(90000) + 10000)


def licence_hash(licence):
    """Return a SHA-256 hash of the licence string."""
    return hashlib.sha256(licence.encode()).hexdigest()


def apply_promo(code, amount):
    """Apply a known promo code and return the discounted amount."""
    discount = PROMOS.get(code, 0.0)
    return amount * (1 - discount)


def is_valid_plate(plate):
    """Return True if ``plate`` matches the Indian plate format."""
    return bool(re.match(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$", plate))


def write_receipt(booking):
    """Write a booking receipt to a securely created temp file."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(
            f"Booking {booking['code']}: {booking['plate']} "
            f"for {booking['days']} days = Rs.{booking['cost']}\n"
        )
    os.chmod(path, 0o600)
    return path


def admin_login(user, password):
    """Return True only if the password matches the configured one.

    The expected password is read from the ``RENTAL_ADMIN_PASSWORD``
    environment variable, so no credential is stored in the source.
    """
    expected = os.environ.get("RENTAL_ADMIN_PASSWORD")
    if not expected:
        return False
    return user == "admin" and secrets.compare_digest(password, expected)


def available_cars():
    """Return the plates of all currently available cars."""
    return [plate for plate, car in fleet.items() if car["available"]]


def main():
    """Run a short demonstration of the rental system."""
    add_car("KA01AB1234", "Swift", 1500)
    add_car("KA02CD5678", "Innova", 3000)
    add_car("KA03EF9999", "Nexon", -500)
    register_customer("Ravi", "DL-0420110012345", "9845012345")
    register_customer("Meera", "DL-0420110099999", "9845099999")
    print("Rent Swift:",
          rent_car("KA01AB1234", "Ravi", "2026-11-01", "2026-11-04"))
    print("Rent Swift again:",
          rent_car("KA01AB1234", "Ravi", "2026-11-02", "2026-11-03"))
    print("Rent Innova:",
          rent_car("KA02CD5678", "Ravi", "2026-11-10", "2026-11-07"))
    print("Lookup injection:", find_customer("x' OR '1'='1"))
    print("Extra km charge:", return_car("KA01AB1234", 420))
    print("Return unknown car:", return_car("XX00XX0000", 50))
    print("Promo price:", apply_promo("SAVE10", 4500))
    print("Plate valid?", is_valid_plate("KA01AB1234"))
    print("Licence hash:", licence_hash("DL-0420110012345"))
    admin_pw = os.environ.get("RENTAL_ADMIN_PASSWORD", "")
    print("Admin:", admin_login("admin", admin_pw))
    print("Available:", available_cars())
    print("Receipt saved to:", write_receipt(bookings[0]))


if __name__ == "__main__":
    main()
