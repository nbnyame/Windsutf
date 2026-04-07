"""Deploy PriceScout to Netlify using the REST API."""
import requests
import zipfile
import os
import io
import sys

TOKEN = os.environ.get("NETLIFY_AUTH_TOKEN", "").strip()
SITE_NAME = "pricescout-compare"
PUBLISH_DIR = os.path.join(os.path.dirname(__file__), "publish")
FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "netlify", "functions")
API = "https://api.netlify.com/api/v1"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


def create_site():
    """Create a new Netlify site."""
    print("Creating site...")
    r = requests.post(f"{API}/sites", headers=HEADERS, json={
        "name": SITE_NAME,
        "force_ssl": True,
    })
    if r.status_code == 422:
        # Name taken, try finding it
        print(f"  Site name '{SITE_NAME}' may already exist, looking it up...")
        r2 = requests.get(f"{API}/sites?name={SITE_NAME}", headers=HEADERS)
        sites = r2.json()
        for s in sites:
            if s.get("name") == SITE_NAME:
                print(f"  Found existing site: {s['url']}")
                return s["id"]
        # Try with a suffix
        import random
        alt = f"{SITE_NAME}-{random.randint(100,999)}"
        r = requests.post(f"{API}/sites", headers=HEADERS, json={"name": alt})
        if r.status_code not in (200, 201):
            print(f"  Error: {r.status_code} {r.text}")
            sys.exit(1)
    elif r.status_code not in (200, 201):
        print(f"  Error: {r.status_code} {r.text}")
        sys.exit(1)
    site = r.json()
    print(f"  Created: {site.get('url', site.get('ssl_url', ''))}")
    return site["id"]


def build_zip():
    """Create a zip archive of publish dir + functions."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Static files
        for root, dirs, files in os.walk(PUBLISH_DIR):
            for f in files:
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, PUBLISH_DIR)
                zf.write(full, arcname)
                print(f"  + {arcname}")
        # Functions
        if os.path.isdir(FUNCTIONS_DIR):
            for root, dirs, files in os.walk(FUNCTIONS_DIR):
                for f in files:
                    full = os.path.join(root, f)
                    arcname = os.path.join("netlify", "functions", os.path.relpath(full, FUNCTIONS_DIR))
                    # Netlify expects functions at root level in the deploy
                    # Actually for function deploys, we upload separately
    buf.seek(0)
    return buf


def deploy_site(site_id):
    """Deploy static files via zip upload."""
    print("\nBuilding deploy zip...")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PUBLISH_DIR):
            for f in files:
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, PUBLISH_DIR)
                zf.write(full, arcname)
                print(f"  + {arcname}")
    buf.seek(0)

    print("\nUploading to Netlify...")
    r = requests.post(
        f"{API}/sites/{site_id}/deploys",
        headers={**HEADERS, "Content-Type": "application/zip"},
        data=buf.getvalue(),
    )
    if r.status_code not in (200, 201):
        print(f"  Deploy error: {r.status_code} {r.text}")
        sys.exit(1)
    deploy = r.json()
    url = deploy.get("ssl_url") or deploy.get("url") or deploy.get("deploy_ssl_url", "")
    print(f"\n  Deployed successfully!")
    print(f"  URL: {url}")
    return deploy


if __name__ == "__main__":
    if not TOKEN:
        print("Set NETLIFY_AUTH_TOKEN environment variable first.")
        sys.exit(1)
    site_id = create_site()
    deploy_site(site_id)
    print("\nDone!")
