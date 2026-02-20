Här är en omskriven manual som utgår från att **varje projekt är en Python-app** (t.ex. `hello_world.py`) som kör **HTTP internt på localhost**, medan Nginx tar **HTTPS på port 8000** och routar `/projekt1/`, `/projekt2/` osv.

---

# Manual: HTTPS på port 8000 med Nginx + routing till Python-appar

## Översikt

Publikt (en port):

* `https://sensorsystem.ri.se:8000/`
* `https://sensorsystem.ri.se:8000/projekt1/`
* `https://sensorsystem.ri.se:8000/projekt2/`

Internt på servern:

* Projekt1-app: `http://127.0.0.1:9001/`
* Projekt2-app: `http://127.0.0.1:9002/`

Nginx:

* Terminerar TLS (cert + key)
* Routar paths till rätt backend-port

---

## 0) Förutsättningar

1. DNS för `sensorsystem.ri.se` pekar på din server.
2. Inbound TCP **8000** är öppet.
3. Du har cert+key (antingen self-signed eller publikt betrott).

> Viktigt: **Nginx måste äga port 8000**. Dina Python-appar ska **inte** lyssna på 8000, utan på 9001/9002 (localhost).

---

## 1) Installera Nginx

```bash
sudo apt update
sudo apt install -y nginx
```

---

## 2) Skapa och kör en Python-app som backend (Projekt1)

Det här är “Steg 2” anpassat till en Python-app.

### 2.1 Minimal Python-backend utan extra bibliotek (HTTP)

Skapa katalog:

```bash
sudo mkdir -p /srv/projekt1
sudo chown -R $USER:$USER /srv/projekt1
cd /srv/projekt1
```

Skapa `hello_world.py` (HTTP, ingen TLS här):

```bash
cat > hello_world.py <<'PY'
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"Hello from Projekt1\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

HTTPServer(("127.0.0.1", 9001), Handler).serve_forever()
PY
```

Starta:

```bash
python3 hello_world.py
```

Test lokalt på servern:

```bash
curl -v http://127.0.0.1:9001/
```

### 2.2 (Valfritt) Projekt2 på annan port

```bash
sudo mkdir -p /srv/projekt2
sudo chown -R $USER:$USER /srv/projekt2
cd /srv/projekt2

cat > hello_world.py <<'PY'
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"Hello from Projekt2\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

HTTPServer(("127.0.0.1", 9002), Handler).serve_forever()
PY

python3 hello_world.py
```

Test:

```bash
curl -v http://127.0.0.1:9002/
```

> Du kan byta ut dessa minimalservrar mot Flask/FastAPI/egen app – principen är densamma: bind till `127.0.0.1` och en intern port.

---

## 3) Se till att port 8000 är fri för Nginx

Om du tidigare körde Python på 8000 måste den stoppas.

Kontroll:

```bash
sudo ss -lntp | grep ':8000' || echo "8000 är fri"
```

Om något lyssnar på 8000:

```bash
sudo fuser -k 8000/tcp
```

---

## 4) Nginx-konfig: HTTPS på 8000 + routing till Python-appar

Skapa fil:

```bash
sudo tee /etc/nginx/sites-available/sensorsystem8000 >/dev/null <<'EOF'
server {
    listen 8000 ssl;
    server_name sensorsystem.ri.se;

    # Certifikatfiler (exempel för Let's Encrypt):
    ssl_certificate     /etc/letsencrypt/live/sensorsystem.ri.se/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/sensorsystem.ri.se/privkey.pem;

    location = / {
        return 200 "Sensorsystem reverse proxy OK\n";
        add_header Content-Type text/plain;
    }

    # /projekt1/ -> http://127.0.0.1:9001/
    location /projekt1/ {
        proxy_pass http://127.0.0.1:9001/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # /projekt2/ -> http://127.0.0.1:9002/
    location /projekt2/ {
        proxy_pass http://127.0.0.1:9002/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
```

Aktivera siten:

```bash
sudo ln -sf /etc/nginx/sites-available/sensorsystem8000 /etc/nginx/sites-enabled/sensorsystem8000
sudo rm -f /etc/nginx/sites-enabled/default
```

Test + restart:

```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl status nginx --no-pager -l
```

---

## 5) Testa routing via HTTPS

På servern:

```bash
curl -vk https://127.0.0.1:8000/
curl -vk https://127.0.0.1:8000/projekt1/
curl -vk https://127.0.0.1:8000/projekt2/
```

Från din dator:

```bash
curl -vk https://sensorsystem.ri.se:8000/projekt1/
curl -vk https://sensorsystem.ri.se:8000/projekt2/
```

