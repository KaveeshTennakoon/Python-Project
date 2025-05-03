import re
from flask import jsonify


def validate_email(email):
    """Validate email format"""
    # More strict email validation pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not isinstance(email, str) or re.match(pattern, email) is None:
        return False
    # Check for common invalid patterns
    if '..' in email or email.startswith('.') or email.endswith('.'):
        return False
    return True


def validate_password(password):
    """Password must be at least 8 characters"""
    if len(password) < 8:
        return False
    return True


def validate_amount(amount):
    """Amount must be positive"""
    try:
        amount = float(amount)
        if amount <= 0:
            return False
        return True
    except (ValueError, TypeError):
        return False


def validate_description(description, default="Transaction"):
    """Validate transaction description"""
    if description is None:
        return default, None
    
    if not isinstance(description, str):
        return None, 'Description must be a string'
    
    if len(description) > 200:
        return None, 'Description must be less than 200 characters'
    
    # Use a whitelist approach for characters - allow alphanumeric and common punctuation
    if not re.match(r'^[a-zA-Z0-9\s.,!?()-_]*$', description):
        return None, 'Description contains invalid characters'
    
    return description, None


def error_response(message, status_code=400):
    """Return a standardized error response with multiple formats for compatibility"""
    response = jsonify({
        'error': message,
        'message': message,
        'msg': message,
        'detail': message,
        'error_message': message,
        'status': status_code,
        'code': status_code
    })
    response.status_code = status_code
    return response