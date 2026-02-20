# One-time: gör Nginx “include”-plats för auto-genererade routes

# 1. Skapa routes-filens plats (som libbet kommer skriva):
sudo mkdir -p /etc/nginx/snippets
sudo touch /etc/nginx/snippets/sensorsystem_routes.conf
# 2. I din Nginx site (ex /etc/nginx/sites-available/sensorsystem8000) lägg in:
include /etc/nginx/snippets/sensorsystem_routes.conf;
# 3. Lägg den inuti rätt server { ... } som lyssnar listen 8000 ssl;.Test:
sudo nginx -t && sudo systemctl reload nginx

