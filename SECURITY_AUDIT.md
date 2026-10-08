# Rapport d'audit de sécurité — Plateforme UHI (FIWARE)

> **Méthodologie.** Audit multi-agents *ancré dans le code* : une analyse par surface d'attaque, puis **vérification adverse** de chaque constat par un second agent indépendant (chargé de *réfuter* la faille) pour éliminer les faux positifs et recalibrer la sévérité.
>
> **Portée.** 9 surfaces d'attaque, **64 constats au total : 63 confirmés, 1 réfuté.** §2-§4 traitent les surfaces Docker/réseau, nginx, Orion-LD, GeoServer et geoserver-sync (40 constats) ; **§5** détaille les 4 surfaces applicatives `prediction-api`, `ingestion-api`, `secrets`, `frontend-app` (24 constats). *Audit complet.*
>
> **Contexte de déploiement visé.** VM publique unique (Oracle Always Free), un seul reverse proxy HTTPS sur :443, tous les backends privés sur le réseau Docker. Le login/register est **désactivé volontairement** — aucune recommandation n'ajoute de compte utilisateur.

---

## 1. Verdict global

**Telle quelle, déployée sur une VM publique, la plateforme serait compromise en quelques heures — automatiquement, sans ciblage.** Deux chemins triviaux suffisent :

1. **MongoDB sans authentification, exposé sur le port 27017.** C'est exactement la configuration balayée en masse par les campagnes de rançongiciel Mongo. Un bot trouve le port ouvert, se connecte sans identifiant, et exécute `db.dropDatabase()` → toutes vos entités NGSI-LD détruites.
2. **GeoServer en identifiants par défaut `admin` / `geoserver`, exposé** (port 8080 direct **et** via le proxy `/geoserver/web` + `/geoserver/rest`). `admin/geoserver` est l'un des couples les plus scannés d'internet. Login → administration complète → lecture de fichiers serveur → RCE (la version 2.24.2 est vulnérable à **CVE-2024-36401**, RCE non authentifiée).

La cause profonde est unique et architecturale : **rien n'isole les backends.** Tous les ports sont publiés, et le proxy relaie l'intégralité des API backend sans aucun filtrage. La bonne nouvelle : la quasi-totalité des correctifs sont **rapides** (`Quick`) et concentrés dans **2 fichiers** — `docker-compose.yml` et `services/frontend/nginx.conf`.

### Répartition des 63 constats confirmés (sévérité recalibrée après vérification)

| Sévérité | Nombre | Nature |
|---|---|---|
| 🔴 Critique | 11 | Compromission/destruction non authentifiée, accessible depuis internet |
| 🟠 Élevé | 18 | Abus sérieux : DoS, exfiltration, prise de contrôle admin, SSRF, lecture de fichier arbitraire |
| 🟡 Moyen | 12 | Faiblesses réelles (TLS, durcissement, injection bornée, token client exposé) |
| 🔵 Faible | 16 | Défense en profondeur |
| ⚪ Info | 6 | Hygiène + 2 résultats *négatifs* rassurants (pas de XSS, dépendances à jour) |

> *Plusieurs constats se recoupent entre surfaces (ex. identifiants GeoServer par défaut, DEBUG Orion) : ce sont des **confirmations indépendantes** des mêmes causes racines, pas des problèmes distincts — ce qui renforce la confiance dans le diagnostic.*

---

## 2. Causes racines (constats regroupés)

### 🔴 CR1 — Tous les ports backends sont publiés sur l'hôte

> **Constats : MongoDB 27017 (Critique), GeoServer 8080 (Critique), Ingestion 8001 (Critique), Orion 1026 (Critique/Élevé), Prediction 8002 (Élevé).**

> ⚠️ **Cas particulier de l'ingestion (port 8001) — relevé Critique.** Contrairement aux autres, `/ingest/*` n'est **pas** derrière le proxy nginx → vous pourriez croire ce service privé. Mais le port publié le rend joignable sur l'IP publique, **sans authentification**, et il sert de **rampe de lancement** à 3 autres failles : SSRF (URLs de téléchargement attaquant), zip-slip, et épuisement disque (voir §5). C'est la porte d'entrée la plus inattendue.

