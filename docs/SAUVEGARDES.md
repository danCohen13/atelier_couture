# Sauvegardes

Deux filets de sécurité, complémentaires :

| Filet | Protège contre | Où |
|---|---|---|
| **Retour dans le temps Neon** (point-in-time restore) | une erreur récente (suppression par erreur, mauvaise migration) | console Neon → *Branches* → *Restore* ; la fenêtre dépend de ton offre (quelques heures à quelques jours) |
| **Sauvegarde chiffrée quotidienne** (ce document) | la perte du compte Neon, une panne longue, une erreur découverte tard | un bucket S3 (Cloudflare R2, Backblaze B2…) **chez un autre fournisseur que Neon** |

Les photos ne sont pas dans la base : elles restent chez Cloudinary (la base ne garde que leurs adresses).

## Mise en place (une seule fois, ~20 minutes)

1. **Créer un bucket** privé chez Cloudflare R2 ou Backblaze B2 (l'offre gratuite suffit largement) et une clé d'accès limitée à ce bucket.
2. **Générer la clé de chiffrement** :
   ```
   python manage.py sauvegarde --generer-cle
   ```
   **Copie cette clé dans ton gestionnaire de mots de passe.** Sans elle, les sauvegardes sont illisibles ; la perdre = perdre les sauvegardes.
3. **Variables d'environnement** (Render → service web, puis le même jeu sur la tâche planifiée) :
   `BACKUP_ENCRYPTION_KEY`, `BACKUP_S3_BUCKET`, `BACKUP_S3_ENDPOINT`, `BACKUP_S3_ACCESS_KEY`, `BACKUP_S3_SECRET_KEY`
   (et `BACKUP_S3_REGION`, `BACKUP_PREFIX` si ton fournisseur l'exige).
4. **Tâche planifiée Render** (*New → Cron Job*, même dépôt, mêmes variables) :
   - commande : `python manage.py sauvegarde`
   - horaire : `0 1 * * *` (chaque nuit, en UTC)
5. **Surveillance** : une 2ᵉ tâche planifiée `python manage.py verifier_sauvegarde` (à 8 h) échoue — et Render t'envoie un e-mail — si la dernière sauvegarde a plus de 36 h, est illisible ou vide.

Conservation automatique : toutes les sauvegardes des 14 derniers jours, puis la première de chacun des 12 derniers mois.

## Exercice de restauration (à faire une fois, puis chaque trimestre)

Une sauvegarde jamais restaurée n'est pas une sauvegarde.

1. Crée une base **vide** (une nouvelle branche Neon, ou un fichier SQLite en local) et pointe `DATABASE_URL` dessus.
2. `python manage.py migrate`
3. `python manage.py restaurer_sauvegarde --confirmer` (ou `--fichier atelier-AAAAMMJJ-HHMMSS.json.gz.enc`)
4. Lance le site avec cette base et vérifie une cliente, une location, les finances.

La commande refuse de restaurer dans une base qui contient déjà des comptes : elle ne peut pas écraser des données vivantes.

## Catastrophe : que faire ?

1. Erreur récente → d'abord le *Restore* de Neon (le plus rapide).
2. Sinon → nouvelle base Neon, `migrate`, `restaurer_sauvegarde --confirmer`, puis changer `DATABASE_URL` sur Render.
3. Noter l'incident dans le registre (voir PROTECTION_DES_DONNEES.md) s'il y a eu perte ou accès non autorisé.

## Export par atelier

Chaque propriétaire peut télécharger toutes les données de son atelier (ZIP de fichiers Excel) depuis la page *Confidentialité*. C'est aussi la réponse à une demande de portabilité des données.
