# Deploy Quickstart

## 1. Instalacion inicial

```bash
cd /home/egonzalez/Documents/app/PanamaAlert2
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
vi .env
chmod +x start_prod.sh
```

Variables minimas para produccion:

```env
APP_ENV=production
COOKIE_SECURE=true
FLASK_DEBUG=false
PREFERRED_URL_SCHEME=https
REQUIRE_STRONG_SECRETS=true
TRUST_PROXY_COUNT=1
```

## 2. Prueba manual de produccion

```bash
./start_prod.sh
```

## 3. Dejarlo automatico con systemd

```bash
sudo cp docs/panamaalert.service.example /etc/systemd/system/panamaalert.service
sudo systemctl daemon-reload
sudo systemctl enable panamaalert
sudo systemctl restart panamaalert
sudo systemctl status panamaalert
```

## 4. Poner nginx delante

```bash
sudo cp docs/nginx.panamaalert.conf.example /etc/nginx/conf.d/panamaalert.conf
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx
```

## 5. Verificaciones rapidas

```bash
curl http://127.0.0.1:5000/health
curl -I http://127.0.0.1:5000/login
sudo journalctl -u panamaalert -n 80 --no-pager
```

## 6. Checklist minimo de salida

```text
- SECRET_KEY, JWT_SECRET y TOTP_ENC_KEY reales y distintos por entorno
- APP_ENV=production
- FLASK_DEBUG=false
- COOKIE_SECURE=true
- HTTPS delante de gunicorn
- nginx enviando X-Forwarded-Proto
- MariaDB accesible y con backup
- SMTP probado
- /health respondiendo OK
- sync de noticias/ofertas probado manualmente
```

## 7. Recomendaciones operativas

```text
- No expongas gunicorn directo a Internet; usa nginx delante.
- No subas .venv dentro del zip; recrealo en la VM.
- Mantén una sola ruta fija de despliegue en producción.
- Revisa /api/admin/security-events después de pruebas y fallos.
- Abre solo puertos necesarios en firewall.
- Si usas HTTPS real, sube TRUST_PROXY_COUNT según tu cadena de proxy.
```