`docker-compose.yml` publie `27017`, `1026`, `8001`, `8002`, `8080` directement sur l'hôte. Sur une VM publique, Docker insère ses propres règles iptables (DNAT) qui **contournent le pare-feu de l'hôte (UFW)** — ces ports sont donc joignables sur l'IP publique, et **court-circuitent complètement** le principe « seul le proxy est public ». Tout durcissement du proxy nginx devient inutile tant que ces ports sont ouverts.

**Correctif (rapide, non destructif).** Supprimer les blocs `ports:` de ces 5 services. Les conteneurs communiquent déjà entre eux par leur **nom Docker** (`mongo`, `orion:1026`, `geoserver:8080`…) — vérifié : `ORIONLD_MONGO_HOST=mongo`, `ORION_URL=http://orion:1026`, `proxy_pass http://geoserver:8080`. Aucune publication d'hôte n'est nécessaire au fonctionnement.

```yaml
  mongo:
    image: mongo:5.0          # garder 5.0 (compat Orion-LD 1.6.0, cf. commentaire ligne 2)
    # ports:                  # ← SUPPRIMÉ (était 27017:27017)
    #   - "27017:27017"
```
Idem pour `orion`, `ingestion`, `prediction`, `geoserver`. Si un port est requis pour du debug ponctuel, le lier au loopback : `"127.0.0.1:1026:1026"`. Défense supplémentaire : restreindre la *Security List* du VCN Oracle à 443 (+22 pour SSH).

> Référence : `docker-compose.yml:6-7, 22-23, 45-46, 72-73, 134-135`.

---

### 🔴 CR2 — Le proxy nginx relaie *toute* l'API backend sans filtrage

> **Constats (12) : Orion write/delete via /orion (Critique ×2), subscriptions SSRF (Élevé), GeoServer /web admin via proxy (Critique), GeoServer /rest via proxy (Critique), surface prediction complète proxifiée (Élevé), précondition d'écriture /orion pour geoserver-sync (Élevé), CORS `*` (Faible), pas de header de méthode appliqué.**

Les trois blocs `location` de [nginx.conf](services/frontend/nginx.conf) font un `proxy_pass` *préfixe* sans aucune restriction de méthode ni de chemin. Point crucial : **`add_header 'Access-Control-Allow-Methods' ...` n'applique rien** — c'est un en-tête de réponse CORS, purement consultatif pour le navigateur. nginx **transmet tous les verbes** (POST/PATCH/DELETE/PUT) au backend. Et un attaquant qui rejoue la requête avec `curl` ignore CORS de toute façon.

Conséquences (toutes non authentifiées, depuis internet) :
- **`/orion/`** → API NGSI-LD complète d'un broker **sans authentification** (Orion-LD 1.6.0 n'en a aucune). `DELETE /orion/ngsi-ld/v1/entities/urn:ngsi-ld:UHIHeatMap:XGBoost:brussels:2024` détruit la carte ; `PATCH .../attrs` falsifie les températures affichées ; `POST /ngsi-ld/v1/subscriptions` avec une `notification.endpoint.uri` arbitraire transforme Orion en **pivot SSRF** vers les services internes et la **métadonnée Oracle** (`169.254.169.254`), ou exfiltre les données vers `attacker.com`. Le frontend ([orionApi.js](services/frontend/src/services/orionApi.js)) ne fait que **2 GET** — tout le reste est de la surface inutile.
- **`/geoserver/`** → expose `/geoserver/web` (console admin) et `/geoserver/rest` (API admin). Combiné aux identifiants par défaut (CR3) = prise de contrôle totale.
- **`/prediction/`** → expose `POST /training/start`, `POST /predict/map`, `DELETE /training/cache` (destructif), `POST /sensors/sync` (SSRF sortant à la demande) — voir CR5.

**Correctif (rapide).** Remplacer chaque `proxy_pass` fourre-tout par une **liste blanche** stricte qui n'autorise *exactement* ce que l'app utilise, et **appliquer** les méthodes avec `limit_except` :

