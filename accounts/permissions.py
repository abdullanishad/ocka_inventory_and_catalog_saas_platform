# accounts/permissions.py
from django.core.exceptions import PermissionDenied

def role_required(*roles):
    def wrapper(view_func):
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())
            if request.user.role not in roles:
                raise PermissionDenied("You don't have access to this area.")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return wrapper
