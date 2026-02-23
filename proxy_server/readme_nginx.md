# Nginx
## 1. Installera
```
sudo apt update
sudo apt install nginx
```

## 2. Starta och aktivera
*Aktiverar Nginx så att det startar vid boot och direkt*
```
sudo systemctl enable --now nginx
```
*Visar statusen för systemtjänsten nginx*
```
sudo systemctl status nginx --no-pager
```

## 3. Kolla om det funkar
*Kör detta efter att konfigurationen är aktiverad: kollar om något lyssnar på port 8000 (HTTPS)*
```
sudo ss -lntp | grep ':8000'
```
## 4. Nginx konfiguration
Öppna:
```
sudo nvim /etc/nginx/sites-available/sensorsystem.conf
```
och klistra in:
```
server {
    listen 8000 ssl;
    server_name sensorsystem.ri.se;  # eller _ om du bara kör via IP

    # TLS-cert (exempel med self-signed eller egen certkedja)
    ssl_certificate     /etc/ssl/certs/sensorsystem.crt;
    ssl_certificate_key /etc/ssl/private/sensorsystem.key;

    # Bra proxy-headers
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # (Valfritt men ofta bra) lite större payloads
    client_max_body_size 50m;

    # Projekt: hello world
    # OBS trailing slash + proxy_pass med trailing slash
    location /hello_world/ {
        proxy_pass http://127.0.0.1:9001/;
    }

    # Ett till projekt...
    # location /projekt2/ {
    #        proxy_pass http://127.0.0.1:9002/;
    # }

    # (Valfritt) startsida som listar länkar
    location = / {
        return 200 "OK\nProjekt: /projekt1/  /projekt2/\n";
        add_header Content-Type text/plain;
    }
}
```

Länka sensorsystem.conf till /etc/nginx/sites-enabled
```
sudo ln -s /etc/nginx/sites-available/sensorsystem.conf /etc/nginx/sites-enabled/sensorsystem.conf
```

# Skapa TLS certifikat
*HTTPS kräver alltid TLS certifikat*
## 1. Installera openssl
```
sudo apt update
sudo apt install openssl
```
## 2. Kolla om /etc/ssl mappen finns annars skapa den
```
sudo mkdir -p /etc/ssl
```
## 3. Skapa certifikat (med namn sensorsystem)
*OBS: giltigt i ett år*
```
sudo openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
  -keyout /etc/ssl/private/sensorsystem.key \
  -out /etc/ssl/certs/sensorsystem.crt \
  -subj "/CN=sensorsystem.ri.se" \
  -addext "subjectAltName=DNS:sensorsystem.ri.se,DNS:localhost"
```
## 4. Ändra filrättigheter
```
sudo chmod 600 /etc/ssl/private/sensorsystem.key
sudo chmod 644 /etc/ssl/certs/sensorsystem.crt
```
## 5. Skapa en HTTP webserver
Spara på fil:
```
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
PORT = 9001

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"Hello world\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # Gör loggningen lite tystare (valfritt)
    def log_message(self, fmt, *args):
        return

if __name__ == "__main__":
    httpd = HTTPServer((HOST, PORT), Handler)
    print(f"Serving on http://{HOST}:{PORT}")
    httpd.serve_forever()
```
och kör:
```
python3 <filnamn>.py
```
Kolla konfigurationen och Starta om Nginx
```
sudo nginx -t
sudo systemctl restart nginx
```
## 6. Test
Testa lokalt på servern
```
curl -k -v https://localhost:8000/<projektnamn>/
```
Testa på klienten
```
wget https://sensorsystem.ri.se:8000/hello_world/ --no-check-certificate
```

## Lägg till en till routing
Exempel: lägg till route `/projekt2/` som proxas till backend på `127.0.0.1:9002`.

### 1. Lägg till `location` i Nginx-konfigurationen
Öppna:
```
sudo nvim /etc/nginx/sites-available/sensorsystem.conf
```
Lägg till i `server { ... }`:
```
location /projekt2/ {
    proxy_pass http://127.0.0.1:9002/;
}
```

### 2. Verifiera och ladda om Nginx
```
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Testa backend direkt på servern
```
curl -v http://127.0.0.1:9002/
```

### 4. Testa routing via Nginx på servern
```
curl -k -v https://localhost:8000/projekt2/
```

### 5. Testa från klient
```
wget https://sensorsystem.ri.se:8000/projekt2/ --no-check-certificate
```