```nginx
# --- ORION : uniquement les 2 GET dont le SPA a besoin ---
location = /orion/ngsi-ld/v1/entities {        # liste des capteurs (avec ?type=...)
    limit_except GET OPTIONS { deny all; }
    proxy_pass http://orion:1026/ngsi-ld/v1/entities$is_args$args;
}
location = /orion/ngsi-ld/v1/entities/urn:ngsi-ld:UHIHeatMap:XGBoost:brussels:2024 {
    limit_except GET OPTIONS { deny all; }
    proxy_pass http://orion:1026/ngsi-ld/v1/entities/urn:ngsi-ld:UHIHeatMap:XGBoost:brussels:2024;
}
location /orion/ { return 404; }               # tout le reste rejeté

# --- GEOSERVER : seulement le WMS, jamais /web ni /rest ---
location ~ ^/geoserver/(web|rest|console|gwc/rest|wps) { return 404; }
location /geoserver/ {
    limit_except GET HEAD OPTIONS { deny all; }
    proxy_pass http://geoserver:8080/geoserver/;
}

# --- PREDICTION : liste blanche des endpoints du SPA (cf. predictionApi.js) ---
#   /predict/pixel/value, /predict/layer/stats, /predict/zone/stats, /predict/zone, /predict/download
location /prediction/ { return 404; }          # catch-all → rejet ; déclarer une location = par endpoint autorisé
```

Et **remplacer `Access-Control-Allow-Origin '*'`** par votre domaine exact (`https://votre-domaine`) — ou supprimer les en-têtes CORS, le SPA étant servi en *same-origin* par le proxy.

> Les services internes (prediction, geoserver-sync) parlent à Orion/GeoServer via le **réseau Docker** (`http://orion:1026`, `http://geoserver:8080/geoserver/rest`) — la liste blanche publique ne casse donc **rien** côté backend.

---

### 🔴 CR3 — GeoServer en identifiants par défaut `admin` / `geoserver`

> **Constats (4) : creds par défaut actifs (Critique), creds codés en dur dans docker-compose (Élevé), réutilisés par geoserver-sync (Moyen), pas de compte à privilèges réduits (Info).**

Le service `geoserver` ne définit **aucun** `GEOSERVER_ADMIN_PASSWORD` → l'image `2.24.2` démarre avec le compte usine `admin/geoserver`. C'est **confirmé en usage** : `geoserver-sync` s'authentifie avec exactement `admin`/`geoserver` ([docker-compose.yml:115-116](docker-compose.yml#L115), [config.py:14-15](services/geoserver-sync/src/config.py#L14)). Ces identifiants sont aussi **versionnés en clair** dans le dépôt.

**Correctif (rapide).**
```yaml
  geoserver:
    environment:
      - GEOSERVER_ADMIN_USER=uhi_admin
      - GEOSERVER_ADMIN_PASSWORD=${GEOSERVER_ADMIN_PASSWORD}   # depuis .env (gitignored)
```
Mettre le même secret fort dans `.env`, le répercuter sur `geoserver-sync` (`GEOSERVER_PASSWORD=${GEOSERVER_ADMIN_PASSWORD}`), **changer aussi le mot de passe *master*** GeoServer après le 1er démarrage, et faire échouer `config.py` si la variable est absente (au lieu de retomber silencieusement sur `geoserver`).

---

### 🟠 CR4 — GeoServer 2.24.2 : RCE connue, non corrigée

> **Constat : images obsolètes / EOL (Élevé).**

GeoServer **2.24.2** est antérieur aux correctifs de **CVE-2024-36401** (évaluation de `PropertyName` → **RCE non authentifiée**, PoC public) et **CVE-2024-36404**. Comme GeoServer est joignable publiquement (CR2), c'est une RCE *directement exploitable*, pas seulement de l'hygiène. MongoDB 5.0 est EOL (oct. 2024) ; `nginx:alpine` n'est pas épinglé.

