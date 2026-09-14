# Odoo 18 Dev-Instanz (Docker)

## Start / Stop
```powershell
docker compose up -d      # starten
docker compose logs -f odoo   # Logs
docker compose down       # stoppen (Daten bleiben in Volumes)
docker compose down -v    # stoppen + Daten loeschen
```

## Zugang
- URL: http://localhost:8069
- Datenbank: `dev` (mit Demo-Daten)
- Login: `admin` / Passwort: `admin`
- Master-Passwort (DB-Manager): `admin`

## Module entwickeln
Eigene Module gehoeren nach `./addons/<modulname>/` — das ist im Container
als `/mnt/extra-addons` gemountet und liegt im addons_path.

`--dev=reload,qweb,xml` ist aktiv: Python-Aenderungen loesen einen Reload aus,
QWeb/XML-Templates werden bei jedem Request neu gelesen.

Nach dem Anlegen eines neuen Moduls: in Odoo unter *Apps* -> *Update Apps List*,
oder per CLI:

```powershell
# Modul installieren
docker compose run --rm --no-deps odoo odoo -c /etc/odoo/odoo.conf -d dev -i <modul> --stop-after-init
# Modul aktualisieren
docker compose run --rm --no-deps odoo odoo -c /etc/odoo/odoo.conf -d dev -u <modul> --stop-after-init
```

Hinweis Git Bash: `MSYS_NO_PATHCONV=1` vor den Befehl setzen, sonst werden
die Container-Pfade in Windows-Pfade umgeschrieben.

## Struktur
- `docker-compose.yml` — odoo:18.0 + postgres:16
- `config/odoo.conf` — Odoo-Konfiguration
- `addons/` — eigene Module (gemountet nach /mnt/extra-addons)
