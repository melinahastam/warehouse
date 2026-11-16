"""Verbatim RBAC helper excerpt from Smart Inventory."""

from functools import wraps

from django.contrib.auth.models import Group
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect


ROLE_GROUPS = {
    'system_admin': 'System Admin',
    'inventory_manager': 'Inventory Manager',
    'warehouse_operator': 'Warehouse Operator',
    'inventory_auditor': 'Inventory Auditor',
}
ACCESS_LEVEL_GROUPS = {
    'admin': 'Admin',
    'user': 'User',
}


def _user_in_role(user, role):
    group_name = ROLE_GROUPS.get(role)
    if not group_name:
        return False
    return user.groups.filter(name=group_name).exists()


def ensure_access_groups():
    for group_name in ACCESS_LEVEL_GROUPS.values():
        Group.objects.get_or_create(name=group_name)
    for group_name in ROLE_GROUPS.values():
        Group.objects.get_or_create(name=group_name)


def is_admin_user(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name=ACCESS_LEVEL_GROUPS['admin']).exists()


def get_user_access_level(user):
    if is_admin_user(user):
        return 'admin'
    return 'user'


def assign_access_level(user, access_level):
    ensure_access_groups()
    admin_group = Group.objects.get(name=ACCESS_LEVEL_GROUPS['admin'])
    user_group = Group.objects.get(name=ACCESS_LEVEL_GROUPS['user'])
    user.groups.remove(admin_group, user_group)
    selected_group = admin_group if access_level == 'admin' else user_group
    user.groups.add(selected_group)
    user.is_staff = access_level == 'admin'
    if access_level != 'admin':
        user.is_superuser = False
    user.save(update_fields=['is_staff', 'is_superuser'])


def has_access(user, *, perms=None, roles=None):
    perms = tuple(perms or ())
    roles = tuple(roles or ())
    if not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    if perms and user.has_perms(perms):
        return True
    return any(_user_in_role(user, role) for role in roles)


def access_required(*, perms=None, roles=None, message='شما مجوز انجام این عملیات را ندارید.'):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if has_access(request.user, perms=perms, roles=roles):
                return view_func(request, *args, **kwargs)

            wants_json = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or 'application/json' in (request.headers.get('accept') or '')
                or request.content_type == 'application/json'
            )
            if wants_json:
                return JsonResponse({'status': 'error', 'message': message}, status=403)

            messages.error(request, message)
            return redirect('scanner:dashboard')

        return _wrapped_view

    return decorator


def admin_required(message='این بخش فقط برای مدیران قابل دسترسی است.'):
    return access_required(message=message, roles=())

