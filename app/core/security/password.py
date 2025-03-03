import random
import bcrypt

from app.core.config import get_settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt(get_settings().security.password_bcrypt_rounds),
    ).decode()

def create_unique_username(email):
    local_part = email.split('@')[0]  # Get the part before the '@'
    random_number = random.randint(1000, 9999)  # Append a random 4-digit number
    username = f"{local_part}_{random_number}"
    return username

DUMMY_PASSWORD = get_password_hash("")
