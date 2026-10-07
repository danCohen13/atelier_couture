"""Réinitialisation du mot de passe par code à 6 chiffres envoyé par e-mail."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.shortcuts import render, redirect

from .models import CodeReinitialisation


def demander_code_reset(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            CodeReinitialisation.objects.filter(user=user).delete()
            code = CodeReinitialisation.generer_code()
            CodeReinitialisation.objects.create(user=user, code=code)
            
            send_mail(
                subject='Votre code de réinitialisation - Atelier Couture',
                message=f'Bonjour,\n\nVoici votre code de vérification à 6 chiffres : {code}\n\nCe code est valable pendant 10 minutes.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
            )
            
            request.session['reset_user_id'] = user.id
            return redirect('verifier_code_reset')
        except User.DoesNotExist:
            messages.error(request, "Aucun compte n'est associé à cet email.")

    return render(request, 'atelier/registration/demander_code.html')


def verifier_code_reset(request):
    user_id = request.session.get('reset_user_id')
    if not user_id:
        return redirect('demander_code_reset')

    if request.method == 'POST':
        code_saisi = request.POST.get('code', '').strip()
        code_obj = CodeReinitialisation.objects.filter(user_id=user_id, code=code_saisi).last()

        if code_obj and code_obj.est_valide():
            request.session['code_verifie'] = True
            code_obj.delete()
            return redirect('nouveau_mot_de_passe')
        else:
            messages.error(request, "Code invalide ou expiré (durée de validité : 10 min).")

    return render(request, 'atelier/registration/verifier_code.html')


def nouveau_mot_de_passe(request):
    user_id = request.session.get('reset_user_id')
    code_verifie = request.session.get('code_verifie')

    if not user_id or not code_verifie:
        return redirect('demander_code_reset')

    if request.method == 'POST':
        mdp1 = request.POST.get('password')
        mdp2 = request.POST.get('password_confirm')

        if mdp1 and mdp1 == mdp2:
            user = User.objects.get(id=user_id)
            user.set_password(mdp1)
            user.save()

            del request.session['reset_user_id']
            del request.session['code_verifie']

            messages.success(request, "Votre mot de passe a été modifié avec succès !")
            return redirect('login')
        else:
            messages.error(request, "Les mots de passe ne correspondent pas.")

    return render(request, 'atelier/registration/nouveau_mot_de_passe.html')
