from flask import g, request, redirect, url_for
from flask_login import current_user, login_user
from werkzeug.exceptions import Unauthorized
from app.models import User

def authenticate():
    if current_user.is_authenticated:
        return
    
    # Try Windows Integrated Authentication
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Negotiate '):
        try:
            # Verify Kerberos ticket
            result = g.kerberos_auth_client.authenticate()
            user = User.get_by_username(result.username)
            login_user(user)
            return
        except Exception as e:
            app.logger.error(f"Kerberos auth failed: {str(e)}")
    
    # Fallback to form-based auth
    return redirect(url_for('login'))