> Använd gärna alltid trailing slash: `/projekt1/` och `/projekt2/`. Det minskar strul med paths och relativa länkar.

---

## 6) Kör Python-apparna som systemd-tjänster (rekommenderat)

Då startar de automatiskt och överlever logouts/reboots.

### Projekt1 service

```bash
sudo tee /etc/systemd/system/projekt1.service >/dev/null <<'EOF'
[Unit]
Description=Projekt1 Python backend
After=network.target

[Service]
WorkingDirectory=/srv/projekt1
ExecStart=/usr/bin/python3 /srv/projekt1/hello_world.py
Restart=always
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
EOF
```

### Projekt2 service

```bash
sudo tee /etc/systemd/system/projekt2.service >/dev/null <<'EOF'
[Unit]
Description=Projekt2 Python backend
After=network.target

[Service]
WorkingDirectory=/srv/projekt2
ExecStart=/usr/bin/python3 /srv/projekt2/hello_world.py
Restart=always
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
EOF
```

Aktivera:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now projekt1 projekt2
sudo systemctl status projekt1 projekt2 --no-pager -l
```

---

## 7) Certifikat på port 8000 (kort)

Om du inte kan använda port 80/443 för cert-utfärdande behöver du oftast DNS-01 via Certbot och Let's Encrypt, och sedan pekar Nginx på `fullchain.pem` + `privkey.pem`. (Det verkar du redan ha fungerande.)

---

### Om du vill att jag anpassar exakt för din befintliga `hello_world.py`

Klistra in din nuvarande `hello_world.py` (eller beskriv om den är Flask/FastAPI/egen server), så skriver jag om “Steg 2” så att **din app**:

* lyssnar på `127.0.0.1:9001` (eller valfri port),
* har rätt “base path” om den behöver ligga under `/projekt1/`,
* och får en korrekt systemd-service.

För att lägga till **projekt3** i den här setupen (Nginx på `:8000` + Python-backends på localhost) behöver du göra två saker:

1. **Starta en ny Python-app** som lyssnar på en ny intern port, t.ex. `127.0.0.1:9003`
2. **Lägga till en ny `location` i Nginx** som routar `/projekt3/` till `http://127.0.0.1:9003/`
   (+ om du kör systemd: skapa/aktivera en ny service för projekt3)

Nedan är exakta steg.

---

## 1) Skapa projekt3-backend (Python) på port 9003

```bash
sudo mkdir -p /srv/projekt3
sudo chown -R $USER:$USER /srv/projekt3
cd /srv/projekt3
```

Skapa en minimal backend `hello_world.py` (HTTP internt):

```bash
cat > hello_world.py <<'PY'
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"Hello from Projekt3\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

HTTPServer(("127.0.0.1", 9003), Handler).serve_forever()
PY
```

Testa lokalt på servern:

```bash
python3 /srv/projekt3/hello_world.py
# i en annan terminal:
curl -v http://127.0.0.1:9003/
```

---

## 2) Lägg till routing i Nginx

Öppna Nginx-siten:

```bash
sudo nano /etc/nginx/sites-available/sensorsystem8000
```

Lägg in detta block (bredvid de andra):

```nginx
location /projekt3/ {
    proxy_pass http://127.0.0.1:9003/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Testa config och ladda om Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Testa:

```bash
curl -vk https://127.0.0.1:8000/projekt3/
curl -vk https://sensorsystem.ri.se:8000/projekt3/
```

---

## 3) (Rekommenderat) Kör projekt3 som systemd-service

Skapa servicefil:

```bash
sudo tee /etc/systemd/system/projekt3.service >/dev/null <<'EOF'
[Unit]
Description=Projekt3 Python backend
After=network.target

[Service]
WorkingDirectory=/srv/projekt3
ExecStart=/usr/bin/python3 /srv/projekt3/hello_world.py
Restart=always
User=www-data
Group=www-data

[Install]
WantedBy=multi-user.target
EOF
```

Aktivera och starta:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now projekt3
sudo systemctl status projekt3 --no-pager -l
```

---

## Tips (för att slippa strul)

* Använd alltid **trailing slash**: `/projekt3/`
* Se till att porten du väljer (9003) inte redan används:

  ```bash
  ss -lntp | grep ':9003' || echo "9003 fri"
  ```
* Backends ska alltid lyssna på **127.0.0.1** (inte 0.0.0.0) för att inte exponeras publikt.

---

Om du vill kan jag också ge en liten “index”-sida på `/` som automatiskt listar dina projektlänkar (projekt1–projektN).


