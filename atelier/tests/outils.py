"""Aides communes aux tests : un atelier de test et des utilisateurs qui lui sont rattachés."""
from django.contrib.auth.models import User

from atelier.models import Adhesion, Atelier


def atelier_test(nom='Atelier test'):
    """L'atelier par défaut des tests (créé une fois par test, la base est rétablie entre deux tests)."""
    return Atelier.objects.get_or_create(nom=nom)[0]


def utilisateur_test(*args, atelier=None, **kwargs):
    """Comme `User.objects.create_user`, mais rattaché à un atelier (celui des tests par défaut)."""
    user = User.objects.create_user(*args, **kwargs)
    Adhesion.objects.create(user=user, atelier=atelier or atelier_test())
    return user
