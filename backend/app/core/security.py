from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings
from typing import Optional
import logging
import bcrypt

# Configure password context with bcrypt for verification
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Bcrypt has a hard limit of 72 bytes for passwords
BCRYPT_MAX_BYTES = 72

# Suppress passlib initialization warnings
logging.getLogger("passlib").setLevel(logging.ERROR)


def _truncate_password(password: str) -> str:
    """Truncate password to 72 bytes to comply with bcrypt limit.
    
    This function safely truncates a password to 72 bytes while preserving
    UTF-8 encoding. It handles multi-byte characters correctly.
    """
    if not password:
        return password
    
    # Encode to bytes and truncate to 72 bytes
    password_bytes = password.encode('utf-8')[:BCRYPT_MAX_BYTES]
    
    # Decode back to string, handling any incomplete UTF-8 sequences
    # Use 'ignore' to skip any incomplete bytes at the end
    password_truncated = password_bytes.decode('utf-8', errors='ignore')
    
    return password_truncated


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    # Truncate plain password to 72 bytes before verification
    plain_password_truncated = _truncate_password(plain_password)
    return pwd_context.verify(plain_password_truncated, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt directly.
    
    Note: Passwords longer than 72 bytes will be truncated.
    Uses bcrypt library directly to avoid passlib initialization issues.
    """
    # Truncate password to 72 bytes before hashing
    password_truncated = _truncate_password(password)
    
    # Use bcrypt directly to avoid passlib initialization issues
    # Convert to bytes for bcrypt
    password_bytes = password_truncated.encode('utf-8')
    
    # Ensure we're definitely under 72 bytes
    if len(password_bytes) > BCRYPT_MAX_BYTES:
        password_bytes = password_bytes[:BCRYPT_MAX_BYTES]
    
    # Generate salt and hash using bcrypt directly
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Return as string (bcrypt hash format)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
