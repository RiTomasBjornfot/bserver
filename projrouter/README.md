# projrouter – enkel projekt-routing på en port (Nginx + Python backends)

Det här exemplet visar hur du kan hantera flera “projekt” bakom **en** publik HTTPS-endpoint på port **8000** genom att:

- köra **Nginx** som reverse proxy + TLS terminering på `:8000`
- köra varje projekt som en **lokal HTTP-backend** på `127.0.0.1:<port>`
- låta ett Python-lib (`projrouter`) skapa/ta bort projekt, uppdatera registry och synka Nginx routes

## Funktionalitet (v1)

Libbet erbjuder:

1. `activate(project_name, http_port)`
   - uppdaterar `registry.toml`
   - genererar ett minimalt `web.py` för projektet (`Hello world: <project_name>`)
   - skapar en systemd-tjänst för projektet (backend på `127.0.0.1:http_port`)
   - uppdaterar Nginx routes-fil och reloadar Nginx
   - gör sanity checks (internal + external /health)

2. `deactivate(project_name)`
   - stoppar/disable:ar systemd-tjänsten
   - tar bort projektet från registry
   - uppdaterar Nginx routes-fil och reloadar Nginx
   - **OBS:** rör inte projektkatalogen / filerna i root

3. `check()`
   - validerar Nginx config och att Nginx är aktiv
   - verifierar att routes-fil matchar registry
   - kontrollerar per projekt: systemd aktiv, port lyssnar, `/health` svarar internt och externt

---

## Arkitektur

Publikt:
- `https://sensorsystem.ri.se:8000/<projekt>/`
- `https://sensorsystem.ri.se:8000/<projekt>/health`

Internt på servern:
- Projekt `<projekt>` kör HTTP på `http://127.0.0.1:<port>/`
- Health: `http://127.0.0.1:<port>/health`

Nginx routar per path:
- `/<projekt>/` → `http://127.0.0.1:<port>/`

---

## Förutsättningar

- Linux-server med:
  - Nginx installerat
  - systemd
  - Python ≥ 3.11 (exemplet använder `tomllib`)
- DNS för `sensorsystem.ri.se` pekar på servern
- Port **8000** är öppen in till servern
- Nginx är redan konfigurerad för HTTPS på port 8000 (cert + key)
- Du kan köra kommandon med `sudo` (krävs för `/etc/nginx` och `/etc/systemd`)

> Viktigt: Nginx måste äga port 8000. Kör inte en Python-server direkt på 8000 samtidigt.

---

## One-time setup: Nginx include för routes

Libbet skriver en separat routes-fil som Nginx inkluderar.

1) Skapa routes-filens plats:

```bash
sudo mkdir -p /etc/nginx/snippets
sudo touch /etc/nginx/snippets/sensorsystem_routes.conf
````

2. Lägg in denna rad i din Nginx site-fil (inuti rätt `server { ... }` som lyssnar på `listen 8000 ssl;`):

```nginx
include /etc/nginx/snippets/sensorsystem_routes.conf;
```

3. Validera och reload:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## registry.toml (minimal)

Exempel: `/home/<user>/servers/registry.toml`

```toml
[global]
root = "/home/<user>/servers/projects"
domain = "sensorsystem.ri.se"
https_port = 8000
nginx_routes_file = "/etc/nginx/snippets/sensorsystem_routes.conf"

[projects]
# projekt1 = 9001
```

* `global.root` är parent-katalogen där projekten skapas:
  `.../projects/<project_name>/`
* `projects` innehåller map: `project_name = port`

---

## Kodlayout (förslag)

```
projrouter/
  projrouter/
    __init__.py
    core.py
  main.py
  README.md
```

---

## Install / körning

Eftersom detta är ett exempel kan du köra direkt med systempython.

### Aktivera ett projekt

```bash
sudo python3 main.py --registry /home/<user>/servers/registry.toml activate projekt1 9001
```

Detta skapar:

* `/home/<user>/servers/projects/projekt1/web.py`
* `/etc/systemd/system/proj-projekt1.service`
* uppdaterar `/etc/nginx/snippets/sensorsystem_routes.conf`
* reloadar Nginx

Testa:

```bash
curl -vk https://sensorsystem.ri.se:8000/projekt1/
curl -vk https://sensorsystem.ri.se:8000/projekt1/health
```

### Lista status / check

```bash
sudo python3 main.py --registry /home/<user>/servers/registry.toml check
```

Om något är fel får du ett sammanställt felmeddelande.

### Deaktivera ett projekt

```bash
sudo python3 main.py --registry /home/<user>/servers/registry.toml deactivate projekt1
```

Detta:

* stoppar/disable:ar `proj-projekt1.service`
* tar bort `projekt1` ur registry
* uppdaterar routes-filen och reloadar Nginx

**Filerna i** `/home/<user>/servers/projects/projekt1/` **lämnas kvar**.

---

## Systemd-tjänster

Tjänstnamn konvention:

* `proj-<project_name>.service`

Exempel:

```bash
systemctl status proj-projekt1 --no-pager -l
journalctl -u proj-projekt1 --no-pager | tail -n 50
```

---

## Nginx routes-fil

Routes-filen ägs helt av verktyget:

* `/etc/nginx/snippets/sensorsystem_routes.conf`

Den innehåller `location /projekt1/ { ... proxy_pass ... }` per projekt.

Manuella ändringar i filen skrivs över nästa gång `activate()/deactivate()` eller `check()` upptäcker diff.

---

## Säkerhet / drift-noter

* Backends lyssnar på `127.0.0.1` för att inte exponeras publikt.
* `activate()` gör en extern health-check med `curl -k` för att fungera även vid dev-cert / kedjeproblem.
  Om du har fullt betrott cert kan du ta bort `-k` i koden.
* För Flask/Dash i produktion: byt backend från `web.py` till `gunicorn app:server`.
  V1-exemplet är avsiktligt minimalt för att få routing + tjänster på plats.

---

## Vanliga problem

### Nginx startar inte efter routes-uppdatering

* Kontrollera att ingen annan process lyssnar på port 8000:

  ```bash
  sudo ss -lntp | grep ':8000'
  ```

### Permission denied vid `activate()`

* Du måste köra med `sudo` för att skriva `/etc/nginx` och `/etc/systemd/system`.

### Health fungerar internt men inte externt

* Kontrollera att Nginx inkluderar routes-filen i rätt `server {}`.
* Kontrollera att brandvägg/SG tillåter TCP 8000.
