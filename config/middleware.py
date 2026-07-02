from django.conf import settings
from django.http import HttpResponseForbidden


class AdminIPWhitelistMiddleware:
    """
    Middleware to restrict admin panel access to whitelisted IP addresses.
    
    Configure in .env:
    - ADMIN_ENABLED: Set to False to completely disable admin panel
    - ADMIN_IP_WHITELIST: Comma-separated list of allowed IPs (e.g., "192.168.1.1,10.0.0.1")
    
    If ADMIN_IP_WHITELIST is empty, all IPs are allowed (useful for development).
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.whitelist = getattr(settings, 'ADMIN_IP_WHITELIST', [])
        self.admin_enabled = getattr(settings, 'ADMIN_ENABLED', True)
    
    def __call__(self, request):
        # Check if accessing admin panel
        if request.path.startswith('/admin/'):
            # Check if admin is disabled
            if not self.admin_enabled:
                return HttpResponseForbidden('Admin panel is disabled.')
            
            # Check IP whitelist (if configured)
            if self.whitelist:
                client_ip = self.get_client_ip(request)
                if client_ip not in self.whitelist:
                    return HttpResponseForbidden(
                        (
                            "Access denied. Your IP "
                            f"({client_ip}) is not authorized to access the admin panel."
                        )
                    )
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        """Get the client's IP address from the request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP in the chain (client's original IP)
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