**Correctif.** Monter GeoServer à la dernière 2.2x de sécurité (**≥ 2.24.4 / 2.25.x**) en priorité ; épingler les images par version/digest ; ajouter un scan (`Trivy` / `docker scout cves`) au build. *(Garder Mongo 5.0 : épinglé pour Orion-LD 1.6.0 — ne pas monter en 7.0.)*

> Référence : `docker-compose.yml:4, 20, 132`.

---

### 🟠 CR5 — Aucune protection anti-DoS ni limite de ressources

> **Constats (5) : pas de rate-limit sur le proxy (Élevé), pas de limites CPU/RAM conteneurs (Élevé), endpoints prediction lourds exposés (Élevé), GetMap WMS non borné (Élevé), pas de rate-limit /orion (Moyen).**

Sur une **petite VM ARM** hébergeant les 7 services, le proxy est la seule barrière. Or il n'a **ni `limit_req`, ni `client_max_body_size` adapté, ni timeouts serrés**, et **aucun service n'a de `mem_limit`/`cpus`/`restart:`**. Vecteurs concrets et non authentifiés :
- `POST /prediction/predict/zone` avec un grand polygone → lecture de 10 rasters + `distance_transform_edt` + `XGBoost.predict(nthread=os.cpu_count())` → **satura tous les cœurs** par requête ([zone_predictor.py:188](services/prediction/algorithm/application/zone_predictor.py#L188)).
- `GET /geoserver/uhi/wms?...&width=20000&height=20000` → ~1,6 Go de heap par image → **OOM-kill** de GeoServer (le raster RGB fait 47500×45001 px).
- Sans `restart:`, un crash reste *down* jusqu'à intervention manuelle.

**Correctif.**
```nginx
# contexte http {}
limit_req_zone  $binary_remote_addr zone=api:10m rate=5r/s;
limit_conn_zone $binary_remote_addr zone=conn:10m;
# dans chaque location proxifiée :
limit_req zone=api burst=10 nodelay;
limit_conn conn 20;
client_max_body_size 256k;
proxy_read_timeout 30s; proxy_send_timeout 15s; client_body_timeout 10s;
```
```yaml
  prediction:
    restart: unless-stopped
    mem_limit: 2g
    cpus: "1.0"
    pids_limit: 256
```
Plus : caps `mem_limit`/`cpus` + `restart: unless-stopped` sur **tous** les services ; dans GeoServer, plafonner *Max rendering memory/time* et la taille GetMap (ex. 4096×4096), ou servir via GeoWebCache pré-seedé ; **valider la taille des polygones** dans `predict_zone` (rejeter au-delà d'une aire max *avant* de lire les rasters).

---

### 🟡 CR6 — Pas de TLS (HTTPS)

> **Constats (2) : proxy en `listen 80` seulement (Moyen), frontend publié en `3000:80` (Moyen).**

[nginx.conf:2](services/frontend/nginx.conf#L2) n'écoute qu'en HTTP. Aucun bloc `:443`, certificat, ni redirection 80→443 dans le dépôt. En l'état, tout le trafic (y compris `/orion`, `/prediction`) passerait **en clair** → interception et injection de JS dans le SPA par un attaquant *on-path*.

**Correctif.** Terminer le TLS au reverse proxy unique. Le plus simple pour un débutant : **Caddy** (certificats Let's Encrypt automatiques), ou un nginx `:443` avec `certbot`. Publier uniquement `443` (+`80` pour ACME/redirection), et lier le frontend en `127.0.0.1:3000:80` derrière le proxy TLS. *(Détails en Phase 3.)*

---

### 🟡 CR7 — geoserver-sync : « confused deputy » via notification Orion

> **Constats (3) : coverage store sur chemin de fichier arbitraire (Moyen), injection XML/chemin dans l'API REST GeoServer (Moyen), creds admin partagés (Moyen).**

`geoserver-sync` est bien privé (pas de port publié), mais il **agit sur des données reçues d'Orion** — or Orion est écrivable publiquement (CR2). Un attaquant POST une entité `GeoSpatialLayer` avec `publishToGeoserver=true` et un `filePath` arbitraire ; `translate_path` **renvoie le chemin tel quel** s'il ne matche aucun préfixe connu ([config.py:67-71](services/geoserver-sync/src/config.py#L67)) ; ce chemin est injecté brut dans `<url>file:{file_path}</url>` ([geoserver.py:198](services/geoserver-sync/src/geoserver.py#L198)) et publié via les **identifiants admin**. De plus, `store_name`/`coverage_name` (dérivés de `layerType.value` attaquant) ne sont **ni échappés ni validés** → injection XML et manipulation de chemin dans l'API REST.

**Correctif.** (1) Le fix CR2 (verrouiller `/orion` en GET seul) **supprime déjà la précondition**. (2) En défense en profondeur : `translate_path` doit **rejeter** (pas laisser passer) les chemins non listés ; valider les noms par regex (`^[a-z0-9_]{1,64}$`) ; échapper le XML / `urllib.parse.quote` les segments d'URL ; ajouter un **secret partagé** sur l'endpoint `/sync` (vérifié dans le handler).

---

### 🔵 CR8 — Durcissement des conteneurs, secrets & journaux

> **Constats (8, Faible→Info) : conteneurs en root sans `cap_drop`/`no-new-privileges`/`read_only` (Moyen), montages hôte inutilement en écriture (Faible), pas de segmentation réseau (Faible), `ORIONLD_LOG_LEVEL=DEBUG` (Faible), pas de headers de sécurité (Faible), `server_tokens` (Info).**

Aucun `Dockerfile` n'a de directive `USER` → tout tourne en **root**. Aucune limite de capacités, montages `./data/*` en écriture partagés entre services, un seul réseau `bridge` à plat, logs Orion en `DEBUG` (fuite d'infos + saturation disque), aucun en-tête de sécurité (CSP, X-Frame-Options, HSTS…), `server_tokens` non désactivé.

**Correctif (à faire en lot, après les P0/P1).**
```dockerfile
RUN useradd -u 10001 -m app
USER app
```
```yaml
    security_opt: ["no-new-privileges:true"]
    cap_drop: ["ALL"]
```
Plus : montages GeoServer `:ro` sur `data/processed`/`data/raw` ; deux réseaux (frontend/backend) ; `ORIONLD_LOG_LEVEL=WARN` + rotation des logs (`json-file`, `max-size: 10m`) ; en-têtes de sécurité (répétés dans chaque `location` — voir note sur l'héritage `add_header`) ; `server_tokens off;`.

---

## 3. Feuille de route priorisée → branchée sur la Phase 3 (déploiement)

### 🔴 P0 — Bloquant. **À faire avant toute mise en ligne.**
1. **CR1** — Supprimer tous les `ports:` backends (`docker-compose.yml`). *(Quick)*
2. **CR3** — Changer le mot de passe admin GeoServer + master password. *(Quick)*
3. **CR2** — Listes blanches méthode+chemin sur les 3 `location` nginx (`/orion` GET-only, bloquer `/geoserver/(web|rest)`, allow-list `/prediction`). *(Quick)*
4. **CR6** — TLS sur le proxy unique (Caddy/Let's Encrypt) + ne publier que 443. *(Medium)*
5. **Pare-feu Oracle** — VCN Security List : ingress 443 (+22) uniquement.

### 🟠 P1 — Important. Juste après la mise en ligne.
6. **CR4** — Monter GeoServer ≥ 2.24.4. *(Medium)*
7. **CR5** — `limit_req`/`client_max_body_size`/timeouts nginx + `mem_limit`/`cpus`/`restart:` + plafonds WMS GeoServer. *(Medium)*
8. **CR2/CR7** — Confirmer que `/orion` est en GET-only (neutralise le confused-deputy) + valider `translate_path`/noms dans geoserver-sync. *(Medium)*
9. Sortir les secrets de `docker-compose.yml` → `.env` gitignored. *(Quick)*

### 🟡 P2 — Défense en profondeur.
10. **CR8** — conteneurs non-root + `cap_drop`/`no-new-privileges`, montages `:ro`, 2 réseaux, `LOG_LEVEL=WARN` + rotation, en-têtes de sécurité, `server_tokens off`. *(Involved)*
11. Scan d'images (Trivy) régulier ; sauvegardes Mongo chiffrées.

---

## 4. Annexe — table des 40 constats confirmés

| # | Surface | Constat | Sévérité (recalibrée) | Effort |
|---|---|---|---|---|
| 1 | docker | MongoDB 27017 sans auth (rançon/destruction) | 🔴 Critique | Quick |
| 2 | docker | Orion 1026 publié (bypass proxy, SSRF) | 🟠 Élevé | Quick |
| 3 | docker | Ingestion 8001 publié (SSRF + download distant) | 🟠 Élevé | Quick |
| 4 | docker | Prediction 8002 publié (endpoints lourds) | 🟠 Élevé | Medium |
| 5 | docker | GeoServer 8080 + creds défaut + CORS `*` | 🔴 Critique | Medium |
| 6 | docker | Creds GeoServer en clair + `LOG_LEVEL=DEBUG` | 🟠 Élevé | Quick |
| 7 | docker | Frontend en `3000:80`, pas de TLS | 🟡 Moyen | Medium |
| 8 | docker | Aucune limite CPU/RAM ni `restart:` | 🟠 Élevé | Medium |
| 9 | docker | Tous les conteneurs en root, pas de `cap_drop` | 🟡 Moyen | Involved |
| 10 | docker | Montages hôte en écriture partagés | 🔵 Faible | Quick |
| 11 | docker | Images obsolètes/EOL (GeoServer 2.24.2 → RCE) | 🟠 Élevé | Medium |
| 12 | docker | nginx PATCH/DELETE sur /orion + CORS `*` | 🟠 Élevé | Medium |
| 13 | docker | Pas de segmentation réseau / `restart:` | 🔵 Faible | Medium |
| 14 | nginx | Orion : API write/delete complète proxifiée | 🔴 Critique | Quick |
| 15 | nginx | Prediction : surface complète proxifiée (+`DELETE /training/cache`) | 🟠 Élevé | Medium |
| 16 | nginx | GeoServer : `/web` + `/rest` admin via proxy | 🟠 Élevé | Medium |
| 17 | nginx | Pas de rate-limit / body-size / timeouts | 🟠 Élevé | Medium |
| 18 | nginx | `listen 80` seulement (pas de TLS) | 🟡 Moyen | Medium |
| 19 | nginx | `Access-Control-Allow-Origin: *` partout | 🔵 Faible | Quick |
| 20 | nginx | Aucune clé d'API sur les endpoints sensibles | 🟡 Moyen | Medium |
| 21 | nginx | Aucun en-tête de sécurité (CSP, HSTS…) | 🔵 Faible | Quick |
| 22 | nginx | `server_tokens` non désactivé | ⚪ Info | Quick |
| 23 | orion | API NGSI-LD write/delete non auth via /orion | 🔴 Critique | Quick |
| 24 | orion | Création de subscription → SSRF / exfiltration | 🟠 Élevé | Quick |
| 25 | orion | Port 1026 publié (bypass total) | 🔴 Critique | Quick |
| 26 | orion | CORS `*` sur /orion | 🔵 Faible | Quick |
| 27 | orion | `ORIONLD_LOG_LEVEL=DEBUG` (fuite + disque) | 🔵 Faible | Quick |
| 28 | orion | Pas de rate-limit / body-size sur /orion | 🟡 Moyen | Medium |
| 29 | geoserver | Console `/web` via proxy + creds défaut → RCE | 🔴 Critique | Quick |
| 30 | geoserver | Port 8080 publié (bypass proxy) | 🔴 Critique | Quick |
| 31 | geoserver | API `/rest` via proxy + creds défaut | 🔴 Critique | Quick |
| 32 | geoserver | Identifiants par défaut `admin/geoserver` | 🔴 Critique | Quick |
| 33 | geoserver | GetMap non borné (OOM / DoS) | 🟠 Élevé | Medium |
| 34 | geoserver | CORS `*` + méthodes write | 🔵 Faible | Quick |
| 35 | geoserver | sync utilise l'admin global (pas de compte scopé) | ⚪ Info | Medium |
| 36 | geoserver | GetCapabilities → reconnaissance | ⚪ Info | Medium |
| 37 | gs-sync | Coverage store sur chemin de fichier arbitraire | 🟡 Moyen | Medium |
| 38 | gs-sync | Injection XML / manipulation chemin REST | 🟡 Moyen | Medium |
| 39 | gs-sync | Creds admin GeoServer codés en dur | 🟡 Moyen | Quick |
| 40 | gs-sync | /orion écrivable = précondition des attaques sync | 🟠 Élevé | Quick |

---

## 5. Surfaces applicatives — résultats (prediction, ingestion, secrets, frontend)

24 constats (23 confirmés, 1 réfuté). Trois sont des nouveautés notables, et il y a aussi de bonnes nouvelles.

### 🆕 Nouveautés importantes

**🟠 N1 — Lecture de fichier arbitraire via `/predict/download` (path traversal, Élevé).**
`download_layer` construit le chemin du fichier **uniquement** à partir du `filePath` de l'entité Orion ([layer_resolver.py:88-108](services/prediction/algorithm/infrastructure/layer_resolver.py#L88) ne vérifie que `path.exists()`). Le *nom* de couche est en liste blanche, mais le *chemin* est ce que contient Orion — or Orion est écrivable depuis internet (CR2). Chaîne : `PATCH /orion/.../entities/urn:...:NDVI:.../attrs {"filePath":{"value":"/etc/passwd"}}` puis `POST /prediction/predict/download {"layer":"ndvi"}` sans géométrie → le service **renvoie le fichier brut** (modèle XGBoost, n'importe quel fichier lisible par le conteneur). *Correctif : verrouiller `/orion` en GET (CR2) **et** valider en défense en profondeur que le chemin résolu reste dans un dossier autorisé (`resolved.is_relative_to(base)`).* → [zone_router.py:339-388](services/prediction/algorithm/api/zone_router.py#L339)

**🟡 N2 — Token Cesium ion exposé dans l'historique git (Moyen).**
Un vrai token Cesium ion (JWT du compte 278738, **sans date d'expiration**) a été codé en dur dans `CesiumViewer.js` sur ~11 commits avant d'être déplacé vers `.env`. Il reste **récupérable à vie dans l'historique git**. *Correctif : (1) **révoquer/roter** le token dans la console Cesium ion immédiatement ; (2) créer un token limité aux seuls asset IDs utilisés ; (3) purger l'historique (`git filter-repo`/BFG) ; (4) le traiter comme une clé publique (un SPA ne peut pas cacher ce token).*

**⚙️ N3 — Piège fonctionnel pour la Phase 3 (à ne pas oublier).** Le constat « token Cesium dans le bundle public » a été **réfuté** : `.dockerignore` exclut `.env`, donc le build Docker de prod **ne contient pas** `VITE_CESIUM_ION_TOKEN`. Conséquence : **en production, le terrain 3D + le géocodeur Cesium tomberont en panne silencieusement** sauf si vous passez le token via un *build arg*. À gérer au déploiement :
```dockerfile
ARG VITE_CESIUM_ION_TOKEN
ENV VITE_CESIUM_ION_TOKEN=$VITE_CESIUM_ION_TOKEN
RUN npm run build
```

### ✅ Bonnes nouvelles (résultats négatifs vérifiés)
- **Pas de XSS** : aucun `v-html`/`innerHTML` ; toutes les données serveur passent par l'interpolation Vue `{{ }}` (échappée). L'InfoBox Cesium est désactivée. *(vérifié sur App.vue, useSensorMarkers.js, CesiumViewer.js)*
- **Dépendances frontend à jour** (Vue 3.5.29, Vite 5.4.21, Cesium 1.138.0) — aucune CVE notable applicable.
- **Pas de source maps** en production.
- **Pas de secret réel** dans le `.env` local (URLs publiques UrbIS uniquement).

### Table des 24 constats applicatifs

| # | Surface | Constat | Sévérité | Effort |
|---|---|---|---|---|
| 41 | prediction | `/training/start` non auth, `n_estimators` non borné → épuisement CPU/RAM/disque | 🟠 Élevé | Medium |
| 42 | prediction | **Lecture fichier arbitraire** via `filePath` Orion + `/predict/download` (N1) | 🟠 Élevé | Medium |
| 43 | prediction | `objects[]` / polygone non bornés dans `/predict/zone` (OOM) | 🟡 Moyen | Medium |
| 44 | prediction | `/predict/map` inférence pleine échelle non auth | 🟡 Moyen | Quick |
| 45 | prediction | `/sensors/sync` non auth → requêtes sortantes (abus/ban IP) | 🔵 Faible | Quick |
| 46 | prediction | `DELETE /training/cache` efface le cache (amplifie le DoS training) | 🔵 Faible | Quick |
| 47 | prediction | Messages d'exception renvoyés verbatim (fuite de chemins internes) | 🔵 Faible | Quick |
| 48 | ingestion | **API 8001 publique, sans auth** (rampe SSRF/zip-slip/disque) | 🔴 Critique | Quick |
| 49 | ingestion | **SSRF** via URLs de téléchargement attaquant (→ métadonnée Oracle, réseau interne) | 🟠 Élevé | Medium |
| 50 | ingestion | Téléchargements non bornés → épuisement disque/bande passante | 🟠 Élevé | Medium |
| 51 | ingestion | **Zip-slip** dans `extractall` (écriture hors dossier, conteneur root) | 🟠 Élevé | Medium |
| 52 | ingestion | Garde de concurrence faible (TOCTOU) sur le déclencheur | 🔵 Faible | Quick |
| 53 | ingestion | Conteneur en root (amplifie zip-slip) | 🔵 Faible | Quick |
| 54 | secrets | **Token Cesium ion dans l'historique git** (sans expiration) (N2) | 🟡 Moyen | Medium |
| 55 | secrets | Identifiants GeoServer par défaut (confirmation, cf. CR3) | 🔴 Critique | Quick |
| 56 | secrets | Token Cesium inliné dans le bundle SPA (clé publique par nature) | 🟡 Moyen | Quick |
| 57 | secrets | Pas de lockfiles Python (`--require-hashes`), `npm install` au lieu de `npm ci` | 🔵 Faible | Medium |
| 58 | secrets | `.gitignore` ne couvre que `.env` (pas `.env.*`) | 🔵 Faible | Quick |
| 59 | secrets | `ORIONLD_LOG_LEVEL=DEBUG` (confirmation, cf. CR8) | ⚪ Info | Quick |
| 60 | frontend | Pas d'en-têtes de sécurité (CSP, X-Frame-Options) | 🔵 Faible | Medium |
| 61 | frontend | Fallback `http://localhost:8080/geoserver` codé en dur (fuite topologie + bug prod) | 🔵 Faible | Quick |
| — | frontend | Token Cesium dans le bundle prod → **RÉFUTÉ** (`.dockerignore` exclut `.env`) (N3) | ⚪ Info | — |
| 62 | frontend | Pas de sink XSS — *résultat négatif rassurant* | ⚪ Info | — |
| 63 | frontend | Dépendances à jour, pas de source maps — *résultat négatif rassurant* | ⚪ Info | — |

### Impact sur la feuille de route
- **P0** : ajouter **#48 (ingestion 8001)** — déjà couvert par CR1 (supprimer les `ports:`).
- **P1** : **#42/N1** (valider le chemin de `/predict/download` + lock `/orion`), **#49-#51** (validation/allow-list des URLs, cap de taille, extraction zip sûre), **#54/N2** (roter le token Cesium + purger l'historique), borner `n_estimators`/`objects[]`/vertices côté FastAPI.
- **Phase 3** : ne pas oublier **N3** (build arg Cesium) sous peine de casser le rendu 3D en prod.
