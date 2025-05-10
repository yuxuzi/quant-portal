import os

# Kerberos Configuration
KRB5_KTNAME = '/etc/krb5.keytab'  # Path to Kerberos keytab

# Flask Configuration
SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# AD/LDAP Configuration
LDAP_SERVER = 'ldap://your-ad-server.domain.com'
LDAP_SEARCH_BASE = 'OU=Users,DC=domain,DC=com'