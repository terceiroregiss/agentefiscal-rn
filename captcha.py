import os, time, base64, requests
from dotenv import load_dotenv

load_dotenv()

TWOCAPTCHA_API_KEY = os.getenv("TWOCAPTCHA_API_KEY", "")

def resolver_captcha_imagem(page) -> str:
    """Captura a imagem do captcha da página e resolve via 2Captcha."""
    if not TWOCAPTCHA_API_KEY:
        raise RuntimeError("TWOCAPTCHA_API_KEY não configurada no .env")

    print("  [captcha] Capturando imagem do captcha...")

    # Pega a imagem do captcha como base64
    img_base64 = page.evaluate("""
    (function() {
        var img = document.querySelector('img[src*="captcha"], .captcha img, img[alt*="aptcha"]');
        if (!img) {
            // Tenta pegar pelo contexto visual
            var imgs = document.querySelectorAll('img');
            for (var i=0; i<imgs.length; i++) {
                if (imgs[i].width > 50 && imgs[i].height > 20) {
                    img = imgs[i];
                    break;
                }
            }
        }
        if (!img) return null;
        var canvas = document.createElement('canvas');
        canvas.width = img.naturalWidth || img.width;
        canvas.height = img.naturalHeight || img.height;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0);
        return canvas.toDataURL('image/png').split(',')[1];
    })();
    """)

    if not img_base64:
        # Fallback: screenshot do elemento
        img_el = page.locator('img').nth(0)
        img_bytes = img_el.screenshot()
        img_base64 = base64.b64encode(img_bytes).decode()

    print("  [captcha] Enviando ao 2Captcha...")
    resp = requests.post("https://2captcha.com/in.php", data={
        "key":    TWOCAPTCHA_API_KEY,
        "method": "base64",
        "body":   img_base64,
        "json":   1,
    }, timeout=30)

    data = resp.json()
    if data.get("status") != 1:
        raise RuntimeError(f"2Captcha erro ao submeter: {data}")

    captcha_id = data["request"]
    print(f"  [captcha] ID {captcha_id} — aguardando resolução...")

    for _ in range(24):
        time.sleep(5)
        res = requests.get("https://2captcha.com/res.php", params={
            "key":    TWOCAPTCHA_API_KEY,
            "action": "get",
            "id":     captcha_id,
            "json":   1,
        }, timeout=15)
        result = res.json()
        if result.get("status") == 1:
            texto = result["request"]
            print(f"  [captcha] Resolvido: {texto}")
            return texto
        if result.get("request") != "CAPCHA_NOT_READY":
            raise RuntimeError(f"2Captcha erro: {result}")

    raise RuntimeError("2Captcha timeout")
